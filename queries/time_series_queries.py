from services.db_services import execute_batch_values, fetch_all
from utils.log import setup_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
logger = setup_logger(__name__)

async def bulk_insert_time_series_data(time_series_data, session: AsyncSession):
    """Optimized TimescaleDB batch insert with conflict detection."""
    logger.info(f"📌 Preparing to insert {len(time_series_data)} time-series records")
    
    if not time_series_data:
        logger.warning("⚠️ No time-series data provided. Skipping insert.")
        return
    
    try:
        # Get raw asyncpg connection
        conn = await session.connection()
        raw_conn = await conn.get_raw_connection()
        asyncpg_conn = raw_conn._connection
        
        # Set a batch size to avoid memory issues
        batch_size = 50000
        
        for i in range(0, len(time_series_data), batch_size):
            batch = time_series_data[i:i + batch_size]
            
            # Prepare arrays for the unnest function
            tag_ids = [record[0] for record in batch]
            timestamps = [record[1] for record in batch]
            values = [str(record[2]) if record[2] is not None else '' for record in batch]
            frequencies = [record[3] for record in batch]
            
            # Use ON CONFLICT DO NOTHING to handle duplicates gracefully
            # This is the most reliable approach for PostgreSQL
            await asyncpg_conn.execute("""
                INSERT INTO time_series (tag_id, timestamp, value, frequency)
                SELECT * FROM unnest($1::int[], $2::timestamp[], $3::text[], $4::text[])
                ON CONFLICT (tag_id, timestamp) DO NOTHING
            """, tag_ids, timestamps, values, frequencies)
            
            logger.info(f"✅ Batch {i//batch_size + 1}: Processed {len(batch)} records (duplicates automatically skipped)")
        
        await session.commit()
        logger.info(f"✅ TimescaleDB optimized insert complete")
        
    except Exception as e:
        logger.error(f"❌ Error inserting time-series data: {e}", exc_info=True)
        raise