from sqlalchemy import text, inspect
from utils.log import setup_logger
import asyncio

logger = setup_logger(__name__)

async def get_number_of_rows_in_table(table_name, db):
    try:
        query = text(f"SELECT COUNT(*) FROM {table_name}")
        result = await db.execute(query)
        return result.scalar()
    except Exception as e:
        logger.error(f"Error getting row count for {table_name}: {e}")
        return 0

async def   insert_data_into_table(table_name, data, db):
    """Insert data with transaction control and conflict handling"""
    if not data:
        return 0
        
    try:
        # Start a transaction
        async with db.begin():
            # Get column names
            first_row = data[0]
            
            if hasattr(first_row, '_fields'):  # Named tuple
                columns = first_row._fields
            elif hasattr(first_row, '_asdict'):  # Row proxy
                columns = first_row._asdict().keys()
            else:  # Regular tuple
                # Get column info from the database
                query = text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name.replace('"', '')}'
                    ORDER BY ordinal_position
                """)
                result = await db.execute(query)
                columns = [row[0] for row in result.fetchall()]
            
            # Format column names
            column_names = [f'"{col}"' for col in columns]
            columns_str = ", ".join(column_names)
            
            # Prepare the batch insert statement
            values_list = []
            params = {}
            
            for i, row in enumerate(data):
                # Convert Row objects to dictionaries if needed
                if hasattr(row, '_asdict'):
                    row_dict = row._asdict()
                    row_values = [row_dict.get(col) for col in columns]
                else:
                    row_values = row
                
                # Create placeholders
                placeholders = []
                for j, value in enumerate(row_values):
                    param_name = f"p{i}_{j}"
                    placeholders.append(f":{param_name}")
                    params[param_name] = value
                
                values_list.append(f"({', '.join(placeholders)})")
            
            # Build the query with ON CONFLICT DO NOTHING
            insert_query = text(f"""
                INSERT INTO "{table_name}" ({columns_str})
                VALUES {', '.join(values_list)}
                ON CONFLICT DO NOTHING
            """)
            
            # Execute the insert
            result = await db.execute(insert_query, params)
            
        return len(data)
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting data into table {table_name}: {e}")
        return 0
    
async def get_table_data(table_name, db, batch_size=1000):
    """Stream data from table using server-side cursor to minimize memory usage"""
    try:
        # Use stream() instead of execute() for server-side cursors
        query = text(f"SELECT * FROM {table_name}")
        result = await db.stream(query)
        
        # Fetch in batches
        batch = []
        count = 0
        
        async for row in result:
            batch.append(row)
            count += 1
            
            if count >= batch_size:
                yield batch
                batch = []
                count = 0
        
        # Yield any remaining rows
        if batch:
            yield batch
            
    except Exception as e:
        logger.error(f"Error getting data from {table_name}: {e}")
        yield []