# upload_service/api/endpoints.py
from fastapi import APIRouter, UploadFile, File, Header, Depends, HTTPException
from services.data_import import DataImportService
from services.hierarchy_service import HierarchyService
import shutil
import os
import base64
from typing import Optional, AsyncGenerator
from database import get_central_db, get_plant_db_with_context, get_plant_context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils.log import setup_logger
from services.db_import_services import import_data_from_db
from datetime import datetime
from utils.response import success_response, fail_response

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
        
        # If the result is already standardized, return it directly
        if isinstance(result, dict) and 'status' in result:
            return result
        
        # Otherwise, wrap it in success response
        return success_response(data=result, message="File processed successfully")
    finally:
        # مسح الملف المؤقت
        os.remove(file_path)

@router.get("/status/{job_id}")
async def get_status(
    job_id: str,
    plant_id: str = Header(..., alias="plant-id")
):
    try:
        service = DataImportService()
        status = await service.get_processing_status(job_id, plant_id)
        
        # If the status is already standardized, return it directly
        if isinstance(status, dict) and 'status' in status:
            return status
        
        # Otherwise, wrap it in success response
        return success_response(data=status, message="Job status retrieved successfully")
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        return fail_response(message=str(e))

@router.post("/decide/{job_id}")
async def make_decision(
    job_id: str, 
    decision: str, 
    frequency: Optional[str] = None,
    plant_id: str = Header(..., alias="plant-id")
):
    try:
        service = DataImportService()
        result = await service.handle_duplicates(job_id, decision, frequency, plant_id)
        
        # If the result is already standardized, return it directly
        if isinstance(result, dict) and 'status' in result:
            return result
        
        # Otherwise, wrap it in success response
        return success_response(data=result, message="Duplicate decision processed successfully")
    except Exception as e:
        logger.error(f"Error handling duplicates: {str(e)}")
        return fail_response(message=str(e))

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
        
        return success_response(data={"history": history}, message="Upload history retrieved successfully")
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
        
        return success_response(data={"metrics": metrics}, message="Metrics retrieved successfully")
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
        
        return success_response(data={"metrics": metrics}, message="Advanced metrics retrieved successfully")
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
            return fail_response(message="TimescaleDB not available. Retention policy not configured.")
        
        # Add a data retention policy
        query = text("""
            SELECT add_retention_policy('time_series', INTERVAL :interval)
        """)
        
        await db.execute(query, {"interval": interval})
        await db.commit()
        
        return success_response(message=f"Retention policy set to {interval}")
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
        return success_response(data=data, message="Database imported successfully")
    except Exception as e:
        logger.error(f"Error importing database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hierarchy/upload")
async def upload_hierarchy_config(
    file: UploadFile = File(...),
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Upload Excel file to build HierarchyConfig based on hierarchy paths"""
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Save file temporarily
    file_path = f"/tmp/{file.filename}"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Use hierarchy service to process the file
        hierarchy_service = HierarchyService(plant_id)
        result = await hierarchy_service.process_hierarchy_excel(file_path, plant_id, db)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing hierarchy file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

@router.get("/hierarchy/config")
async def get_hierarchy_config(
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Get all hierarchy configuration records"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.get_hierarchy_config(db)

@router.get("/hierarchy/config/with-ids")
async def get_hierarchy_config_with_ids(
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Get all hierarchy configuration records with their database IDs and icon content"""
    try:
        from sqlalchemy import text
        result = await db.execute(text("""
            SELECT id, label, path, display_order, parent_label, display_name, is_active, icon
            FROM hierarchy_config 
            ORDER BY display_order, label
        """))
        
        records = []
        for row in result.fetchall():
            record = {
                "id": row[0],
                "label": row[1],
                "path": row[2],
                "display_order": row[3],
                "parent_label": row[4],
                "display_name": row[5],
                "is_active": row[6],
                "icon": row[7]
            }
            
            # Add icon content if icon path exists
            if record['icon'] and record['icon'].startswith('/'):
                try:
                    if os.path.exists(record['icon']):
                        with open(record['icon'], 'r', encoding='utf-8') as f:
                            svg_content = f.read()
                        record['svg_content'] = svg_content
                        record['svg_base64'] = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                    else:
                        record['svg_content'] = None
                        record['svg_base64'] = None
                except Exception as e:
                    logger.warning(f"Error reading icon file {record['icon']}: {str(e)}")
                    record['svg_content'] = None
                    record['svg_base64'] = None
            else:
                record['svg_content'] = None
                record['svg_base64'] = None
            
            records.append(record)
        
        return success_response(
            data={
                "hierarchy_config": records,
                "total_records": len(records)
            },
            message="Hierarchy configuration with IDs retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error fetching hierarchy config with IDs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching hierarchy config: {str(e)}")

@router.get("/hierarchy/tree")
async def get_hierarchy_tree(
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Get hierarchy configuration in tree structure"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.get_hierarchy_tree_structure(db)

@router.get("/hierarchy/config/{label}")
async def get_hierarchy_by_label(
    label: str,
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Get specific hierarchy configuration by label"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.get_hierarchy_by_label(label, db)

@router.get("/hierarchy/children/{parent_label}")
async def get_hierarchy_children(
    parent_label: str,
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Get children of a specific parent label"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.get_hierarchy_children(parent_label, db)

@router.put("/hierarchy/config/{label}")
async def update_hierarchy_config(
    label: str,
    updates: dict,
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Update a specific hierarchy configuration record"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.update_hierarchy_record(label, updates, db)

@router.delete("/hierarchy/config/{label}")
async def delete_hierarchy_config(
    label: str,
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Delete a specific hierarchy configuration record"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.delete_hierarchy_record(label, db)

@router.delete("/hierarchy/config")
async def clear_hierarchy_config(
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Clear all hierarchy configuration records"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.clear_all_hierarchy(plant_id, db)

@router.get("/hierarchy/validate")
async def validate_hierarchy_integrity(
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Validate the integrity of the hierarchy structure"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.validate_hierarchy(db)

@router.post("/hierarchy/icons/upload")
async def upload_svg_icon(
    icon_name: str,
    file: UploadFile = File(...),
    plant_id: str = Header(..., alias="plant-id")
):
    """Upload SVG icon file for hierarchy configuration"""
    
    # Validate file type
    if not file.filename.endswith('.svg'):
        raise HTTPException(status_code=400, detail="File must be an SVG file (.svg)")
    
    # Validate icon name
    if not icon_name or len(icon_name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Icon name is required")
    
    # Clean icon name (remove special characters)
    clean_icon_name = "".join(c for c in icon_name if c.isalnum() or c in ('-', '_')).strip()
    if not clean_icon_name:
        raise HTTPException(status_code=400, detail="Icon name must contain alphanumeric characters")
    
    # Save file temporarily
    file_path = f"/tmp/{file.filename}"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Use hierarchy service to process the SVG
        hierarchy_service = HierarchyService(plant_id)
        result = await hierarchy_service.upload_svg_icon(file_path, clean_icon_name)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing SVG icon: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

@router.get("/hierarchy/icons")
async def get_available_icons(
    plant_id: str = Header(..., alias="plant-id")
):
    """Get list of available SVG icons"""
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.get_available_icons()

@router.put("/hierarchy/config/{label}/icon")
async def update_hierarchy_icon(
    label: str,
    icon_data: dict,
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Update the icon for a specific hierarchy configuration record"""
    
    if "icon" not in icon_data:
        raise HTTPException(status_code=400, detail="Icon name is required in request body")
    
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.update_hierarchy_icon(label, icon_data["icon"], db)

@router.put("/hierarchy/config/row/{row_id}/icon")
async def update_hierarchy_icon_by_row(
    row_id: int,
    icon_data: dict,
    plant_id: str = Header(..., alias="plant-id"),
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    """Update the icon for a specific hierarchy configuration record by row ID"""
    
    # Accept either icon_path or icon_name
    if "icon_path" in icon_data:
        icon_value = icon_data["icon_path"]
    elif "icon_name" in icon_data:
        icon_value = icon_data["icon_name"]
    else:
        raise HTTPException(status_code=400, detail="Either icon_path or icon_name is required in request body")
    
    hierarchy_service = HierarchyService(plant_id)
    return await hierarchy_service.update_hierarchy_icon_by_row(row_id, icon_value, db)

@router.get("/hierarchy/icons/{icon_name}")
async def get_svg_icon(
    icon_name: str,
    plant_id: str = Header(..., alias="plant-id")
):
    """Get SVG icon content by name"""
    
    hierarchy_service = HierarchyService(plant_id)
    icons_response = await hierarchy_service.get_available_icons()
    
    # Find the icon
    icon_found = None
    for icon in icons_response["data"]:
        if icon["icon_name"] == icon_name:
            icon_found = icon
            break
    
    if not icon_found:
        raise HTTPException(status_code=404, detail=f"Icon not found: {icon_name}")
    
    try:
        # Read SVG content
        with open(icon_found["file_path"], 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        # Return SVG content with proper headers
        from fastapi.responses import Response
        return Response(
            content=svg_content,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Disposition": f"inline; filename={icon_found['filename']}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error reading SVG icon {icon_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error reading SVG icon: {str(e)}")