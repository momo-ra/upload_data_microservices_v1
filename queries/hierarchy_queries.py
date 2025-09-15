from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from models.plant_models import HierarchyConfig
from utils.log import setup_logger
from typing import List, Dict, Any, Optional

logger = setup_logger(__name__)

async def get_all_hierarchy_config(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get all active hierarchy configuration records"""
    try:
        query = text("""
            SELECT id, label, path, display_order, parent_label, display_name, is_active, icon, created_at, updated_at
            FROM hierarchy_config
            WHERE is_active = true
            ORDER BY display_order, path
        """)
        
        result = await db.execute(query)
        records = result.fetchall()
        
        return [
            {
                "id": row[0],
                "label": row[1],
                "path": row[2],
                "display_order": row[3],
                "parent_label": row[4],
                "display_name": row[5],
                "is_active": row[6],
                "icon": row[7],
                "created_at": str(row[8]) if row[8] else None,
                "updated_at": str(row[9]) if row[9] else None
            }
            for row in records
        ]
        
    except Exception as e:
        logger.error(f"Error fetching hierarchy config: {str(e)}", exc_info=True)
        raise e

async def get_hierarchy_config_by_label(db: AsyncSession, label: str) -> List[Dict[str, Any]]:
    """Get all hierarchy configuration records by label"""
    try:
        query = text("""
            SELECT id, label, path, display_order, parent_label, display_name, is_active, icon, created_at, updated_at
            FROM hierarchy_config
            WHERE label = :label AND is_active = true
            ORDER BY path
        """)
        
        result = await db.execute(query, {"label": label})
        records = result.fetchall()
        
        return [
            {
                "id": row[0],
                "label": row[1],
                "path": row[2],
                "display_order": row[3],
                "parent_label": row[4],
                "display_name": row[5],
                "is_active": row[6],
                "icon": row[7],
                "created_at": str(row[8]) if row[8] else None,
                "updated_at": str(row[9]) if row[9] else None
            }
            for row in records
        ]
        
    except Exception as e:
        logger.error(f"Error fetching hierarchy config by label {label}: {str(e)}", exc_info=True)
        raise e

async def get_hierarchy_config_by_label_and_path(db: AsyncSession, label: str, path: str) -> Optional[Dict[str, Any]]:
    """Get hierarchy configuration by label and path combination"""
    try:
        query = text("""
            SELECT id, label, path, display_order, parent_label, display_name, is_active, icon, created_at, updated_at
            FROM hierarchy_config
            WHERE label = :label AND path = :path AND is_active = true
        """)
        
        result = await db.execute(query, {"label": label, "path": path})
        row = result.fetchone()
        
        if not row:
            return None
            
        return {
            "id": row[0],
            "label": row[1],
            "path": row[2],
            "display_order": row[3],
            "parent_label": row[4],
            "display_name": row[5],
            "is_active": row[6],
            "icon": row[7],
            "created_at": str(row[8]) if row[8] else None,
            "updated_at": str(row[9]) if row[9] else None
        }
        
    except Exception as e:
        logger.error(f"Error fetching hierarchy config by label {label} and path {path}: {str(e)}", exc_info=True)
        raise e

async def get_hierarchy_children(db: AsyncSession, parent_label: str) -> List[Dict[str, Any]]:
    """Get all children of a specific parent label"""
    try:
        query = text("""
            SELECT id, label, path, display_order, parent_label, display_name, is_active, icon, created_at, updated_at
            FROM hierarchy_config
            WHERE parent_label = :parent_label AND is_active = true
            ORDER BY display_order, label
        """)
        
        result = await db.execute(query, {"parent_label": parent_label})
        records = result.fetchall()
        
        return [
            {
                "id": row[0],
                "label": row[1],
                "path": row[2],
                "display_order": row[3],
                "parent_label": row[4],
                "display_name": row[5],
                "is_active": row[6],
                "icon": row[7],
                "created_at": str(row[8]) if row[8] else None,
                "updated_at": str(row[9]) if row[9] else None
            }
            for row in records
        ]
        
    except Exception as e:
        logger.error(f"Error fetching hierarchy children for parent {parent_label}: {str(e)}", exc_info=True)
        raise e

async def get_hierarchy_tree(db: AsyncSession) -> Dict[str, Any]:
    """Get the complete hierarchy tree structure"""
    try:
        # Get all records
        all_records = await get_all_hierarchy_config(db)
        
        # Build tree structure
        tree = {}
        nodes = {record["label"]: record for record in all_records}
        
        for record in all_records:
            if record["parent_label"] is None:
                # Root node
                tree[record["label"]] = {**record, "children": []}
            else:
                # Add to parent's children
                parent = nodes.get(record["parent_label"])
                if parent:
                    if "children" not in tree.get(parent["label"], {}):
                        tree[parent["label"]] = {**parent, "children": []}
                    tree[parent["label"]]["children"].append(record)
        
        return tree
        
    except Exception as e:
        logger.error(f"Error building hierarchy tree: {str(e)}", exc_info=True)
        raise e

async def bulk_insert_hierarchy_config(db: AsyncSession, hierarchy_records: List[Dict[str, Any]]) -> int:
    """Bulk insert hierarchy configuration records"""
    try:
        created_count = 0
        
        for record in hierarchy_records:
            hierarchy_config = HierarchyConfig(
                label=record['label'],
                path=record['path'],
                display_order=record['display_order'],
                parent_label=record['parent_label'],
                display_name=record['display_name'],
                icon=record.get('icon', 'file'),
                is_active=True
            )
            db.add(hierarchy_config)
            created_count += 1
        
        await db.commit()
        logger.info(f"Successfully inserted {created_count} hierarchy config records")
        return created_count
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error bulk inserting hierarchy config: {str(e)}", exc_info=True)
        raise e

async def clear_all_hierarchy_config(db: AsyncSession) -> int:
    """Clear all hierarchy configuration records"""
    try:
        # Get count before deletion
        count_query = text("SELECT COUNT(*) FROM hierarchy_config")
        count_result = await db.execute(count_query)
        deleted_count = count_result.scalar()
        
        # Delete all records
        await db.execute(text("DELETE FROM hierarchy_config"))
        await db.commit()
        
        logger.info(f"Successfully deleted {deleted_count} hierarchy config records")
        return deleted_count
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error clearing hierarchy config: {str(e)}", exc_info=True)
        raise e

async def update_hierarchy_config(db: AsyncSession, label: str, updates: Dict[str, Any], path: str = None) -> bool:
    """Update a specific hierarchy configuration record by label or label+path"""
    try:
        # Build dynamic update query
        set_clauses = []
        params = {"label": label}
        
        for key, value in updates.items():
            if key in ["display_name", "display_order", "is_active", "parent_label", "icon"]:
                set_clauses.append(f"{key} = :{key}")
                params[key] = value
        
        if not set_clauses:
            return False
        
        # Build WHERE clause
        where_clause = "WHERE label = :label"
        if path:
            where_clause += " AND path = :path"
            params["path"] = path
            
        query = text(f"""
            UPDATE hierarchy_config 
            SET {', '.join(set_clauses)}, updated_at = NOW()
            {where_clause}
        """)
        
        result = await db.execute(query, params)
        await db.commit()
        
        updated = result.rowcount > 0
        if updated:
            if path:
                logger.info(f"Successfully updated hierarchy config for label {label} and path {path}")
            else:
                logger.info(f"Successfully updated hierarchy config for label {label}")
        else:
            if path:
                logger.warning(f"No hierarchy config found for label {label} and path {path}")
            else:
                logger.warning(f"No hierarchy config found for label {label}")
            
        return updated
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating hierarchy config for label {label}: {str(e)}", exc_info=True)
        raise e

async def delete_hierarchy_config_by_label(db: AsyncSession, label: str) -> bool:
    """Delete all hierarchy configuration records for a specific label"""
    try:
        # Get all records with this label
        records = await get_hierarchy_config_by_label(db, label)
        
        if not records:
            logger.warning(f"No hierarchy config found for label {label}")
            return False
        
        # Delete all records with this label
        result = await db.execute(
            text("DELETE FROM hierarchy_config WHERE label = :label"),
            {"label": label}
        )
        
        await db.commit()
        
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(f"Successfully deleted {result.rowcount} hierarchy config records for label {label}")
        else:
            logger.warning(f"No hierarchy config found for label {label}")
            
        return deleted
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting hierarchy config for label {label}: {str(e)}", exc_info=True)
        raise e

async def delete_hierarchy_config_by_label_and_path(db: AsyncSession, label: str, path: str) -> bool:
    """Delete a specific hierarchy configuration record by label and path"""
    try:
        result = await db.execute(
            text("DELETE FROM hierarchy_config WHERE label = :label AND path = :path"),
            {"label": label, "path": path}
        )
        
        await db.commit()
        
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(f"Successfully deleted hierarchy config for label {label} and path {path}")
        else:
            logger.warning(f"No hierarchy config found for label {label} and path {path}")
            
        return deleted
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting hierarchy config for label {label} and path {path}: {str(e)}", exc_info=True)
        raise e

async def _get_all_children_recursive(db: AsyncSession, parent_label: str) -> List[str]:
    """Recursively get all children labels of a parent"""
    children = []
    
    # Get direct children
    direct_children = await get_hierarchy_children(db, parent_label)
    
    for child in direct_children:
        child_label = child["label"]
        children.append(child_label)
        
        # Recursively get children of this child
        grandchildren = await _get_all_children_recursive(db, child_label)
        children.extend(grandchildren)
    
    return children

async def validate_hierarchy_integrity(db: AsyncSession) -> Dict[str, Any]:
    """Validate the integrity of the hierarchy structure"""
    try:
        issues = []
        
        # Check for orphaned records (parent_label points to non-existent label)
        orphan_query = text("""
            SELECT h1.label, h1.parent_label
            FROM hierarchy_config h1
            LEFT JOIN hierarchy_config h2 ON h1.parent_label = h2.label
            WHERE h1.parent_label IS NOT NULL AND h2.label IS NULL
        """)
        
        result = await db.execute(orphan_query)
        orphans = result.fetchall()
        
        if orphans:
            issues.append({
                "type": "orphaned_records",
                "description": "Records with parent_label pointing to non-existent labels",
                "records": [{"label": row[0], "parent_label": row[1]} for row in orphans]
            })
        
        # Check for circular references
        all_records = await get_all_hierarchy_config(db)
        for record in all_records:
            if await _has_circular_reference(db, record["label"], record["parent_label"]):
                issues.append({
                    "type": "circular_reference",
                    "description": f"Circular reference detected for label {record['label']}",
                    "record": record
                })
        
        # Check for duplicate paths
        duplicate_query = text("""
            SELECT path, COUNT(*) as count
            FROM hierarchy_config
            GROUP BY path
            HAVING COUNT(*) > 1
        """)
        
        result = await db.execute(duplicate_query)
        duplicates = result.fetchall()
        
        if duplicates:
            issues.append({
                "type": "duplicate_paths",
                "description": "Multiple records with the same path",
                "paths": [{"path": row[0], "count": row[1]} for row in duplicates]
            })
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "total_records": len(all_records)
        }
        
    except Exception as e:
        logger.error(f"Error validating hierarchy integrity: {str(e)}", exc_info=True)
        raise e

async def _has_circular_reference(db: AsyncSession, label: str, parent_label: str, visited: set = None) -> bool:
    """Check if there's a circular reference in the hierarchy"""
    if visited is None:
        visited = set()
    
    if parent_label is None:
        return False
    
    if parent_label == label:
        return True
    
    if parent_label in visited:
        return True
    
    visited.add(parent_label)
    
    # Get the parent of the parent
    parent_record = await get_hierarchy_config_by_label(db, parent_label)
    if parent_record:
        return await _has_circular_reference(db, label, parent_record["parent_label"], visited)
    
    return False
