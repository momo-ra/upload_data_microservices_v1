from sqlalchemy import text
from database import AsyncSessionLocal
from utils.log import setup_logger

logger = setup_logger(__name__)

async def initialize_timescaledb():
    """Initialize TimescaleDB with appropriate extensions and settings."""
    logger.info("🔧 Initializing TimescaleDB...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Enable TimescaleDB extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            
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
            logger.info("✅ TimescaleDB initialization complete!")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Failed to initialize TimescaleDB: {str(e)}", exc_info=True)
            raise

async def verify_hypertable():
    """Verify time_series is a proper hypertable."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text("""
                SELECT * FROM timescaledb_information.hypertables 
                WHERE hypertable_name = 'time_series'
            """))
            is_hypertable = result.fetchone() is not None
            
            if is_hypertable:
                logger.info("✅ time_series is a valid hypertable.")
            else:
                logger.warning("⚠️ time_series is NOT a hypertable!")
                
            return is_hypertable
            
        except Exception as e:
            logger.error(f"❌ Error verifying hypertable: {str(e)}", exc_info=True)
            return False 