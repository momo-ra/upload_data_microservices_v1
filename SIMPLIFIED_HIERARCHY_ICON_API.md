# Simplified Hierarchy & Icon Management API

This document describes the simplified two-step process for managing hierarchy configuration and icons.

## Overview

The system now works in two simple steps:
1. **Upload hierarchy config file** → Fill the table with all data except the icon column
2. **Upload individual icons** → Update specific rows with the icon path

## Plant-Specific Icon Storage

Icons are stored in **plant-specific directories** to prevent conflicts between different plants:
- **Plant 1**: `/tmp/hierarchy_icons/plant_1/`
- **Plant 2**: `/tmp/hierarchy_icons/plant_2/`
- **Plant N**: `/tmp/hierarchy_icons/plant_N/`

This ensures that each plant has its own isolated icon storage and there are no naming conflicts between plants.

## API Endpoints

### Step 1: Upload Hierarchy Configuration

**Endpoint:** `POST /api/v1/hierarchy/upload`

**Description:** Upload an Excel file to build hierarchy configuration. All records will be created WITHOUT icons (icon column will be NULL).

**Request:**
- **Method:** POST
- **Content-Type:** multipart/form-data
- **Headers:** 
  - `plant-id: <plant_id>`

**Request Body:**
```
file: <Excel file (.xlsx or .xls)>
```

**Excel File Format:**
The Excel file must contain a column named `path` with hierarchy paths in the format:
```
Equipment:Process:Vessel:Mixer
Equipment:Process:Vessel:Tank
Equipment:Safety:Valve
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "records_created": 15,
    "records_deleted": 5,
    "total_paths": 20,
    "valid_paths": 18
  },
  "message": "Successfully processed 20 paths and created 15 hierarchy config records"
}
```

### Step 2: Get Hierarchy Records with IDs

**Endpoint:** `GET /api/v1/hierarchy/config/with-ids`

**Description:** Get all hierarchy configuration records with their database IDs for easy reference.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`

**Response:**
```json
{
  "status": "success",
  "data": {
    "hierarchy_config": [
      {
        "id": 1,
        "label": "Equipment",
        "path": "Equipment",
        "display_order": 0,
        "parent_label": null,
        "display_name": "Equipment",
        "is_active": true,
        "icon": "/tmp/hierarchy_icons/plant_1/equipment_icon_a1b2c3d4.svg",
        "svg_content": "<svg width=\"24\" height=\"24\"...>...</svg>",
        "svg_base64": "PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQi...",
        "created_at": "2024-01-15 10:30:00",
        "updated_at": "2024-01-15 10:30:00"
      },
      {
        "id": 2,
        "label": "Process",
        "path": "Equipment:Process",
        "display_order": 1,
        "parent_label": "Equipment",
        "display_name": "Process",
        "is_active": true,
        "icon": "/tmp/hierarchy_icons/plant_1/process_icon_b2c3d4e5.svg",
        "svg_content": "<svg width=\"24\" height=\"24\"...>...</svg>",
        "svg_base64": "PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQi...",
        "created_at": "2024-01-15 10:30:00",
        "updated_at": "2024-01-15 10:30:00"
      }
    ],
    "total_records": 2
  },
  "message": "Hierarchy configuration with IDs retrieved successfully"
}
```

### Step 3: Upload Individual Icons

**Endpoint:** `POST /api/v1/hierarchy/icons/upload`

**Description:** Upload SVG icon file for hierarchy configuration.

**Request:**
- **Method:** POST
- **Content-Type:** multipart/form-data
- **Headers:** 
  - `plant-id: <plant_id>`

**Request Body:**
```
icon_name: <icon_name>
file: <SVG file (.svg)>
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "icon_name": "mixer_icon",
    "filename": "mixer_icon_a1b2c3d4.svg",
    "file_path": "/tmp/hierarchy_icons/mixer_icon_a1b2c3d4.svg",
    "svg_base64": "PHN2Zz4...",
    "size_bytes": 1024
  },
  "message": "Successfully uploaded SVG icon: mixer_icon"
}
```

### Step 4: Update Hierarchy Row with Icon

**Endpoint:** `PUT /api/v1/hierarchy/config/row/{row_id}/icon`

**Description:** Update the icon for a specific hierarchy configuration record by row ID.

**Request:**
- **Method:** PUT
- **Headers:** 
  - `plant-id: <plant_id>`
  - `Content-Type: application/json`

**Request Body (Option 1 - Using Icon Path):**
```json
{
  "icon_path": "/tmp/hierarchy_icons/plant_1/mixer_icon_a1b2c3d4.svg"
}
```

**Request Body (Option 2 - Using Icon Name):**
```json
{
  "icon_name": "mixer_icon"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "row_id": 2,
    "label": "Mixer",
    "icon_value": "/tmp/hierarchy_icons/plant_1/mixer_icon_a1b2c3d4.svg"
  },
  "message": "Successfully updated icon for hierarchy row 2 (label: Mixer)"
}
```

## Complete Workflow Example

1. **Upload hierarchy config:**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/hierarchy/upload" \
        -H "plant-id: 1" \
        -F "file=@hierarchy_paths.xlsx"
   ```

2. **Get hierarchy records with IDs:**
   ```bash
   curl -X GET "http://localhost:8000/api/v1/hierarchy/config/with-ids" \
        -H "plant-id: 1"
   ```

3. **Upload an icon:**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/hierarchy/icons/upload?icon_name=mixer_icon" \
        -H "plant-id: 1" \
        -F "file=@mixer_icon.svg"
   ```

4. **Update specific row with icon:**
   ```bash
   curl -X PUT "http://localhost:8000/api/v1/hierarchy/config/row/2/icon" \
        -H "plant-id: 1" \
        -H "Content-Type: application/json" \
        -d '{"icon_path": "/tmp/hierarchy_icons/mixer_icon_a1b2c3d4.svg"}'
   ```

## Key Changes Made

1. **Hierarchy upload no longer assigns default icons** - All records are created with `icon: null`
2. **New endpoint for getting records with IDs** - Makes it easy to identify which row to update
3. **New endpoint for updating by row ID** - Simple way to update specific rows with icon paths
4. **Simplified workflow** - Clear separation between hierarchy data and icon management

This approach eliminates the complexity of automatic icon assignment and gives you full control over which icons are assigned to which hierarchy records.
