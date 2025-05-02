import psycopg2
from utils.log import setup_logger
from core.config import settings
from database import AsyncSessionLocal
from sqlalchemy import text
import time
from sqlalchemy.ext.asyncio import AsyncSession
import io


logger = setup_logger(__name__)


def get_db_connection(retries=3, delay=2):
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(**settings.DB_CONFIG)
            logger.info("✅ Successfully connected to TimescaleDB via psycopg2!")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"❌ Database Connection Error: {e}")
            logger.info(f"🔍 DB Config: {settings.DB_CONFIG}")
            if attempt < retries - 1:
                logger.info(f"🔄 Retrying connection in {delay} seconds...")
                time.sleep(delay)
            else:
                raise

async def fetch_all(query: str, params: dict = None, session: AsyncSession = None) -> list:
    """Fetch existing time-series data efficiently."""
    
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True  # ✅ سيتم إغلاق الجلسة إذا تم إنشاؤها داخل الدالة

    try:
        if params and isinstance(params, list):
            if not params:
                return []
            
            # ✅ فرض نوع البيانات في الاستعلام
            tag_ids, timestamps = zip(*params)
            query = """
                SELECT t.tag_id, t.timestamp
                FROM time_series t
                WHERE (t.tag_id, t.timestamp) IN (
                    SELECT unnest(CAST(:tag_ids AS INTEGER[])), 
                           unnest(CAST(:timestamps AS TIMESTAMP[]))
                )
            """
            result = await session.execute(
                text(query), {"tag_ids": list(tag_ids), "timestamps": list(timestamps)}
            )
            return result.fetchall()
        else:
            result = await session.execute(text(query), params)
            return result.fetchall()
    except Exception as e:
        logger.error(f"❌ Fetch error: {e}")
        return []
    finally:
        if close_session:
            await session.close()  # ✅ إغلاق الجلسة فقط إذا تم إنشاؤها داخل الدالة

async def execute_batch_values(query: str, values: list, session: AsyncSession) -> list:
    """Execute batch insert using TimescaleDB's optimized methods."""
    try:
        if not values:
            logger.warning("⚠️ No values provided for batch insert")
            return []
            
        conn = await session.connection()
        raw_conn = await conn.get_raw_connection()
        asyncpg_conn = raw_conn._connection
        
        # Use more efficient batch processing
        if "INSERT INTO tag" in query:
            # For tag table, use simple batch insert
            num_columns = len(values[0])
            placeholders = ", ".join(f"${i+1}" for i in range(num_columns))
            query = query.replace("VALUES %s", f"VALUES ({placeholders})")
            
            for value_chunk in [values[i:i+1000] for i in range(0, len(values), 1000)]:
                await asyncpg_conn.executemany(query, value_chunk)
                
        elif "INSERT INTO time_series" in query:
            # For time_series, use the COPY command for maximum efficiency
            copy_stmt = "COPY time_series (tag_id, timestamp, value, frequency) FROM STDIN"
            
            buffer = io.StringIO()
            for row in values:
                # Convert row data to tab-separated string format
                formatted_values = [
                    str(row[0]),  # tag_id
                    row[1].isoformat(),  # timestamp
                    str(row[2]) if row[2] is not None else '',  # value
                    str(row[3])  # frequency
                ]
                buffer.write('\t'.join(formatted_values) + '\n')
            
            buffer.seek(0)
            await asyncpg_conn.copy_to_table('time_series', source=buffer, format='csv', 
                                            delimiter='\t', null='')
        
        logger.info(f"✅ Batch operation successful! Processed {len(values)} rows.")
        return values
    except Exception as e:
        logger.error(f"❌ Batch operation error: {str(e)}", exc_info=True)
        raise