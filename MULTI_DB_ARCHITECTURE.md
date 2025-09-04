# Multi-Database Architecture

This project now supports a multi-database architecture with a central database and multiple plant-specific databases.

## Architecture Overview

### Central Database
- **Purpose**: Stores user management, plant registry, permissions, and global configuration
- **Tables**: Users, GlobalRoles, GlobalPermissions, PlantsRegistry, UserPlantAccess, AdminLogs, PlantSchemaVersion
- **Connection**: Single database connection for all central operations

### Plant Databases
- **Purpose**: Each plant has its own database with identical schema
- **Tables**: All plant-specific data (workspaces, tags, time_series, alerts, etc.)
- **Connection**: Dynamic connection based on plant_id

## Database Configuration

### Environment Variables

#### Central Database
```env
DB_USER=your_central_db_user
DB_PASSWORD=your_central_db_password
DB_HOST=your_central_db_host
DB_PORT=5432
DB_NAME=your_central_db_name
```

#### Plant Databases
For each plant, you need to set environment variables using the plant's `database_key`:

```env
# For plant with database_key "CAIRO"
CAIRO_USER=cairo_db_user
CAIRO_PASSWORD=cairo_db_password
CAIRO_HOST=cairo_db_host
CAIRO_PORT=5432
CAIRO_NAME=cairo_db_name

# For plant with database_key "ALEX"
ALEX_USER=alex_db_user
ALEX_PASSWORD=alex_db_password
ALEX_HOST=alex_db_host
ALEX_PORT=5432
ALEX_NAME=alex_db_name
```

## Database Models

### Central Models (`models/central_models.py`)
- `User`: User accounts
- `GlobalRole`: Global roles across all plants
- `GlobalPermission`: Global permissions
- `PlantsRegistry`: Registry of all plants and their connection info
- `UserPlantAccess`: User access to specific plants
- `AdminLogs`: Administrative activity logs
- `PlantSchemaVersion`: Schema version tracking for each plant

### Plant Models (`models/plant_models.py`)
- `Workspace`: Plant-specific workspaces
- `Tag`: Plant-specific tags
- `TimeSeries`: Time-series data
- `Alerts`: Plant-specific alerts
- And many more plant-specific entities

## API Usage

### Required Headers
All plant-specific endpoints require the `plant-id` header:

```http
plant-id: 1
x-user-id: 123
```

### Database Dependencies

#### Central Database Operations
```python
from database import get_central_db

async def user_operation():
    async for session in get_central_db():
        # Central database operations
        pass
```

#### Plant Database Operations
```python
from database import get_plant_db_with_context, get_plant_context
from fastapi import Depends

async def plant_operation(
    db: AsyncSession = Depends(get_plant_db_with_context)
):
    # Plant database operations
    pass
```

## Database Initialization

The system automatically initializes all databases on startup:

1. **Central Database**: Creates all central tables
2. **Plant Databases**: For each active plant in the registry, creates all plant tables

## Health Monitoring

The system provides health checks for all databases:

```python
from database import check_db_health

health_status = await check_db_health()
# Returns status of central DB and all plant DBs
```

## Migration from Single Database

### Breaking Changes
1. All endpoints now require `plant-id` header
2. Database sessions are plant-specific
3. Some utility functions now require `plant_id` parameter

### Updated Files
- `main.py`: Removed old database initialization
- `routers/endpoints.py`: Updated to use plant-specific sessions
- `services/data_import.py`: Updated to accept plant_id
- `services/db_import_services.py`: Updated for plant-specific imports
- `services/date_retrieval.py`: Updated for plant-specific operations
- `utils/db_init.py`: Updated for plant-specific initialization

## Testing

Run the test script to verify the multi-database setup:

```bash
python test_multi_db.py
```

## Troubleshooting

### Common Issues

1. **Missing Plant ID Header**
   ```
   HTTP 400: Plant ID header (plant-id) is required
   ```
   Solution: Add `plant-id` header to your request

2. **Plant Not Found**
   ```
   HTTP 404: Plant {plant_id} not found or inactive
   ```
   Solution: Check if the plant exists and is active in the central database

3. **Database Connection Error**
   ```
   HTTP 500: Missing required environment variables for plant database: {database_key}
   ```
   Solution: Ensure all environment variables for the plant's database are set

### Environment Variable Checklist

For each plant in your `plants_registry` table, ensure these environment variables exist:
- `{DATABASE_KEY}_USER`
- `{DATABASE_KEY}_PASSWORD`
- `{DATABASE_KEY}_HOST`
- `{DATABASE_KEY}_PORT`
- `{DATABASE_KEY}_NAME`

## Security Considerations

1. **Plant Isolation**: Each plant's data is completely isolated in separate databases
2. **Access Control**: User access to plants is controlled through the central database
3. **Connection Security**: Each database connection uses its own credentials
4. **Header Validation**: All plant-specific operations validate the plant-id header

## Performance Considerations

1. **Connection Pooling**: Each plant database maintains its own connection pool
2. **Caching**: Plant database engines are cached for performance
3. **Parallel Processing**: Plant databases can be processed in parallel
4. **Resource Management**: Connections are properly closed after use 