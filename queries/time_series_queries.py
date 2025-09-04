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
            
            # First, check for existing records to avoid duplicates
            existing_query = """
                SELECT tag_id, timestamp FROM time_series 
                WHERE (tag_id, timestamp) IN (
                    SELECT unnest($1::int[]), unnest($2::timestamp[])
                )
            """
            existing_records = await asyncpg_conn.fetch(existing_query, tag_ids, timestamps)
            existing_pairs = {(row['tag_id'], row['timestamp']) for row in existing_records}
            
            # Filter out existing records
            filtered_batch = []
            filtered_tag_ids = []
            filtered_timestamps = []
            filtered_values = []
            filtered_frequencies = []
            
            for j, (tag_id, timestamp, value, frequency) in enumerate(batch):
                if (tag_id, timestamp) not in existing_pairs:
                    filtered_batch.append((tag_id, timestamp, value, frequency))
                    filtered_tag_ids.append(tag_id)
                    filtered_timestamps.append(timestamp)
                    filtered_values.append(value)
                    filtered_frequencies.append(frequency)
            
            if filtered_batch:
                # Use asyncpg directly with pure SQL - without ON CONFLICT clause
                await asyncpg_conn.execute("""
                    INSERT INTO time_series (tag_id, timestamp, value, frequency)
                    SELECT * FROM unnest($1::int[], $2::timestamp[], $3::text[], $4::text[])
                """, filtered_tag_ids, filtered_timestamps, filtered_values, filtered_frequencies)
                
                logger.info(f"✅ Batch {i//batch_size + 1}: Inserted {len(filtered_batch)} records (skipped {len(batch) - len(filtered_batch)} duplicates)")
            else:
                logger.info(f"ℹ️ Batch {i//batch_size + 1}: All {len(batch)} records already exist, skipping")
        
        await session.commit()
        logger.info(f"✅ TimescaleDB optimized insert complete")
        
    except Exception as e:
        logger.error(f"❌ Error inserting time-series data: {e}", exc_info=True)
        raise