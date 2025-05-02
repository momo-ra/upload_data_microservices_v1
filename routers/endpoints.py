# upload_service/api/endpoints.py
from fastapi import APIRouter, UploadFile, File
from services.data_import import DataImportService
import shutil
import os
from typing import Optional
from database import AsyncSessionLocal
from sqlalchemy import text
from fastapi import HTTPException
from utils.log import setup_logger
from services.db_import_services import import_data_from_db

logger = setup_logger(__name__)

router = APIRouter()

@router.post("/upload-excel/")
async def upload_excel(file: UploadFile = File(...)):
    # حفظ الملف مؤقتاً
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        service = DataImportService()
        # Extract the file extension to determine the file type
        file_extension = file.filename.split('.')[-1]
        result = await service.process_file(file_path, file_extension)
        return result
    finally:
        # مسح الملف المؤقت
        os.remove(file_path)

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    service = DataImportService()
    return await service.get_processing_status(job_id)

@router.post("/decide/{job_id}")
async def make_decision(job_id: str, decision: str, frequency: Optional[str] = None):
    service = DataImportService()
    return await service.handle_duplicates(job_id, decision, frequency)

@router.get("/metrics/{tag_id}")
async def get_metrics(tag_id: int, start_time: str, end_time: str, interval: str = "1 hour"):
    """Leverage TimescaleDB time_bucket for efficient time-series analytics."""
    try:
        async with AsyncSessionLocal() as session:
            query = text(r"""
                SELECT 
                    time_bucket(:interval, timestamp) AS bucket,
                    AVG(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS avg_value,
                    MIN(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS min_value,
                    MAX(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS max_value,
                    COUNT(*) AS sample_count
                FROM time_series
                WHERE tag_id = :tag_id
                  AND timestamp BETWEEN :start_time AND :end_time
                GROUP BY bucket
                ORDER BY bucket
            """)
            
            result = await session.execute(
                query, 
                {
                    "tag_id": tag_id, 
                    "start_time": start_time, 
                    "end_time": end_time,
                    "interval": interval
                }
            )
            
            metrics = [
                {
                    "timestamp": str(row[0]),
                    "avg": float(row[1]) if row[1] else None,
                    "min": float(row[2]) if row[2] else None,
                    "max": float(row[3]) if row[3] else None,
                    "count": row[4]
                }
                for row in result.fetchall()
            ]
            
            return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced-metrics/{tag_id}")
async def get_advanced_metrics(tag_id: int, start_time: str, end_time: str, interval: str = "1 hour"):
    """Advanced TimescaleDB analytics with first/last values and interpolation."""
    try:
        async with AsyncSessionLocal() as session:
            query = text(r"""
                SELECT 
                    time_bucket_gapfill(:interval, timestamp) AS bucket,
                    AVG(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS avg_value,
                    MIN(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS min_value,
                    MAX(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS max_value,
                    first(value::numeric, timestamp) AS first_value,
                    last(value::numeric, timestamp) AS last_value,
                    COUNT(*) AS sample_count,
                    locf(AVG(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END)) AS interpolated_value
                FROM time_series
                WHERE tag_id = :tag_id
                  AND timestamp BETWEEN :start_time AND :end_time
                GROUP BY bucket
                ORDER BY bucket
            """)
            
            result = await session.execute(
                query, 
                {
                    "tag_id": tag_id, 
                    "start_time": start_time, 
                    "end_time": end_time,
                    "interval": interval
                }
            )
            
            metrics = [
                {
                    "timestamp": str(row[0]),
                    "avg": float(row[1]) if row[1] else None,
                    "min": float(row[2]) if row[2] else None,
                    "max": float(row[3]) if row[3] else None,
                    "first": float(row[4]) if row[4] else None,
                    "last": float(row[5]) if row[5] else None,
                    "count": row[6],
                    "interpolated": float(row[7]) if row[7] else None
                }
                for row in result.fetchall()
            ]
            
            return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Error fetching advanced metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retention/configure")
async def configure_retention(interval: str = "3 months"):
    """Configure TimescaleDB data retention policies."""
    try:
        async with AsyncSessionLocal() as session:
            # Add a data retention policy
            query = text("""
                SELECT add_retention_policy('time_series', INTERVAL :interval)
            """)
            
            await session.execute(query, {"interval": interval})
            await session.commit()
            
            return {"status": "success", "message": f"Retention policy set to {interval}"}
    except Exception as e:
        logger.error(f"Error configuring retention policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/import-db")
async def import_db(db_url:str):
    try:
        data = await import_data_from_db(db_url)
        return {"status": "success", "message": "Database imported successfully", "data": data}
    except Exception as e:
        logger.error(f"Error importing database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))