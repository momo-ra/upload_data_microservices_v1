from utils.log import setup_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from queries.db_queries import get_number_of_rows_in_table, insert_data_into_table, get_table_data
import asyncio
from database import get_plant_db
logger = setup_logger(__name__)

async def _process_table(table_schema, table_name, source_engine, target_session, max_rows=10000):
    """Process a single table with optimized memory usage"""
    try:
        full_table_name = f'"{table_schema}"."{table_name}"'
        simple_table_name = table_name
        
        # Create a new connection for each table to prevent "operation in progress" errors
        async with source_engine.connect() as source_conn:
            # Get row count
            number_of_rows = await get_number_of_rows_in_table(full_table_name, source_conn)
            logger.info(f"Table: {full_table_name} - Rows: {number_of_rows}")
            
            if number_of_rows > 0:
                # Process the table data in batches
                batch_size = min(1000, max_rows)
                
                # Use the optimized streaming approach
                processed_rows = 0
                async for batch in get_table_data(full_table_name, source_conn, batch_size):
                    if batch:
                        inserted = await insert_data_into_table(simple_table_name, batch, target_session)
                        processed_rows += inserted
                        
                        # Log progress for large tables
                        if number_of_rows > 10000 and processed_rows % 10000 == 0:
                            logger.info(f"Progress for {full_table_name}: {processed_rows}/{number_of_rows} rows")
                
                logger.success(f"Completed {full_table_name}: {processed_rows} rows processed")
                return True
            else:
                logger.info(f"Skipping empty table: {full_table_name}")
                return True
    except Exception as e:
        logger.error(f"Error processing table {table_schema}.{table_name}: {e}")
        return False

async def import_data_from_db(db_url, plant_id: str = None, max_rows=10000, concurrency=3):
    """Import data from source database to target database with optimized performance"""
    if not plant_id:
        raise ValueError("Plant ID is required for database import")
        
    tables_needed_to_import = ['time_series', 'tags', 'polling_tasks']
    
    try:
        # Connect to source database
        source_engine = create_async_engine(db_url)
        
        async with source_engine.begin() as conn:
            # Get only regular tables (not views) and exclude system schemas
            tables_query = await conn.execute(text("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                AND table_type = 'BASE TABLE'
            """))
            all_tables = tables_query.all()
            logger.success(f"Found {len(all_tables)} tables to import")
            
            # Filter large tables based on priority
            if max_rows > 0:
                important_tables = []
                regular_tables = []
                
                for table in all_tables:
                    schema, name = table
                    if name in tables_needed_to_import:
                        important_tables.append(table)
                    else:
                        regular_tables.append(table)
                
                # Process important tables first, then regular tables
                tables_to_process = important_tables
            else:
                tables_to_process = all_tables
            
            # Process tables using plant-specific database session
            async for target_session in get_plant_db(plant_id):
                # Process tables in parallel with controlled concurrency
                for i in range(0, len(tables_to_process), concurrency):
                    batch = tables_to_process[i:i+concurrency]
                    tasks = []
                    
                    for table in batch:
                        schema, name = table
                        task = _process_table(schema, name, source_engine, target_session, max_rows)
                        tasks.append(task)
                    
                    # Wait for all tasks in this batch to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Check results
                    for j, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.error(f"Error processing table {batch[j][0]}.{batch[j][1]}: {result}")
            
            logger.success("Successfully completed database import")
            return True
    except Exception as e:
        logger.error(f"Error importing data from db: {e}")
        raise e
