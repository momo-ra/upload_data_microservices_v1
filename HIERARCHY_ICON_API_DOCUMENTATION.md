# Hierarchy Configuration & SVG Icons API Documentation

This document provides comprehensive API documentation for hierarchy configuration and SVG icon management endpoints.

## Base URL
```
http://your-server:8000/api/v1
```

## Authentication & Headers
All endpoints require the following header:
```
plant-id: <your_plant_id>
```

## Response Format
All endpoints return responses in the following standardized format:

```json
{
  "status": "success" | "fail",
  "data": <response_data>,
  "message": "Optional descriptive message",
  "pagination": null
}
```

---

## 1. Hierarchy Configuration Endpoints

### 1.1 Upload Hierarchy Configuration

**Endpoint:** `POST /hierarchy/upload`

**Description:** Upload an Excel file to build hierarchy configuration based on hierarchy paths.

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

**Error Responses:**
- `400`: Invalid file format or missing 'path' column
- `500`: Server error during processing

---

### 1.2 Get Hierarchy Configuration

**Endpoint:** `GET /hierarchy/config`

**Description:** Get all hierarchy configuration records.

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
        "display_name": "Equipment",
        "display_order": 0,
        "parent_label": null,
        "icon": "cog",
        "is_active": true,
        "created_at": "2024-01-15T10:30:00",
        "updated_at": "2024-01-15T10:30:00"
      },
      {
        "id": 2,
        "label": "Process",
        "path": "Equipment:Process",
        "display_name": "Process",
        "display_order": 1,
        "parent_label": "Equipment",
        "icon": "settings",
        "is_active": true,
        "created_at": "2024-01-15T10:30:01",
        "updated_at": "2024-01-15T10:30:01"
      }
    ],
    "total_records": 2
  },
  "message": "Hierarchy configuration retrieved successfully"
}
```

---

### 1.3 Get Hierarchy Tree Structure

**Endpoint:** `GET /hierarchy/tree`

**Description:** Get hierarchy configuration in tree structure format.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`

**Response:**
```json
{
  "status": "success",
  "data": {
    "tree": [
      {
        "label": "Equipment",
        "display_name": "Equipment",
        "icon": "cog",
        "children": [
          {
            "label": "Process",
            "display_name": "Process",
            "icon": "settings",
            "children": [
              {
                "label": "Vessel",
                "display_name": "Vessel",
                "icon": "database",
                "children": []
              }
            ]
          }
        ]
      }
    ],
    "total_nodes": 3
  },
  "message": "Hierarchy tree structure retrieved successfully"
}
```

---

### 1.4 Get Hierarchy by Label

**Endpoint:** `GET /hierarchy/config/{label}`

**Description:** Get specific hierarchy configuration by label.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`
- **Path Parameters:**
  - `label`: The hierarchy label to retrieve

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "label": "Equipment",
    "path": "Equipment",
    "display_name": "Equipment",
    "display_order": 0,
    "parent_label": null,
    "icon": "cog",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  },
  "message": "Hierarchy configuration retrieved successfully"
}
```

**Error Responses:**
- `404`: Hierarchy config not found for the specified label

---

### 1.5 Get Hierarchy Children

**Endpoint:** `GET /hierarchy/children/{parent_label}`

**Description:** Get children of a specific parent label.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`
- **Path Parameters:**
  - `parent_label`: The parent label to get children for

**Response:**
```json
{
  "status": "success",
  "data": {
    "children": [
      {
        "id": 2,
        "label": "Process",
        "path": "Equipment:Process",
        "display_name": "Process",
        "display_order": 1,
        "parent_label": "Equipment",
        "icon": "settings",
        "is_active": true
      }
    ],
    "total_children": 1
  },
  "message": "Hierarchy children retrieved successfully"
}
```

---

### 1.6 Update Hierarchy Configuration

**Endpoint:** `PUT /hierarchy/config/{label}`

**Description:** Update a specific hierarchy configuration record.

**Request:**
- **Method:** PUT
- **Headers:** 
  - `plant-id: <plant_id>`
  - `Content-Type: application/json`
- **Path Parameters:**
  - `label`: The hierarchy label to update

**Request Body:**
```json
{
  "display_name": "Updated Equipment Name",
  "display_order": 5,
  "is_active": true,
  "parent_label": "NewParent",
  "icon": "new-icon"
}
```

**Allowed Fields:**
- `display_name`: String
- `display_order`: Integer
- `is_active`: Boolean
- `parent_label`: String (or null)
- `icon`: String

**Response:**
```json
{
  "status": "success",
  "data": {
    "updated_fields": ["display_name", "icon"]
  },
  "message": "Successfully updated hierarchy config for label: Equipment"
}
```

**Error Responses:**
- `400`: No valid fields to update
- `404`: Hierarchy config not found for the specified label

---

### 1.7 Delete Hierarchy Configuration

**Endpoint:** `DELETE /hierarchy/config/{label}`

**Description:** Delete a specific hierarchy configuration record.

**Request:**
- **Method:** DELETE
- **Headers:** 
  - `plant-id: <plant_id>`
- **Path Parameters:**
  - `label`: The hierarchy label to delete

**Response:**
```json
{
  "status": "success",
  "data": null,
  "message": "Successfully deleted hierarchy config for label: Equipment"
}
```

**Error Responses:**
- `404`: Hierarchy config not found for the specified label

---

### 1.8 Clear All Hierarchy Configuration

**Endpoint:** `DELETE /hierarchy/config`

**Description:** Clear all hierarchy configuration records.

**Request:**
- **Method:** DELETE
- **Headers:** 
  - `plant-id: <plant_id>`

**Response:**
```json
{
  "status": "success",
  "data": {
    "deleted_count": 15
  },
  "message": "Successfully deleted 15 hierarchy config records"
}
```

---

### 1.9 Validate Hierarchy Integrity

**Endpoint:** `GET /hierarchy/validate`

**Description:** Validate the integrity of the hierarchy structure.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`

**Response:**
```json
{
  "status": "success",
  "data": {
    "is_valid": true,
    "total_records": 15,
    "orphaned_records": 0,
    "circular_references": 0,
    "validation_errors": []
  },
  "message": "Hierarchy validation completed successfully"
}
```

---

## 2. SVG Icons Endpoints

### 2.1 Upload SVG Icon

**Endpoint:** `POST /hierarchy/icons/upload`

**Description:** Upload SVG icon file for hierarchy configuration.

**Request:**
- **Method:** POST
- **Content-Type:** multipart/form-data
- **Headers:** 
  - `plant-id: <plant_id>`
- **Query Parameters:**
  - `icon_name`: String (required) - Name for the icon

**Request Body:**
```
file: <SVG file (.svg)>
```

**SVG File Requirements:**
- Must be valid SVG format
- Maximum file size: 1MB
- Must not contain dangerous elements (script, object, embed, iframe, link)
- Must not contain event handlers (onload, onclick, etc.)

**Response:**
```json
{
  "status": "success",
  "data": {
    "icon_name": "equipment-icon",
    "filename": "equipment-icon_a1b2c3d4.svg",
    "file_path": "/tmp/hierarchy_icons/equipment-icon_a1b2c3d4.svg",
    "svg_base64": "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPi4uLjwvc3ZnPg==",
    "size_bytes": 1024
  },
  "message": "Successfully uploaded SVG icon: equipment-icon"
}
```

**Error Responses:**
- `400`: Invalid file format, missing icon name, or dangerous SVG content
- `500`: Server error during processing

---

### 2.2 Get Available Icons

**Endpoint:** `GET /hierarchy/icons`

**Description:** Get list of available SVG icons.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`

**Response:**
```json
{
  "status": "success",
  "data": {
    "icons": [
      {
        "icon_name": "equipment-icon",
        "filename": "equipment-icon_a1b2c3d4.svg",
        "file_size": 1024,
        "file_path": "/tmp/hierarchy_icons/equipment-icon_a1b2c3d4.svg"
      },
      {
        "icon_name": "process-icon",
        "filename": "process-icon_e5f6g7h8.svg",
        "file_size": 2048,
        "file_path": "/tmp/hierarchy_icons/process-icon_e5f6g7h8.svg"
      }
    ],
    "total_icons": 2
  },
  "message": "Available icons retrieved successfully"
}
```

---

### 2.3 Get SVG Icon Content

**Endpoint:** `GET /hierarchy/icons/{icon_name}`

**Description:** Get SVG icon content by name.

**Request:**
- **Method:** GET
- **Headers:** 
  - `plant-id: <plant_id>`
- **Path Parameters:**
  - `icon_name`: The icon name to retrieve

**Response:**
- **Content-Type:** `image/svg+xml`
- **Body:** Raw SVG content
- **Headers:**
  - `Cache-Control: public, max-age=3600`
  - `Content-Disposition: inline; filename=<filename>`

**Error Responses:**
- `404`: Icon not found
- `500`: Error reading SVG file

---

### 2.4 Update Hierarchy Icon

**Endpoint:** `PUT /hierarchy/config/{label}/icon`

**Description:** Update the icon for a specific hierarchy configuration record.

**Request:**
- **Method:** PUT
- **Headers:** 
  - `plant-id: <plant_id>`
  - `Content-Type: application/json`
- **Path Parameters:**
  - `label`: The hierarchy label to update

**Request Body:**
```json
{
  "icon": "new-icon-name"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "label": "Equipment",
    "new_icon": "new-icon-name"
  },
  "message": "Successfully updated icon for hierarchy label: Equipment"
}
```

**Error Responses:**
- `400`: Icon name is required in request body
- `404`: Hierarchy config not found for the specified label

---

## 3. Frontend Implementation Examples

### 3.1 JavaScript/TypeScript Examples

#### Upload Hierarchy Configuration
```javascript
const uploadHierarchyConfig = async (file, plantId) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/v1/hierarchy/upload', {
    method: 'POST',
    headers: {
      'plant-id': plantId
    },
    body: formData
  });

  const result = await response.json();
  return result;
};
```

#### Upload SVG Icon
```javascript
const uploadSVGIcon = async (file, iconName, plantId) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`/api/v1/hierarchy/icons/upload?icon_name=${encodeURIComponent(iconName)}`, {
    method: 'POST',
    headers: {
      'plant-id': plantId
    },
    body: formData
  });

  const result = await response.json();
  return result;
};
```

#### Get Hierarchy Tree
```javascript
const getHierarchyTree = async (plantId) => {
  const response = await fetch('/api/v1/hierarchy/tree', {
    method: 'GET',
    headers: {
      'plant-id': plantId
    }
  });

  const result = await response.json();
  return result;
};
```

#### Update Hierarchy Configuration
```javascript
const updateHierarchyConfig = async (label, updates, plantId) => {
  const response = await fetch(`/api/v1/hierarchy/config/${encodeURIComponent(label)}`, {
    method: 'PUT',
    headers: {
      'plant-id': plantId,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });

  const result = await response.json();
  return result;
};
```

#### Get Available Icons
```javascript
const getAvailableIcons = async (plantId) => {
  const response = await fetch('/api/v1/hierarchy/icons', {
    method: 'GET',
    headers: {
      'plant-id': plantId
    }
  });

  const result = await response.json();
  return result;
};
```

### 3.2 React Component Example

```jsx
import React, { useState, useEffect } from 'react';

const HierarchyManager = ({ plantId }) => {
  const [hierarchyTree, setHierarchyTree] = useState([]);
  const [availableIcons, setAvailableIcons] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadHierarchyTree();
    loadAvailableIcons();
  }, [plantId]);

  const loadHierarchyTree = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/hierarchy/tree', {
        headers: { 'plant-id': plantId }
      });
      const result = await response.json();
      
      if (result.status === 'success') {
        setHierarchyTree(result.data.tree);
      }
    } catch (error) {
      console.error('Error loading hierarchy tree:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableIcons = async () => {
    try {
      const response = await fetch('/api/v1/hierarchy/icons', {
        headers: { 'plant-id': plantId }
      });
      const result = await response.json();
      
      if (result.status === 'success') {
        setAvailableIcons(result.data.icons);
      }
    } catch (error) {
      console.error('Error loading icons:', error);
    }
  };

  const handleFileUpload = async (file, type) => {
    const formData = new FormData();
    formData.append('file', file);

    const endpoint = type === 'hierarchy' 
      ? '/api/v1/hierarchy/upload'
      : `/api/v1/hierarchy/icons/upload?icon_name=${file.name.replace('.svg', '')}`;

    try {
      setLoading(true);
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'plant-id': plantId },
        body: formData
      });

      const result = await response.json();
      
      if (result.status === 'success') {
        if (type === 'hierarchy') {
          await loadHierarchyTree();
        } else {
          await loadAvailableIcons();
        }
        alert(`${type} uploaded successfully!`);
      } else {
        alert(`Error: ${result.message}`);
      }
    } catch (error) {
      console.error(`Error uploading ${type}:`, error);
      alert(`Error uploading ${type}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Hierarchy Manager</h2>
      
      {/* File upload sections */}
      <div>
        <h3>Upload Hierarchy Configuration</h3>
        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0], 'hierarchy')}
        />
      </div>

      <div>
        <h3>Upload SVG Icon</h3>
        <input
          type="file"
          accept=".svg"
          onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0], 'icon')}
        />
      </div>

      {/* Display hierarchy tree */}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <div>
          <h3>Hierarchy Tree</h3>
          <pre>{JSON.stringify(hierarchyTree, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default HierarchyManager;
```

---

## 4. Error Handling

All endpoints follow a consistent error response format:

```json
{
  "status": "fail",
  "data": null,
  "message": "Detailed error message"
}
```

### Common HTTP Status Codes:
- `200`: Success
- `400`: Bad Request (invalid input, missing required fields)
- `404`: Not Found (resource not found)
- `500`: Internal Server Error

### Error Handling Best Practices:
1. Always check the `status` field in the response
2. Display the `message` field to users for error feedback
3. Implement proper loading states during API calls
4. Handle network errors and timeouts appropriately

---

## 5. Default Icons Available

The system automatically assigns default icons based on component names:

| Component Type | Default Icon |
|----------------|--------------|
| equipment | cog |
| process | settings |
| vessel | database |
| mixer | shuffle |
| splitter | split |
| column | bar-chart |
| pump | zap |
| valve | toggle-left |
| tank | droplet |
| reactor | atom |
| heat | thermometer |
| cool | snowflake |
| filter | filter |
| separator | layers |
| compressor | wind |
| turbine | rotate-cw |
| motor | power |
| sensor | activity |
| control | sliders |
| safety | shield |
| maintenance | tool |
| inspection | search |
| quality | check-circle |
| production | play-circle |
| utility | grid |
| electrical | zap |
| mechanical | settings |
| instrumentation | gauge |
| piping | git-branch |
| default | file |

---

This completes the comprehensive API documentation for hierarchy configuration and SVG icon management endpoints. The frontend team can use this documentation to implement the required functionality.


