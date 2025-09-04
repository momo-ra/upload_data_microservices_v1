from services.db_services import execute_batch_values, fetch_all
from utils.log import setup_logger
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime

logger = setup_logger(__name__)

async def bulk_get_or_create_tags(tag_data, session, plant_id: int = None):
    """Insert tags into the database if they do not exist."""
    logger.info(f"📌 Bulk getting or creating tags: {len(list(tag_data.keys()))}")

    if not tag_data:
        logger.error("⚠️ No tag names provided. Skipping tag creation.")
        return {}

    existing_query = """
        SELECT id, name FROM tags WHERE name = ANY(:values)
    """
    existing_tags = await fetch_all(existing_query, {"values": list(tag_data.keys())}, session)

    tag_mapping = {tag[1]: tag[0] for tag in existing_tags} if existing_tags else {}

    current_time = datetime.now()
    missing_tags = [
        (name, tag_data[name].get("description"), tag_data[name].get("unit_of_measure"), plant_id, current_time, current_time)
        for name in tag_data.keys() if name not in tag_mapping
    ]

    if missing_tags:
        insert_query = """
            INSERT INTO tags (name, description, unit_of_measure, plant_id, created_at, updated_at)
            VALUES %s
            ON CONFLICT (name) DO NOTHING
            RETURNING id, name
        """
        await execute_batch_values(insert_query, missing_tags, session)
        existing_tags = await fetch_all(existing_query, {"values": list(tag_data.keys())}, session)

        if not existing_tags:
            logger.error("❌ Even after fetching, some tags are missing!")
            return tag_mapping

        tag_mapping.update({tag[1]: tag[0] for tag in existing_tags})

    return tag_mapping


async def get_tag_statistics(tag_ids, start_time, end_time, session):
    """Use TimescaleDB functions for efficient tag statistics."""
    try:
        # First check if TimescaleDB is available
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            );
        """))
        timescaledb_available = result.scalar()
        
        if timescaledb_available:
            # Use TimescaleDB optimized query
            query = text("""
                SELECT 
                    t.id,
                    t.name,
                    t.unit_of_measure,
                    COUNT(ts.value) AS data_points,
                    MIN(ts.timestamp) AS first_timestamp,
                    MAX(ts.timestamp) AS last_timestamp,
                    time_bucket_gapfill('1 day', ts.timestamp) AS day,
                    COUNT(ts.value) AS daily_count
                FROM tags t
                LEFT JOIN time_series ts ON t.id = ts.tag_id
                WHERE t.id = ANY(:tag_ids)
                  AND ts.timestamp BETWEEN :start_time AND :end_time
                GROUP BY t.id, t.name, t.unit_of_measure, day
                ORDER BY t.name, day
            """)
        else:
            # Fallback to regular PostgreSQL query
            query = text("""
                SELECT 
                    t.id,
                    t.name,
                    t.unit_of_measure,
                    COUNT(ts.value) AS data_points,
                    MIN(ts.timestamp) AS first_timestamp,
                    MAX(ts.timestamp) AS last_timestamp,
                    DATE_TRUNC('day', ts.timestamp) AS day,
                    COUNT(ts.value) AS daily_count
                FROM tags t
                LEFT JOIN time_series ts ON t.id = ts.tag_id
                WHERE t.id = ANY(:tag_ids)
                  AND ts.timestamp BETWEEN :start_time AND :end_time
                GROUP BY t.id, t.name, t.unit_of_measure, day
                ORDER BY t.name, day
            """)
        
        result = await session.execute(
            query,
            {
                "tag_ids": tag_ids,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        
        return result.fetchall()
    except Exception as e:
        logger.error(f"Error getting tag statistics: {e}")
        raise
    

