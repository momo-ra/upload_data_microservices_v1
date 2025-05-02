# utils/db_optimizer.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils.log import setup_logger

logger = setup_logger(__name__)

async def optimize_for_bulk_insert(session: AsyncSession):
    """تحسين إعدادات قاعدة البيانات للإدخال السريع"""
    try:
        await session.execute(text("""
            SET maintenance_work_mem = '1GB';
            SET work_mem = '50MB';
            SET synchronous_commit = OFF;
            SET vacuum_cost_delay = 0;
            ALTER TABLE time_series SET (autovacuum_enabled = false);
        """))
        logger.success("✅ Database optimized for bulk insert")
    except Exception as e:
        logger.error(f"❌ Error optimizing database: {e}")

async def restore_after_bulk_insert(session: AsyncSession):
    """استعادة إعدادات قاعدة البيانات بعد الإدخال"""
    try:
        await session.execute(text("""
            RESET maintenance_work_mem;
            RESET work_mem;
            SET synchronous_commit = ON;
            RESET vacuum_cost_delay;
            ALTER TABLE time_series SET (autovacuum_enabled = true);
            ANALYZE time_series;
        """))
        logger.success("✅ Database settings restored after bulk insert")
    except Exception as e:
        logger.error(f"❌ Error restoring database settings: {e}")