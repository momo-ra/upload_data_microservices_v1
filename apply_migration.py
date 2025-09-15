#!/usr/bin/env python3
"""
Migration script to remove workspace_id from time_series table
"""
import asyncio
import asyncpg
from core.config import settings
from utils.log import setup_logger

logger = setup_logger(__name__)

async def apply_migration():
    """Apply the migration to remove workspace_id from time_series"""
    
    # Get all plant database URLs
    plant_ids = [1, 2]  # Add more plant IDs as needed
    
    for plant_id in plant_ids:
        try:
            # Get plant database URL and convert to asyncpg format
            try:
                db_url = settings.get_plant_database_url(f"PLANT{plant_id}_DATABASE")
            except ValueError:
                # Try alternative naming
                db_url = settings.get_plant_database_url(f"PLANT_DATABASE" if plant_id == 1 else f"PLANT2_DATABASE")
            
            # Convert from SQLAlchemy format to asyncpg format
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            
            # Connect to the database
            conn = await asyncpg.connect(db_url)
            
            logger.info(f"🔄 Applying migration to Plant {plant_id} database...")
            
            # Read and execute the migration SQL
            with open('migrations/remove_workspace_id_from_time_series.sql', 'r') as f:
                migration_sql = f.read()
            
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement:
                    try:
                        await conn.execute(statement)
                        logger.info(f"✅ Executed: {statement[:50]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ Statement failed (may already be applied): {e}")
            
            await conn.close()
            logger.success(f"✅ Migration completed for Plant {plant_id}")
            
        except Exception as e:
            logger.error(f"❌ Migration failed for Plant {plant_id}: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(apply_migration())
