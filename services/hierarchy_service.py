import pandas as pd
import os
import uuid
import base64
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from queries.hierarchy_queries import (
    get_all_hierarchy_config,
    get_hierarchy_config_by_label,
    get_hierarchy_config_by_label_and_path,
    get_hierarchy_children,
    get_hierarchy_tree,
    bulk_insert_hierarchy_config,
    clear_all_hierarchy_config,
    update_hierarchy_config,
    delete_hierarchy_config_by_label,
    delete_hierarchy_config_by_label_and_path,
    validate_hierarchy_integrity
)
from utils.log import setup_logger
from fastapi import HTTPException
from utils.response import success_response, fail_response

logger = setup_logger(__name__)

class HierarchyService:
    """Service for managing hierarchy configuration"""
    
    def __init__(self, plant_id: str = None):
        # Create plant-specific icons directory
        if plant_id:
            self.icons_dir = f"/tmp/hierarchy_icons/plant_{plant_id}"
        else:
            self.icons_dir = "/tmp/hierarchy_icons"
        os.makedirs(self.icons_dir, exist_ok=True)
    
    async def process_hierarchy_excel(self, file_path: str, plant_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Process Excel file and build HierarchyConfig records"""
        
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=400, detail="File not found")
            
            # Read Excel file
            try:
                df = pd.read_excel(file_path)
            except Exception as e:
                logger.error(f"Error reading Excel file: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")
            
            # Validate required column
            if 'path' not in df.columns:
                raise HTTPException(status_code=400, detail="Excel file must contain a 'path' column")
            
            # Parse hierarchy paths
            hierarchy_records = self.parse_hierarchy_paths(df['path'].tolist())
            
            if not hierarchy_records:
                raise HTTPException(status_code=400, detail="No valid hierarchy paths found in the Excel file")
            
            # Clear existing hierarchy config for this plant
            deleted_count = await clear_all_hierarchy_config(db)
            logger.info(f"Cleared {deleted_count} existing hierarchy records for plant {plant_id}")
            
            # Insert new hierarchy records
            created_count = await bulk_insert_hierarchy_config(db, hierarchy_records)
            
            logger.info(f"Successfully created {created_count} hierarchy config records for plant {plant_id}")
            
            return success_response(
                data={
                    "records_created": created_count,
                    "records_deleted": deleted_count,
                    "total_paths": len(df),
                    "valid_paths": len([p for p in df['path'].tolist() if p and not pd.isna(p)])
                },
                message=f"Successfully processed {len(df)} paths and created {created_count} hierarchy config records"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing hierarchy Excel: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing hierarchy Excel: {str(e)}")

    def parse_hierarchy_paths(self, paths: List[str]) -> List[Dict[str, Any]]:
        """Parse hierarchy paths and create structured records"""
        
        hierarchy_records = []
        seen_combinations = set()  # Track label+path combinations to avoid duplicates
        display_order = 0
        
        logger.info(f"Processing {len(paths)} hierarchy paths")
        
        for path in paths:
            # Skip empty paths
            if not path or pd.isna(path):
                continue
                
            # Clean the path (remove leading/trailing colons and spaces)
            clean_path = str(path).strip().strip(':')
            
            if not clean_path:
                continue
                
            # Split path into components
            components = [comp.strip() for comp in clean_path.split(':') if comp.strip()]
            
            if not components:
                continue
            
            # Build hierarchy for each level
            current_path = ""
            parent_label = None
            
            for i, component in enumerate(components):
                # Build current path
                if current_path:
                    current_path += f":{component}"
                else:
                    current_path = component
                    
                # Create label (use the component as label)
                label = component
                
                # Create unique combination key for label+path
                combination_key = f"{label}:{current_path}"
                
                # Skip if we've already processed this label+path combination
                if combination_key in seen_combinations:
                    parent_label = label
                    continue
                    
                # Create display name (capitalize and format)
                display_name = self._format_display_name(component)
                
                # Create record (without icon - will be set later via separate icon upload)
                record = {
                    'label': label,
                    'path': current_path,
                    'display_order': display_order,
                    'parent_label': parent_label,
                    'display_name': display_name,
                    'icon': None  # No icon assigned during hierarchy upload
                }
                
                hierarchy_records.append(record)
                seen_combinations.add(combination_key)
                display_order += 1
                
                logger.debug(f"Created hierarchy record: {label} -> {current_path} (parent: {parent_label})")
                
                # Set current component as parent for next level
                parent_label = label
        
        logger.info(f"Created {len(hierarchy_records)} unique hierarchy records from {len(paths)} paths")
        return hierarchy_records

    def _format_display_name(self, component: str) -> str:
        """Format component name for display"""
        # Replace underscores and hyphens with spaces
        formatted = component.replace('_', ' ').replace('-', ' ')
        
        # Title case
        formatted = formatted.title()
        
        # Handle common abbreviations
        abbreviations = {
            'Kg': 'KG',
            'Id': 'ID',
            'Db': 'DB',
            'Api': 'API',
            'Ui': 'UI',
            'Url': 'URL',
            'Http': 'HTTP',
            'Https': 'HTTPS',
            'Json': 'JSON',
            'Xml': 'XML',
            'Sql': 'SQL'
        }
        
        for abbrev, correct in abbreviations.items():
            formatted = formatted.replace(abbrev, correct)
        
        return formatted

    def _get_default_icon_for_component(self, component: str) -> str:
        """Get default icon name based on component type"""
        component_lower = component.lower()
        
        # Define icon mappings based on component names
        icon_mappings = {
            'equipment': 'cog',
            'process': 'settings',
            'vessel': 'database',
            'mixer': 'shuffle',
            'splitter': 'split',
            'column': 'bar-chart',
            'pump': 'zap',
            'valve': 'toggle-left',
            'tank': 'droplet',
            'reactor': 'atom',
            'heat': 'thermometer',
            'cool': 'snowflake',
            'filter': 'filter',
            'separator': 'layers',
            'compressor': 'wind',
            'turbine': 'rotate-cw',
            'motor': 'power',
            'sensor': 'activity',
            'control': 'sliders',
            'safety': 'shield',
            'maintenance': 'tool',
            'inspection': 'search',
            'quality': 'check-circle',
            'production': 'play-circle',
            'utility': 'grid',
            'electrical': 'zap',
            'mechanical': 'settings',
            'instrumentation': 'gauge',
            'piping': 'git-branch'
        }
        
        # Check for keyword matches
        for keyword, icon in icon_mappings.items():
            if keyword in component_lower:
                return icon
        
        # Default icon
        return 'file'

    async def upload_svg_icon(self, file_path: str, icon_name: str) -> Dict[str, Any]:
        """Process and validate SVG file upload"""
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=400, detail="SVG file not found")
            
            # Validate SVG content
            svg_validation = self.validate_svg_file(file_path)
            if not svg_validation["is_valid"]:
                raise HTTPException(status_code=400, detail=svg_validation["error"])
            
            # Generate unique filename
            unique_filename = f"{icon_name}_{uuid.uuid4().hex[:8]}.svg"
            destination_path = os.path.join(self.icons_dir, unique_filename)
            
            # Read and process SVG content
            with open(file_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Clean and optimize SVG
            cleaned_svg = self._clean_svg_content(svg_content)
            
            # Save processed SVG
            with open(destination_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_svg)
            
            # Generate base64 encoded version for API responses
            svg_base64 = base64.b64encode(cleaned_svg.encode('utf-8')).decode('utf-8')
            
            logger.info(f"Successfully uploaded SVG icon: {icon_name} -> {unique_filename}")
            
            return success_response(
                data={
                    "icon_name": icon_name,
                    "filename": unique_filename,
                    "file_path": destination_path,
                    "svg_base64": svg_base64,
                    "size_bytes": len(cleaned_svg)
                },
                message=f"Successfully uploaded SVG icon: {icon_name}"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading SVG icon: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error uploading SVG icon: {str(e)}")

    def validate_svg_file(self, file_path: str) -> Dict[str, Any]:
        """Validate SVG file format and content"""
        try:
            if not os.path.exists(file_path):
                return {"is_valid": False, "error": "File not found"}
            
            # Check file extension
            if not file_path.lower().endswith('.svg'):
                return {"is_valid": False, "error": "File must be an SVG file (.svg)"}
            
            # Check file size (limit to 1MB)
            file_size = os.path.getsize(file_path)
            if file_size > 1024 * 1024:  # 1MB
                return {"is_valid": False, "error": "SVG file too large (max 1MB)"}
            
            # Try to parse as XML/SVG
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check if it's valid XML
                ET.fromstring(content)
                
                # Check if it contains SVG root element
                if '<svg' not in content.lower():
                    return {"is_valid": False, "error": "File does not contain valid SVG content"}
                
                # Check for potentially dangerous content
                dangerous_elements = ['script', 'object', 'embed', 'iframe', 'link']
                content_lower = content.lower()
                for element in dangerous_elements:
                    if f'<{element}' in content_lower:
                        return {"is_valid": False, "error": f"SVG contains potentially dangerous element: {element}"}
                
                return {
                    "is_valid": True,
                    "file_size": file_size,
                    "content_length": len(content)
                }
                
            except ET.ParseError as e:
                return {"is_valid": False, "error": f"Invalid XML/SVG format: {str(e)}"}
            except UnicodeDecodeError:
                return {"is_valid": False, "error": "File encoding not supported (use UTF-8)"}
            
        except Exception as e:
            logger.error(f"Error validating SVG file: {str(e)}", exc_info=True)
            return {"is_valid": False, "error": f"Error validating file: {str(e)}"}

    def _clean_svg_content(self, svg_content: str) -> str:
        """Clean and optimize SVG content"""
        try:
            # Parse the SVG
            root = ET.fromstring(svg_content)
            
            # Remove potentially dangerous elements and attributes
            dangerous_elements = ['script', 'object', 'embed', 'iframe', 'link']
            dangerous_attributes = ['onload', 'onclick', 'onmouseover', 'onerror']
            
            # Remove dangerous elements
            for element in root.iter():
                if element.tag.lower() in dangerous_elements:
                    element.clear()
                    continue
                
                # Remove dangerous attributes
                for attr in list(element.attrib.keys()):
                    if any(dangerous_attr in attr.lower() for dangerous_attr in dangerous_attributes):
                        del element.attrib[attr]
            
            # Ensure SVG has proper attributes
            if 'xmlns' not in root.attrib:
                root.set('xmlns', 'http://www.w3.org/2000/svg')
            
            # Convert back to string
            cleaned_svg = ET.tostring(root, encoding='unicode')
            
            # Add XML declaration if missing
            if not cleaned_svg.startswith('<?xml'):
                cleaned_svg = '<?xml version="1.0" encoding="UTF-8"?>\n' + cleaned_svg
            
            return cleaned_svg
            
        except Exception as e:
            logger.warning(f"Error cleaning SVG, returning original content: {str(e)}")
            return svg_content

    async def update_hierarchy_icon(self, label: str, icon_name: str, db: AsyncSession) -> Dict[str, Any]:
        """Update the icon for a specific hierarchy record"""
        try:
            updated = await update_hierarchy_config(db, label, {"icon": icon_name})
            
            if not updated:
                raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label}")
            
            return success_response(
                data={
                    "label": label,
                    "new_icon": icon_name
                },
                message=f"Successfully updated icon for hierarchy label: {label}"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating hierarchy icon for {label}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error updating hierarchy icon: {str(e)}")

    async def update_hierarchy_icon_by_row(self, row_id: int, icon_value: str, db: AsyncSession) -> Dict[str, Any]:
        """Update the icon for a specific hierarchy record by row ID"""
        try:
            # First, get the hierarchy record by ID
            from sqlalchemy import text
            result = await db.execute(
                text("SELECT id, label FROM hierarchy_config WHERE id = :row_id"),
                {"row_id": row_id}
            )
            row = result.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail=f"Hierarchy config not found for row ID: {row_id}")
            
            # Handle both icon_name and icon_path
            final_icon_value = icon_value
            
            # If it's just an icon name (not a full path), find the actual file path
            if not icon_value.startswith('/') and not icon_value.startswith('http'):
                # Look for the icon file in the icons directory
                icon_files = []
                if os.path.exists(self.icons_dir):
                    for filename in os.listdir(self.icons_dir):
                        if filename.endswith('.svg'):
                            # Extract icon name (remove UUID suffix)
                            icon_name = filename.replace('.svg', '')
                            if '_' in icon_name:
                                icon_name = '_'.join(icon_name.split('_')[:-1])
                            
                            if icon_name == icon_value:
                                final_icon_value = os.path.join(self.icons_dir, filename)
                                break
                
                # If no file found, use the icon name as is (for backward compatibility)
                if not final_icon_value.startswith('/'):
                    final_icon_value = icon_value
            
            # Update the icon
            updated = await update_hierarchy_config(db, row[1], {"icon": final_icon_value})
            
            if not updated:
                raise HTTPException(status_code=404, detail=f"Failed to update hierarchy config for row ID: {row_id}")
            
            return success_response(
                data={
                    "row_id": row_id,
                    "label": row[1],
                    "icon_value": final_icon_value
                },
                message=f"Successfully updated icon for hierarchy row {row_id} (label: {row[1]})"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating hierarchy icon for row {row_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error updating hierarchy icon: {str(e)}")

    async def get_available_icons(self) -> Dict[str, Any]:
        """Get list of available SVG icons"""
        try:
            icons = []
            
            if os.path.exists(self.icons_dir):
                for filename in os.listdir(self.icons_dir):
                    if filename.endswith('.svg'):
                        file_path = os.path.join(self.icons_dir, filename)
                        file_size = os.path.getsize(file_path)
                        
                        # Extract icon name (remove UUID suffix)
                        icon_name = filename.replace('.svg', '')
                        if '_' in icon_name:
                            icon_name = '_'.join(icon_name.split('_')[:-1])
                        
                        # Read SVG content and encode as base64
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                svg_content = f.read()
                            svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                        except Exception as e:
                            logger.warning(f"Error reading SVG file {filename}: {str(e)}")
                            svg_base64 = None
                        
                        icons.append({
                            "icon_name": icon_name,
                            "filename": filename,
                            "file_size": file_size,
                            "file_path": file_path,
                            "svg_base64": svg_base64,
                            "svg_content": svg_content if 'svg_content' in locals() else None
                        })
            
            return success_response(
                data={
                    "icons": icons,
                    "total_icons": len(icons)
                },
                message="Available icons retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting available icons: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error getting available icons: {str(e)}")

    async def get_hierarchy_config(self, db: AsyncSession) -> Dict[str, Any]:
        """Get all hierarchy configuration records with icon content"""
        try:
            hierarchy_config = await get_all_hierarchy_config(db)
            
            # Enhance each record with icon content
            enhanced_config = []
            for record in hierarchy_config:
                enhanced_record = record.copy()
                
                # If there's an icon path, load the SVG content
                if record.get('icon') and record['icon'].startswith('/'):
                    try:
                        if os.path.exists(record['icon']):
                            with open(record['icon'], 'r', encoding='utf-8') as f:
                                svg_content = f.read()
                            enhanced_record['svg_content'] = svg_content
                            enhanced_record['svg_base64'] = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                        else:
                            enhanced_record['svg_content'] = None
                            enhanced_record['svg_base64'] = None
                    except Exception as e:
                        logger.warning(f"Error reading icon file {record['icon']}: {str(e)}")
                        enhanced_record['svg_content'] = None
                        enhanced_record['svg_base64'] = None
                else:
                    enhanced_record['svg_content'] = None
                    enhanced_record['svg_base64'] = None
                
                enhanced_config.append(enhanced_record)
            
            return success_response(
                data={
                    "hierarchy_config": enhanced_config,
                    "total_records": len(enhanced_config)
                },
                message="Hierarchy configuration retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error fetching hierarchy config: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error fetching hierarchy config: {str(e)}")

    async def get_hierarchy_tree_structure(self, db: AsyncSession) -> Dict[str, Any]:
        """Get hierarchy in tree structure format"""
        try:
            tree = await get_hierarchy_tree(db)
            
            return success_response(
                data={
                    "tree": tree,
                    "total_nodes": len(tree)
                },
                message="Hierarchy tree structure retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error fetching hierarchy tree: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error fetching hierarchy tree: {str(e)}")

    async def get_hierarchy_by_label(self, label: str, db: AsyncSession) -> Dict[str, Any]:
        """Get all hierarchy configurations by label"""
        try:
            configs = await get_hierarchy_config_by_label(db, label)
            
            if not configs:
                raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label}")
            
            return success_response(
                data={
                    "configs": configs,
                    "total_configs": len(configs)
                },
                message=f"Retrieved {len(configs)} hierarchy configurations for label: {label}"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching hierarchy config by label {label}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error fetching hierarchy config: {str(e)}")

    async def get_hierarchy_by_label_and_path(self, label: str, path: str, db: AsyncSession) -> Dict[str, Any]:
        """Get specific hierarchy configuration by label and path"""
        try:
            config = await get_hierarchy_config_by_label_and_path(db, label, path)
            
            if not config:
                raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label} and path: {path}")
            
            return success_response(
                data=config,
                message="Hierarchy configuration retrieved successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching hierarchy config by label {label} and path {path}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error fetching hierarchy config: {str(e)}")

    async def get_hierarchy_children(self, parent_label: str, db: AsyncSession) -> Dict[str, Any]:
        """Get children of a specific parent label"""
        try:
            children = await get_hierarchy_children(db, parent_label)
            
            return success_response(
                data={
                    "children": children,
                    "total_children": len(children)
                },
                message="Hierarchy children retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error fetching hierarchy children for {parent_label}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error fetching hierarchy children: {str(e)}")

    async def update_hierarchy_record(self, label: str, updates: Dict[str, Any], db: AsyncSession, path: str = None) -> Dict[str, Any]:
        """Update a specific hierarchy configuration record by label or label+path"""
        try:
            # Validate updates
            allowed_fields = ["display_name", "display_order", "is_active", "parent_label", "icon"]
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            if not filtered_updates:
                raise HTTPException(status_code=400, detail="No valid fields to update")
            
            updated = await update_hierarchy_config(db, label, filtered_updates, path)
            
            if not updated:
                if path:
                    raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label} and path: {path}")
                else:
                    raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label}")
            
            return success_response(
                data={
                    "updated_fields": list(filtered_updates.keys()),
                    "label": label,
                    "path": path
                },
                message=f"Successfully updated hierarchy config for label: {label}" + (f" and path: {path}" if path else "")
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating hierarchy config for {label}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error updating hierarchy config: {str(e)}")

    async def delete_hierarchy_record(self, label: str, db: AsyncSession, path: str = None) -> Dict[str, Any]:
        """Delete hierarchy configuration record(s) by label or label+path"""
        try:
            if path:
                deleted = await delete_hierarchy_config_by_label_and_path(db, label, path)
                if not deleted:
                    raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label} and path: {path}")
                message = f"Successfully deleted hierarchy config for label: {label} and path: {path}"
            else:
                deleted = await delete_hierarchy_config_by_label(db, label)
                if not deleted:
                    raise HTTPException(status_code=404, detail=f"Hierarchy config not found for label: {label}")
                message = f"Successfully deleted hierarchy config for label: {label}"
            
            return success_response(
                message=message
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting hierarchy config for {label}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error deleting hierarchy config: {str(e)}")

    async def clear_all_hierarchy(self, plant_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Clear all hierarchy configuration records"""
        try:
            deleted_count = await clear_all_hierarchy_config(db)
            
            logger.info(f"Successfully deleted {deleted_count} hierarchy config records for plant {plant_id}")
            
            return success_response(
                data={
                    "deleted_count": deleted_count
                },
                message=f"Successfully deleted {deleted_count} hierarchy config records"
            )
            
        except Exception as e:
            logger.error(f"Error clearing hierarchy config: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error clearing hierarchy config: {str(e)}")

    async def validate_hierarchy(self, db: AsyncSession) -> Dict[str, Any]:
        """Validate the integrity of the hierarchy structure"""
        try:
            validation_result = await validate_hierarchy_integrity(db)
            
            return success_response(
                data=validation_result,
                message="Hierarchy validation completed successfully"
            )
            
        except Exception as e:
            logger.error(f"Error validating hierarchy: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error validating hierarchy: {str(e)}")

    def validate_excel_file(self, file_path: str) -> Dict[str, Any]:
        """Validate Excel file format and content"""
        try:
            if not os.path.exists(file_path):
                return {"is_valid": False, "error": "File not found"}
            
            # Check file extension
            if not file_path.lower().endswith(('.xlsx', '.xls')):
                return {"is_valid": False, "error": "File must be an Excel file (.xlsx or .xls)"}
            
            # Try to read the file
            try:
                df = pd.read_excel(file_path)
            except Exception as e:
                return {"is_valid": False, "error": f"Error reading Excel file: {str(e)}"}
            
            # Check for required column
            if 'path' not in df.columns:
                return {"is_valid": False, "error": "Excel file must contain a 'path' column"}
            
            # Check for empty data
            if df.empty:
                return {"is_valid": False, "error": "Excel file is empty"}
            
            # Count valid paths
            valid_paths = [p for p in df['path'].tolist() if p and not pd.isna(p)]
            
            if not valid_paths:
                return {"is_valid": False, "error": "No valid paths found in the Excel file"}
            
            return {
                "is_valid": True,
                "total_rows": len(df),
                "valid_paths": len(valid_paths),
                "invalid_paths": len(df) - len(valid_paths),
                "columns": df.columns.tolist()
            }
            
        except Exception as e:
            logger.error(f"Error validating Excel file: {str(e)}", exc_info=True)
            return {"is_valid": False, "error": f"Error validating file: {str(e)}"}
