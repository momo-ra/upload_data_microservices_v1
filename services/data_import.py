import pandas as pd
from queries.tag_queries import bulk_get_or_create_tags
from queries.time_series_queries import bulk_insert_time_series_data
from database import get_plant_db
from utils.log import setup_logger
from utils.table_frequency import determine_frequency
from utils.check_hypertable import convert_to_hypertable
from utils.chunk_interval import get_chunk_interval
from services.job_client import JobsClient
from services.date_retrieval import convert_timestamp_format
from core.config import settings
from sqlalchemy.sql import text
from utils.db_init import verify_hypertable, ensure_time_series_constraints

logger = setup_logger(__name__)

class DataImportService:
    def __init__(self):
        self.jobs_client = JobsClient(settings.JOBS_SERVICE_URL)

    async def _check_for_duplicates(self, df_clean, timestamp_columns, tag_names, frequency, plant_id: str):
        """Check for duplicate data"""
        try:
            async for session in get_plant_db(plant_id):
                duplicates = []
                # Check for duplicates with different frequencies
                for tag_name in tag_names:
                    existing_data = await session.execute(
                        text("""
                        SELECT DISTINCT frequency 
                        FROM time_series ts
                        JOIN tags t ON ts.tag_id = t.id
                        WHERE t.name = :tag_name
                        AND ts.timestamp BETWEEN :start_date AND :end_date
                        """),
                        {
                            "tag_name": tag_name,
                            "start_date": df_clean[timestamp_columns].min(),
                            "end_date": df_clean[timestamp_columns].max()
                        }
                    )
                    existing_frequencies = existing_data.fetchall()
                    
                    if existing_frequencies and frequency not in [f[0] for f in existing_frequencies]:
                        duplicates.append({
                            "tag_name": tag_name,
                            "existing_frequency": existing_frequencies[0][0],
                            "new_frequency": frequency
                        })
                
                return duplicates
        except Exception as e:
            logger.error(f"Error checking duplicates: {e}")
            raise

    async def process_file(self, file_path: str, file_type: str = "xlsx", plant_id: str = None):
        """Process the file with duplicate checking"""
        if not plant_id:
            raise ValueError("Plant ID is required for data processing")
            
        logger.info(f"📌 Processing {file_type} file: {file_path} for Plant {plant_id}")
        try:
            # Read the file
            if file_type in ["xlsx", "xls"]:
                xls = pd.ExcelFile(file_path)
                sheet_name = xls.sheet_names[0]
                df = xls.parse(sheet_name, header=None)
            elif file_type == "csv":
                df = pd.read_csv(file_path, header=None)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # Extract header
            header = df.iloc[0].str.lower().str.strip()
            
            # Initialize description and unit_of_measure as dictionaries
            description = {}
            unit_of_measure = {}
            
            # Skip the timestamp column and process each data column
            for col in range(1, len(header)):
                tag_name = header[col]
                if pd.notna(tag_name):  # Check if tag name exists
                    # Get description and unit for this specific tag
                    desc = df.iloc[1, col] if pd.notna(df.iloc[1, col]) else None
                    unit = df.iloc[2, col] if pd.notna(df.iloc[2, col]) else None
                    
                    # Store in dictionaries with tag name as key
                    description[tag_name] = desc if isinstance(desc, str) and desc.strip() else None
                    unit_of_measure[tag_name] = unit if isinstance(unit, str) and unit.strip() else None

            # Create a clean DataFrame starting from the fourth row
            df_clean = df.iloc[3:].copy()
            df_clean.columns = header

            # Dynamically find the timestamp column
            timestamp_columns = [col for col in df_clean.columns if 'time' in col or 'timestamp' in col]
            
            if not timestamp_columns:
                raise ValueError("No timestamp column found in the data.")

            # Use the first valid timestamp column
            valid_timestamp_column = timestamp_columns[0]
            logger.info(f"Detected timestamp column: {valid_timestamp_column}")

            # Attempt to convert to datetime
            df_clean[valid_timestamp_column] = pd.to_datetime(
                df_clean[valid_timestamp_column], 
                errors='coerce'
            )

            # Check for NaT values after conversion
            if df_clean[valid_timestamp_column].isna().all():
                raise ValueError(f"All values in {valid_timestamp_column} could not be converted to datetime.")

            # Determine frequency using the actual timestamp column name
            frequency = await determine_frequency(df_clean, valid_timestamp_column)
            logger.info(f"📊 Detected data frequency: {frequency}")

            # Clean data
            df_clean = df_clean.dropna(subset=[valid_timestamp_column])
            tag_names = [col for col in df_clean.columns if col != valid_timestamp_column]

            # Check for duplicates
            duplicates = await self._check_for_duplicates(df_clean, valid_timestamp_column, tag_names, frequency, plant_id)
            
            if duplicates:
                # If duplicates found, send the file to jobs service
                job_id = await self.jobs_client.create_job(
                    file_path=file_path,
                    original_filename=file_path.split('/')[-1],
                    metadata={
                        "frequency": frequency,
                        "duplicates": duplicates,
                        "plant_id": plant_id
                    }
                )
                return {
                    "status": "duplicate_found",
                    "job_id": job_id,
                    "duplicates": duplicates,
                    "message": "Found duplicate data with different frequencies"
                }

            # If no duplicates, continue processing
            return await self._process_data(df_clean, valid_timestamp_column, tag_names, frequency, description, unit_of_measure, plant_id)

        except ValueError as e:
            logger.error(f"❌ Value error processing file: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
        except pd.errors.ParserError as e:
            logger.error(f"❌ Error parsing file: {str(e)}", exc_info=True)
            return {"status": "error", "message": "Invalid file format. Please check your file."}
        except Exception as e:
            logger.error(f"❌ Unexpected error processing file: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    async def _process_data(self, df_clean, timestamp_columns, tag_names, frequency, description, unit_of_measure, plant_id: str):
        """Process the data with improved error handling"""
        tag_data = {
        tag: {
            "description": description.get(tag) if description.get(tag) else f"Sensor data collected at {frequency} intervals",
            "unit_of_measure": unit_of_measure.get(tag)
        } for tag in tag_names
        }

        async for session in get_plant_db(plant_id):
            try:
                async with session.begin():
                    # Validate data types before proceeding
                    df_clean[timestamp_columns] = pd.to_datetime(df_clean[timestamp_columns], errors='coerce')
                    if df_clean[timestamp_columns].isna().any():
                        bad_rows = df_clean[df_clean[timestamp_columns].isna()].index.tolist()
                        logger.warning(f"⚠️ Found {len(bad_rows)} rows with invalid timestamps. Dropping them.")
                        df_clean = df_clean.dropna(subset=[timestamp_columns])
                    
                    tag_mapping = await bulk_get_or_create_tags(tag_data, session, int(plant_id))
                    chunk_interval = await get_chunk_interval(frequency)
                    
                    # Ensure time_series is a hypertable (only if TimescaleDB is available)
                    # Wrap in try-catch to prevent transaction abort
                    try:
                        is_hypertable = await verify_hypertable(plant_id)
                        if not is_hypertable:
                            # Check if TimescaleDB is available before trying to create hypertable
                            result = await session.execute(text("""
                                SELECT EXISTS (
                                    SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                                );
                            """))
                            timescaledb_available = result.scalar()
                            
                            if timescaledb_available:
                                await session.execute(text("""
                                    SELECT create_hypertable('time_series', 'timestamp', 
                                        if_not_exists => TRUE,
                                        migrate_data => TRUE,
                                        create_default_indexes => FALSE)
                                """))
                                logger.info("✅ Created hypertable for time_series")
                            else:
                                logger.info("ℹ️ TimescaleDB not available. Continuing with regular table.")
                    
                        # Ensure constraints are properly set after hypertable conversion
                        await ensure_time_series_constraints(plant_id)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ TimescaleDB not available or hypertable creation failed: {e}")
                        logger.info("ℹ️ Continuing without TimescaleDB optimization")
                    
                    # Try to optimize the hypertable if TimescaleDB is available
                    try:
                        await self.optimize_hypertable(session)
                    except Exception as e:
                        logger.warning(f"⚠️ TimescaleDB optimization failed: {e}")
                        logger.info("ℹ️ Continuing without TimescaleDB optimization")
                    
                    # Fixed version: Properly handle Series objects
                    time_series_data = []
                    for _, row in df_clean.iterrows():
                        timestamp_value = row[timestamp_columns]
                        
                        for tag_name in tag_names:
                            if tag_name in tag_mapping:
                                # Get the value and check if it's not NaN using pandas' proper method
                                value = row[tag_name]
                                if isinstance(value, pd.Series):
                                    # If it's a Series, take the first non-NaN value
                                    value = value.dropna().iloc[0] if not value.dropna().empty else None
                                
                                if pd.notna(value):  # This correctly checks both scalar and Series
                                    # Convert value to string to match database schema
                                    value_str = str(value) if value is not None else ''
                                    time_series_data.append((tag_mapping[tag_name], timestamp_value, value_str, frequency))
                    
                    if not time_series_data:
                        logger.warning("⚠️ No valid time series data to insert!")
                        return {
                            "status": "warning",
                            "message": "No valid data to process. Check your file."
                        }

                    await bulk_insert_time_series_data(time_series_data, session)
                    
                    return {
                        "status": "success",
                        "message": "Data processed successfully!",
                        "data_frequency": frequency,
                        "records_processed": len(time_series_data)
                    }

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error processing data: {str(e)}", exc_info=True)
                raise

    async def get_processing_status(self, job_id: str, plant_id: str = None):
        """Get the processing status of a job"""
        try:
            return await self.jobs_client.get_job_status(job_id)
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            raise

    async def handle_duplicates(self, job_id: str, decision: str, frequency: str = None, plant_id: str = None):
        """Handle user decision regarding duplicate data"""
        try:
            # Get job details
            job_status = await self.jobs_client.get_job_status(job_id)
            
            if decision == "process":
                # Process data with new frequency
                return await self.jobs_client.make_decision(job_id, "process")
            elif decision == "skip":
                # Ignore duplicate data
                return await self.jobs_client.make_decision(job_id, "skip")
            else:
                raise ValueError(f"Invalid decision: {decision}")

        except Exception as e:
            logger.error(f"Error handling duplicate decision: {e}")
            raise

    async def handle_duplicate_decision(self, job_id: str, decision: str):
        """Handle user decision regarding duplicate data (backward compatibility)"""
        return await self.handle_duplicates(job_id, decision)

    async def optimize_hypertable(self, session):
        """Apply TimescaleDB optimization settings."""
        try:
            # First check if TimescaleDB is available
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                );
            """))
            timescaledb_available = result.scalar()
            
            if not timescaledb_available:
                logger.info("ℹ️ TimescaleDB not available. Skipping optimization.")
                return
            
            # Check if timescaledb_information schema exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = 'timescaledb_information'
                );
            """))
            schema_exists = result.scalar()
            
            if not schema_exists:
                logger.info("ℹ️ TimescaleDB information schema not available. Skipping optimization.")
                return
            
            # Set chunk time interval based on data frequency
            await session.execute(text("""
                SELECT set_chunk_time_interval('time_series', INTERVAL '1 week');
            """))
            
            # Enable compression (great for historical data)
            await session.execute(text("""
                ALTER TABLE time_series SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'tag_id',
                    timescaledb.compress_orderby = 'timestamp'
                );
            """))
            
            # Add compression policy to automatically compress chunks
            await session.execute(text("""
                SELECT add_compression_policy('time_series', INTERVAL '1 month');
            """))
            
            # Create a continuous aggregate for common queries
            await session.execute(text("""
                CREATE MATERIALIZED VIEW time_series_daily_avg
                WITH (timescaledb.continuous) AS
                SELECT tag_id,
                       time_bucket('1 day', timestamp) AS bucket,
                       AVG(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS avg_value,
                       COUNT(*) as sample_count
                FROM time_series
                GROUP BY tag_id, bucket;
            """))
            
            # Add refresh policy for the continuous aggregate
            await session.execute(text("""
                SELECT add_continuous_aggregate_policy('time_series_daily_avg',
                    start_offset => INTERVAL '1 month',
                    end_offset => INTERVAL '1 hour',
                    schedule_interval => INTERVAL '1 day');
            """))
            
            logger.info("✅ TimescaleDB optimizations applied successfully")
        except Exception as e:
            logger.warning(f"⚠️ TimescaleDB optimization failed: {e}")
            # Don't raise the exception, just log it and continue
            pass