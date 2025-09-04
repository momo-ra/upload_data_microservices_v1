# upload_service/api/endpoints.py
from fastapi import APIRouter, UploadFile, File, Header, Depends, HTTPException
from services.data_import import DataImportService
import shutil
import os
from typing import Optional, AsyncGenerator
from database import get_central_db, get_plant_db_with_context, get_plant_context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils.log import setup_logger
from services.db_import_services import import_data_from_db
from datetime import datetime

logger = setup_logger(__name__)

router = APIRouter()

@router.post("/upload-file/")
async def upload_excel(
    file: UploadFile = File(...),
    plant_id: str = Header(..., alias="plant-id")
):
    # حفظ الملف مؤقتاً
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        service = DataImportService()
        # Extract the file extension to determine the file type
        file_extension = file.filename.split('.')[-1]
        result = await service.process_file(file_path, file_extension, plant_id)
        return result
    finally:
        # مسح الملف المؤقت
        os.remove(file_path)

@router.get("/status/{job_id}")
async def get_status(
    job_id: str,
    plant_id: str = Header(..., alias="plant-id")
):
    service = DataImportService()
    return await service.get_processing_status(job_id, plant_id)

@router.post("/decide/{job_id}")
async def make_decision(
    job_id: str, 
    decision: str, 
    frequency: Optional[str] = None,
    plant_id: str = Header(..., alias="plant-id")
):
    service = DataImportService()
    return await service.handle_duplicates(job_id, decision, frequency, plant_id)

@router.get("/uploads/history")
async def get_upload_history(
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Get upload history for a plant"""
    try:
        # Query recent uploads from time_series table - using correct column structure
        query = text("""
            SELECT 
                t.name as tag_name,
                COUNT(*) as records_count,
                MIN(ts.timestamp) as first_record,
                MAX(ts.timestamp) as last_record,
                ts.frequency
            FROM time_series ts
            JOIN tags t ON ts.tag_id = t.id
            WHERE t.plant_id = :plant_id
            GROUP BY t.name, ts.frequency
            ORDER BY MAX(ts.timestamp) DESC
            LIMIT 50
        """)
        
        result = await db.execute(query, {"plant_id": int(plant_id)})
        
        history = [
            {
                "tag_name": row[0],
                "records_count": row[1],
                "first_record": str(row[2]) if row[2] else None,
                "last_record": str(row[3]) if row[3] else None,
                "frequency": row[4]
            }
            for row in result.fetchall()
        ]
        
        return {"history": history}
    except Exception as e:
        logger.error(f"Error fetching upload history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/{tag_id}")
async def get_metrics(
    tag_id: int, 
    start_time: str, 
    end_time: str, 
    interval: str = "1 hour",
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Leverage TimescaleDB time_bucket for efficient time-series analytics."""
    try:
        # Convert string timestamps to datetime objects and make them timezone-naive
        start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
        end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00')).replace(tzinfo=None)
        
        # Check if TimescaleDB is available
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            );
        """))
        timescaledb_available = result.scalar()
        
        if timescaledb_available:
            # Use TimescaleDB optimized query
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
        else:
            # Fallback to regular PostgreSQL query
            query = text(r"""
                SELECT 
                    DATE_TRUNC(:interval, timestamp) AS bucket,
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
        
        result = await db.execute(
            query, 
            {
                "tag_id": tag_id, 
                "start_time": start_datetime, 
                "end_time": end_datetime,
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
async def get_advanced_metrics(
    tag_id: int, 
    start_time: str, 
    end_time: str, 
    interval: str = "1 hour",
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Advanced TimescaleDB analytics with first/last values and interpolation."""
    try:
        # Convert string timestamps to datetime objects and make them timezone-naive
        start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
        end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00')).replace(tzinfo=None)
        
        # Check if TimescaleDB is available
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            );
        """))
        timescaledb_available = result.scalar()
        
        if timescaledb_available:
            # Use TimescaleDB optimized query
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
        else:
            # Fallback to regular PostgreSQL query (without TimescaleDB-specific functions)
            query = text(r"""
                SELECT 
                    DATE_TRUNC(:interval, timestamp) AS bucket,
                    AVG(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS avg_value,
                    MIN(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS min_value,
                    MAX(CASE WHEN value ~ '^[0-9]+(\.[0-9]+)?$' THEN value::numeric ELSE NULL END) AS max_value,
                    NULL AS first_value,
                    NULL AS last_value,
                    COUNT(*) AS sample_count,
                    NULL AS interpolated_value
                FROM time_series
                WHERE tag_id = :tag_id
                  AND timestamp BETWEEN :start_time AND :end_time
                GROUP BY bucket
                ORDER BY bucket
            """)
        
        result = await db.execute(
            query, 
            {
                "tag_id": tag_id, 
                "start_time": start_datetime, 
                "end_time": end_datetime,
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
async def configure_retention(
    interval: str = "3 months",
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Configure TimescaleDB data retention policies."""
    try:
        # Check if TimescaleDB is available
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            );
        """))
        timescaledb_available = result.scalar()
        
        if not timescaledb_available:
            return {"status": "warning", "message": "TimescaleDB not available. Retention policy not configured."}
        
        # Add a data retention policy
        query = text("""
            SELECT add_retention_policy('time_series', INTERVAL :interval)
        """)
        
        await db.execute(query, {"interval": interval})
        await db.commit()
        
        return {"status": "success", "message": f"Retention policy set to {interval}"}
    except Exception as e:
        logger.error(f"Error configuring retention policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/import-db")
async def import_db(
    db_url: str,
    plant_id: str = Header(..., alias="plant-id")
):
    try:
        data = await import_data_from_db(db_url, plant_id)
        return {"status": "success", "message": "Database imported successfully", "data": data}
    except Exception as e:
        logger.error(f"Error importing database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))