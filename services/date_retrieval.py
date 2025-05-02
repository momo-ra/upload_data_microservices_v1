from sqlalchemy import text
from database import AsyncSessionLocal
from utils.log import setup_logger
from datetime import datetime

logger = setup_logger(__name__)

def convert_timestamp_format(timestamp: str):
    """Convert different timestamp formats to PostgreSQL format (YYYY-MM-DD HH:MM:SS)."""
    accepted_formats = [
        "%Y-%m-%d %H:%M:%S",  # 2024-11-29 08:00:00
        "%Y-%m-%d",  # 2024-11-29
        "%d/%m/%Y %H:%M:%S",  # 29/11/2024 08:00:00
        "%d/%m/%Y",  # 29/11/2024
        "%m/%d/%Y %H:%M:%S",  # 11/29/2024 08:00:00
        "%m/%d/%Y",  # 11/29/2024
    ]

    for fmt in accepted_formats:
        try:
            return datetime.strptime(timestamp, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    raise ValueError(f"❌ Unsupported timestamp format: {timestamp}")

### 📌 1️⃣ List All Tables
async def list_tables():
    """Retrieve all available tables."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            raise

### 📌 2️⃣ Get Table Columns & Data Types
async def get_table_columns(table_name: str):
    """Retrieve column names and data types."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = :table
            """), {"table": table_name})
            return [{"name": row[0], "type": row[1]} for row in result]
        except Exception as e:
            logger.error(f"Error getting table columns: {e}")
            raise

### 📌 3️⃣ Retrieve Table Data with Filtering
async def get_table_data(table_name: str, start_time: str = None, end_time: str = None, limit: int = 100):
    """Fetch data from a table with optional time filtering."""
    async with AsyncSessionLocal() as session:
        try:
            query = f"SELECT * FROM {table_name}"
            conditions = []
            params = {}

            if start_time:
                start_time = convert_timestamp_format(start_time)
                conditions.append("timestamp >= :start_time")
                params["start_time"] = start_time
            if end_time:
                end_time = convert_timestamp_format(end_time)
                conditions.append("timestamp <= :end_time")
                params["end_time"] = end_time

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT :limit"
            params["limit"] = limit

            result = await session.execute(text(query), params)
            return [dict(row) for row in result.mappings()]
        except ValueError as e:
            logger.error(f"Timestamp format error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error retrieving table data: {e}")
            raise

### 📌 4️⃣ Delete All Data from a Table
async def delete_table_data(table_name: str):
    """Delete all records from a table."""
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                await session.execute(text(f"DELETE FROM {table_name}"))
            return "All records deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting table data: {e}")
            raise

### 📌 5️⃣ Update a Specific Record in a Table
async def update_record(table_name: str, record_id: int, update_data: dict):
    """Update a record in a table."""
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
                update_data["record_id"] = record_id

                query = text(f"UPDATE {table_name} SET {set_clause} WHERE id = :record_id")
                await session.execute(query, update_data)
                
            return "Record updated successfully"
        except Exception as e:
            logger.error(f"Error updating record: {e}")
            raise