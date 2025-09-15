# Hierarchy Configuration API

This document describes the hierarchy configuration API that follows the project's architectural patterns with proper separation of concerns using services and queries layers.

## Architecture Overview

The hierarchy system follows the established project structure:

```
├── routers/endpoints.py          # API endpoints (controllers)
├── services/hierarchy_service.py # Business logic layer
├── queries/hierarchy_queries.py  # Database operations layer
└── models/plant_models.py        # HierarchyConfig model
```

### Key Components

- **HierarchyService**: Handles business logic, validation, and Excel processing
- **hierarchy_queries**: Database operations and SQL queries
- **endpoints**: FastAPI route handlers that delegate to services
- **HierarchyConfig Model**: SQLAlchemy model for database schema

## API Endpoints

### 1. Upload Hierarchy Configuration

**POST** `/hierarchy/upload`

Upload an Excel file to build HierarchyConfig records from hierarchical paths.

#### Headers
- `plant-id`: Plant identifier (required)

#### Request Body
- `file`: Excel file (.xlsx or .xls) with `path` column

#### Excel Format
```
path
:Equipment
:Equipment:Process
:Equipment:Process:Vessel
:Equipment:Process:Vessel:Mixer
```

#### Response
```json
{
  "status": "success",
  "message": "Successfully processed 67 paths and created 45 hierarchy config records",
  "records_created": 45,
  "records_deleted": 12,
  "total_paths": 67,
  "valid_paths": 65
}
```

### 2. Get All Hierarchy Configuration

**GET** `/hierarchy/config`

Retrieve all active hierarchy configuration records.

#### Response
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "label": "Equipment",
      "path": "Equipment",
      "display_order": 0,
      "parent_label": null,
      "display_name": "Equipment",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total_records": 45
}
```

### 3. Get Hierarchy Tree Structure

**GET** `/hierarchy/tree`

Get hierarchy in nested tree format for UI components.

#### Response
```json
{
  "status": "success",
  "data": {
    "Equipment": {
      "id": 1,
      "label": "Equipment",
      "path": "Equipment",
      "children": [
        {
          "id": 2,
          "label": "Process",
          "path": "Equipment:Process",
          "children": [...]
        }
      ]
    }
  },
  "total_nodes": 5
}
```

### 4. Get Hierarchy by Label

**GET** `/hierarchy/config/{label}`

Get specific hierarchy configuration by label.

#### Response
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "label": "Equipment",
    "path": "Equipment",
    "display_order": 0,
    "parent_label": null,
    "display_name": "Equipment",
    "is_active": true
  }
}
```

### 5. Get Hierarchy Children

**GET** `/hierarchy/children/{parent_label}`

Get all direct children of a specific parent label.

#### Response
```json
{
  "status": "success",
  "data": [
    {
      "id": 2,
      "label": "Process",
      "parent_label": "Equipment"
    }
  ],
  "total_children": 3
}
```

### 6. Update Hierarchy Configuration

**PUT** `/hierarchy/config/{label}`

Update a specific hierarchy configuration record.

#### Request Body
```json
{
  "display_name": "Updated Equipment Name",
  "display_order": 5,
  "is_active": false
}
```

#### Response
```json
{
  "status": "success",
  "message": "Successfully updated hierarchy config for label: Equipment",
  "updated_fields": ["display_name", "display_order"]
}
```

### 7. Delete Hierarchy Configuration

**DELETE** `/hierarchy/config/{label}`

Delete a specific hierarchy configuration record and all its children.

#### Response
```json
{
  "status": "success",
  "message": "Successfully deleted hierarchy config for label: Equipment"
}
```

### 8. Clear All Hierarchy Configuration

**DELETE** `/hierarchy/config`

Remove all hierarchy configuration records for the plant.

#### Response
```json
{
  "status": "success",
  "message": "Successfully deleted 45 hierarchy config records",
  "deleted_count": 45
}
```

### 9. Validate Hierarchy Integrity

**GET** `/hierarchy/validate`

Validate the integrity of the hierarchy structure.

#### Response
```json
{
  "status": "success",
  "validation": {
    "is_valid": true,
    "issues": [],
    "total_records": 45
  }
}
```

## Service Layer Details

### HierarchyService Methods

```python
# Main processing method
async def process_hierarchy_excel(file_path: str, plant_id: str, db: AsyncSession)

# Path parsing with validation
def parse_hierarchy_paths(paths: List[str]) -> List[Dict[str, Any]]

# CRUD operations
async def get_hierarchy_config(db: AsyncSession)
async def get_hierarchy_tree_structure(db: AsyncSession)
async def update_hierarchy_record(label: str, updates: Dict, db: AsyncSession)
async def delete_hierarchy_record(label: str, db: AsyncSession)

# Validation methods
async def validate_hierarchy(db: AsyncSession)
def validate_excel_file(file_path: str) -> Dict[str, Any]
```

### Query Layer Methods

```python
# Basic CRUD operations
async def get_all_hierarchy_config(db: AsyncSession)
async def get_hierarchy_config_by_label(db: AsyncSession, label: str)
async def bulk_insert_hierarchy_config(db: AsyncSession, records: List[Dict])

# Tree operations
async def get_hierarchy_children(db: AsyncSession, parent_label: str)
async def get_hierarchy_tree(db: AsyncSession)

# Maintenance operations
async def clear_all_hierarchy_config(db: AsyncSession)
async def validate_hierarchy_integrity(db: AsyncSession)
```

## Processing Logic

### Excel File Processing

1. **File Validation**: Checks file format and required columns
2. **Path Parsing**: Splits colon-separated paths into hierarchy levels
3. **Relationship Building**: Establishes parent-child relationships
4. **Duplicate Prevention**: Ensures unique labels across the hierarchy
5. **Display Formatting**: Creates user-friendly display names

### Path Processing Example

Input: `:Equipment:Process:Vessel:Mixer`

Processing:
1. Clean path: `Equipment:Process:Vessel:Mixer`
2. Split components: `["Equipment", "Process", "Vessel", "Mixer"]`
3. Create records:
   - `Equipment` (parent: null, path: `Equipment`)
   - `Process` (parent: `Equipment`, path: `Equipment:Process`)
   - `Vessel` (parent: `Process`, path: `Equipment:Process:Vessel`)
   - `Mixer` (parent: `Vessel`, path: `Equipment:Process:Vessel:Mixer`)

## Usage Examples

### Python Client Example

```python
import requests
import json

base_url = "http://localhost:8000"
headers = {"plant-id": "1"}

# Upload hierarchy file
with open('hierarchy.xlsx', 'rb') as f:
    response = requests.post(
        f"{base_url}/hierarchy/upload",
        headers=headers,
        files={'file': f}
    )
    print(response.json())

# Get hierarchy tree
response = requests.get(f"{base_url}/hierarchy/tree", headers=headers)
tree_data = response.json()

# Update a hierarchy record
update_data = {"display_name": "New Equipment Name"}
response = requests.put(
    f"{base_url}/hierarchy/config/Equipment",
    headers={**headers, "Content-Type": "application/json"},
    json=update_data
)
```

### cURL Examples

```bash
# Upload hierarchy file
curl -X POST "http://localhost:8000/hierarchy/upload" \
  -H "plant-id: 1" \
  -F "file=@hierarchy.xlsx"

# Get all hierarchy config
curl -X GET "http://localhost:8000/hierarchy/config" \
  -H "plant-id: 1"

# Get hierarchy tree
curl -X GET "http://localhost:8000/hierarchy/tree" \
  -H "plant-id: 1"

# Validate hierarchy
curl -X GET "http://localhost:8000/hierarchy/validate" \
  -H "plant-id: 1"
```

## Error Handling

### Common Error Responses

**File Validation Errors:**
```json
{
  "detail": "File must be an Excel file (.xlsx or .xls)"
}
```

**Data Validation Errors:**
```json
{
  "detail": "Excel file must contain a 'path' column"
}
```

**Not Found Errors:**
```json
{
  "detail": "Hierarchy config not found for label: NonExistentLabel"
}
```

**Validation Errors:**
```json
{
  "detail": "No valid fields to update"
}
```

## Database Schema

```sql
CREATE TABLE hierarchy_config (
    id SERIAL PRIMARY KEY,
    label VARCHAR UNIQUE NOT NULL,
    path VARCHAR NOT NULL,
    display_order INTEGER DEFAULT 0,
    parent_label VARCHAR REFERENCES hierarchy_config(label),
    display_name VARCHAR,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Best Practices

### Development
- Follow the service-query pattern for new features
- Use dependency injection for database sessions
- Implement proper error handling and logging
- Write comprehensive tests for business logic

### Data Management
- Validate Excel files before processing
- Use transactions for bulk operations
- Implement proper backup strategies
- Monitor hierarchy integrity regularly

### Performance
- Use bulk operations for large datasets
- Implement proper indexing on frequently queried columns
- Cache frequently accessed hierarchy trees
- Monitor query performance and optimize as needed

## Integration Notes

- **Plant-Specific**: All operations are scoped to specific plants using `plant-id` header
- **Database Agnostic**: Uses SQLAlchemy for database operations
- **Async Support**: Full async/await support throughout the stack
- **Error Propagation**: Proper error handling from database to API level
- **Logging**: Comprehensive logging at all levels for debugging and monitoring
