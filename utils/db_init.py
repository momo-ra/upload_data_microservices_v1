from sqlalchemy import text
from database import get_plant_db
from utils.log import setup_logger

logger = setup_logger(__name__)

async def ensure_time_series_constraints(plant_id: str = None):
    """Ensure time_series table has proper constraints after hypertable conversion."""
    if not plant_id:
        logger.warning("⚠️ Plant ID is required for constraint verification")
        return
        
    async for session in get_plant_db(plant_id):
        try:
            # Check if the composite primary key constraint exists
            result = await session.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'time_series' 
                AND constraint_type = 'PRIMARY KEY'
            """))
            primary_key_exists = result.fetchone() is not None
            
            if not primary_key_exists:
                logger.warning("⚠️ Primary key constraint missing on time_series table. Creating it...")
                
                # Create the composite primary key constraint
                await session.execute(text("""
                    ALTER TABLE time_series 
                    ADD CONSTRAINT time_series_pkey 
                    PRIMARY KEY (tag_id, timestamp)
                """))
                logger.info("✅ Created composite primary key constraint on time_series")
            else:
                logger.info("✅ Primary key constraint already exists on time_series")
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.warning(f"⚠️ Error ensuring time_series constraints for Plant {plant_id}: {str(e)}")
            # Don't raise the exception, just log it and continue
            return

async def initialize_timescaledb(plant_id: str = None):
    """Initialize TimescaleDB with appropriate extensions and settings."""
    if not plant_id:
        logger.warning("⚠️ Plant ID is required for TimescaleDB initialization")
        return
        
    logger.info(f"🔧 Initializing TimescaleDB for Plant {plant_id}...")
    
    async for session in get_plant_db(plant_id):
        try:
            # Check if TimescaleDB extension is available
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                );
            """))
            timescaledb_available = result.scalar()
            
            if not timescaledb_available:
                logger.warning("⚠️ TimescaleDB extension not available. Skipping TimescaleDB initialization.")
                return
            
            # Enable TimescaleDB extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            
            # Check if timescaledb_information schema exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = 'timescaledb_information'
                );
            """))
            schema_exists = result.scalar()
            
            if not schema_exists:
                logger.warning("⚠️ TimescaleDB information schema not available. Skipping hypertable operations.")
                return
            
            # First check if the table is already a hypertable
            result = await session.execute(text("""
                SELECT * FROM timescaledb_information.hypertables 
                WHERE hypertable_name = 'time_series'
            """))
            is_hypertable = result.fetchone() is not None
            
            if not is_hypertable:
                # Create hypertable if it doesn't exist - WITH migrate_data=true for non-empty tables
                await session.execute(text("""
                    SELECT create_hypertable('time_series', 'timestamp', 
                        if_not_exists => TRUE,
                        migrate_data => TRUE,
                        create_default_indexes => FALSE)
                """))
                logger.info("✅ Converted time_series to hypertable with data migration")
            else:
                logger.info("✅ time_series is already a hypertable")
            
            # Ensure constraints are properly set after hypertable conversion
            await ensure_time_series_constraints(plant_id)
            
            # Create optimized indexes
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_time_series_tag_time 
                ON time_series (tag_id, timestamp DESC);
            """))
            
            # Set chunk_time_interval appropriately
            await session.execute(text("""
                SELECT set_chunk_time_interval('time_series', INTERVAL '1 day');
            """))
            
            await session.commit()
            logger.info(f"✅ TimescaleDB initialization complete for Plant {plant_id}!")
            
        except Exception as e:
            await session.rollback()
            logger.warning(f"⚠️ TimescaleDB initialization failed for Plant {plant_id}: {str(e)}")
            # Don't raise the exception, just log it and continue
            return

async def verify_hypertable(plant_id: str = None):
    """Verify time_series is a proper hypertable."""
    if not plant_id:
        logger.warning("⚠️ Plant ID is required for hypertable verification")
        return False
        
    async for session in get_plant_db(plant_id):
        try:
            # First check if TimescaleDB is available
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                );
            """))
            timescaledb_available = result.scalar()
            
            if not timescaledb_available:
                logger.info("ℹ️ TimescaleDB not available. Skipping hypertable verification.")
                return False
            
            # Check if timescaledb_information schema exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = 'timescaledb_information'
                );
            """))
            schema_exists = result.scalar()
            
            if not schema_exists:
                logger.info("ℹ️ TimescaleDB information schema not available. Skipping hypertable verification.")
                return False
            
            result = await session.execute(text("""
                SELECT * FROM timescaledb_information.hypertables 
                WHERE hypertable_name = 'time_series'
            """))
            is_hypertable = result.fetchone() is not None
            
            if is_hypertable:
                logger.info(f"✅ time_series is a valid hypertable for Plant {plant_id}.")
            else:
                logger.info(f"ℹ️ time_series is NOT a hypertable for Plant {plant_id}.")
                
            return is_hypertable
            
        except Exception as e:
            logger.warning(f"⚠️ Error verifying hypertable for Plant {plant_id}: {str(e)}")
            return False 