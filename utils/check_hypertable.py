from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from utils.log import setup_logger

logger = setup_logger(__name__)

async def convert_to_hypertable(session: AsyncSession, table_name: str, time_column: str, chunk_interval: str = '1 day'):
    """
    Convert an existing table to a hypertable if it's not already one.
    
    Args:
        session (AsyncSession): Database session
        table_name (str): Name of the table to convert
        time_column (str): Name of the timestamp column
        chunk_interval (str): Size of chunks (e.g., '1 day', '1 hour')
    """
    try:
        # First, check if the table is already a hypertable
        check_sql = """
        SELECT EXISTS (
            SELECT 1 
            FROM timescaledb_information.hypertables 
            WHERE hypertable_name = :table_name
        );
        """
        result = await session.execute(text(check_sql), {"table_name": table_name})
        is_hypertable = result.scalar()

        if not is_hypertable:
            # If it's not a hypertable, convert it
            convert_sql = f"""
            SELECT create_hypertable(
                '{table_name}', 
                '{time_column}',
                chunk_time_interval => INTERVAL '{chunk_interval}',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
            """
            await session.execute(text(convert_sql))
            logger.success(f"✅ Table {table_name} converted to hypertable with chunk interval {chunk_interval}")
        else:
            # If it's already a hypertable, update the chunk_interval
            update_sql = f"""
            SELECT set_chunk_time_interval(
                '{table_name}', 
                INTERVAL '{chunk_interval}'
            );
            """
            await session.execute(text(update_sql))
            logger.info(f"ℹ️ Updated chunk interval to {chunk_interval} for table {table_name}")

    except Exception as e:
        logger.error(f"❌ Error working with hypertable: {e}")
        raise e