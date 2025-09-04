from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.config import settings
from utils.log import setup_logger
from models.central_models import CentralBase
from models.plant_models import PlantBase
from fastapi import Header, HTTPException, Depends
from typing import Optional, AsyncGenerator, Dict, Tuple
from sqlalchemy import text
import asyncio

logger = setup_logger(__name__)

# =============================================================================
# DATABASE ENGINES
# =============================================================================

# Central Database Engine - for users, plants, permissions
central_engine = create_async_engine(settings.CENTRAL_DATABASE_URL, echo=False, future=True)
logger.info(f"Central Database initialized")
CentralSessionLocal = async_sessionmaker(central_engine, class_=AsyncSession, expire_on_commit=False)

# Plant Database Engines Cache - {plant_id: (engine, session_maker)}
plant_engines: Dict[str, Tuple] = {}
plant_engines_lock = asyncio.Lock()

async def get_plant_engine(plant_id: str) -> Tuple:
    """Get or create database engine for a specific plant"""
    async with plant_engines_lock:
        if plant_id in plant_engines:
            return plant_engines[plant_id]
        
        # Get plant database connection info from central database
        async with CentralSessionLocal() as session:
            query = text("""
                SELECT database_key, connection_key, name 
                FROM plants_registry 
                WHERE id = :plant_id AND is_active = true
            """)
            # Convert plant_id to integer for database query
            result = await session.execute(query, {"plant_id": int(plant_id)})
            plant_info = result.fetchone()
            
            if not plant_info:
                raise HTTPException(status_code=404, detail=f"Plant {plant_id} not found or inactive")
            
            # database_key = plant_info.database_key
            connection_key = plant_info.connection_key
            plant_name = plant_info.name
            
            # Get database URL using the settings method with database_key
            try:
                db_url = settings.get_plant_database_url(connection_key)
            except ValueError as e:
                raise HTTPException(status_code=500, detail=str(e))
            
            # Create database engine and session maker
            engine = create_async_engine(db_url, echo=False, future=True)
            session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            
            # Cache the engine and session maker
            plant_engines[plant_id] = (engine, session_maker)
            logger.info(f"Created database connection for Plant {plant_id} ({plant_name})")
            
            return engine, session_maker

# =============================================================================
# DATABASE DEPENDENCIES
# =============================================================================

async def get_central_db() -> AsyncGenerator[AsyncSession, None]:
    """Central database dependency - for users, plants, permissions"""
    async with CentralSessionLocal() as session:
        try:
            logger.debug("Creating central database session")
            yield session
        except Exception as e:
            logger.error(f"Error in central database session: {e}")
            await session.rollback()
            raise e
        finally:
            await session.close()

async def get_plant_db(plant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Plant database dependency - for plant-specific data"""
    try:
        _, session_maker = await get_plant_engine(plant_id)
        async with session_maker() as session:
            try:
                logger.debug(f"Creating plant database session for Plant {plant_id}")
                yield session
            except Exception as e:
                logger.error(f"Error in plant database session for Plant {plant_id}: {e}")
                await session.rollback()
                raise e
            finally:
                await session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create plant database session for Plant {plant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed for Plant {plant_id}")

async def get_plant_context(
    plant_id: Optional[str] = Header(None, alias="plant-id"),
    auth_user_id: Optional[str] = Header(None, alias="x-user-id")
) -> dict:
    """Get plant context from headers"""
    if not plant_id:
        raise HTTPException(status_code=400, detail="Plant ID header (plant-id) is required")
    
    return {
        "plant_id": plant_id,
        "auth_user_id": auth_user_id
    }

async def get_plant_db_with_context(
    context: dict = Depends(get_plant_context)
) -> AsyncGenerator[AsyncSession, None]:
    """Plant database with context validation"""
    async for session in get_plant_db(context["plant_id"]):
        yield session

# =============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# =============================================================================

async def get_db():
    """Original get_db function - requires plant context in headers for backward compatibility"""
    # Try to get plant_id from headers (this will work in FastAPI request context)
    try:
        from fastapi import Request
        # This is a fallback - ideally all endpoints should be updated to use get_plant_db_with_context
        raise HTTPException(
            status_code=400, 
            detail="This endpoint needs to be updated to use plant-specific database dependencies"
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Plant ID header (plant-id) is required for database access"
        )

# =============================================================================
# CONVENIENCE FUNCTIONS FOR SPECIFIC OPERATIONS
# =============================================================================

async def get_user_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for user operations (central database)"""
    async for session in get_central_db():
        yield session

async def get_workspace_db_for_plant(plant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for workspace operations for a specific plant"""
    async for session in get_plant_db(plant_id):
        yield session

async def get_tag_db_for_plant(plant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for tag operations for a specific plant"""
    async for session in get_plant_db(plant_id):
        yield session

async def get_card_db_for_plant(plant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for card operations for a specific plant"""
    async for session in get_plant_db(plant_id):
        yield session

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

async def init_db():
    """Initialize central database and all active plant databases"""
    logger.info("Initializing databases...")
    
    # Initialize central database first
    await init_central_db()
    
    # Get all active plants and initialize their databases
    try:
        async with CentralSessionLocal() as session:
            query = text("SELECT id, name FROM plants_registry WHERE is_active = true")
            result = await session.execute(query)
            plants = result.fetchall()
        
        if not plants:
            logger.warning("No active plants found in plants_registry")
            return
        
        # Initialize all plant databases
        for plant_id, plant_name in plants:
            try:
                await init_plant_db(str(plant_id))
                logger.success(f"Initialized database for Plant {plant_id} ({plant_name})")
            except Exception as e:
                logger.error(f"Failed to initialize database for Plant {plant_id} ({plant_name}): {e}")
                # Continue with other plants even if one fails
                continue
        
        logger.success("All databases initialized successfully")
        
    except Exception as e:
        logger.error(f"Error getting plant list for initialization: {e}")
        raise e

async def init_central_db():
    """Initialize central database"""
    try:
        async with central_engine.begin() as conn:
            await conn.run_sync(CentralBase.metadata.create_all)
            logger.success("Central database tables created")
    except Exception as e:
        logger.error(f"Error creating central database tables: {e}")
        raise e

async def init_plant_db(plant_id: str):
    """Initialize a specific plant's database"""
    try:
        engine, _ = await get_plant_engine(plant_id)
        async with engine.begin() as conn:
            await conn.run_sync(PlantBase.metadata.create_all)
            logger.success(f"Plant {plant_id} database tables created")
    except Exception as e:
        logger.error(f"Error creating plant {plant_id} database tables: {e}")
        raise e

# =============================================================================
# HEALTH CHECK & MONITORING
# =============================================================================

async def check_db_health() -> dict:
    """Check health of central database and all active plant databases"""
    health_status = {
        "central_db": False,
        "plant_dbs": {}
    }
    
    # Check central database
    try:
        async with CentralSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            health_status["central_db"] = True
            logger.debug("Central database health check passed")
    except Exception as e:
        logger.error(f"Central database health check failed: {e}")
        health_status["central_db"] = False
    
    # Check all active plant databases
    try:
        async with CentralSessionLocal() as session:
            query = text("SELECT id, name FROM plants_registry WHERE is_active = true")
            result = await session.execute(query)
            plants = result.fetchall()
        
        for plant_id, plant_name in plants:
            plant_id_str = str(plant_id)
            try:
                engine, _ = await get_plant_engine(plant_id_str)
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                    health_status["plant_dbs"][plant_id_str] = {
                        "status": True,
                        "name": plant_name
                    }
                    logger.debug(f"Plant {plant_id} ({plant_name}) database health check passed")
            except Exception as e:
                logger.error(f"Plant {plant_id} ({plant_name}) database health check failed: {e}")
                health_status["plant_dbs"][plant_id_str] = {
                    "status": False,
                    "name": plant_name,
                    "error": str(e)
                }
    except Exception as e:
        logger.error(f"Error checking plant databases health: {e}")
    
    return health_status

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def get_active_plants() -> list:
    """Get list of all active plants"""
    try:
        async with CentralSessionLocal() as session:
            query = text("""
                SELECT id, name, connection_key, database_key 
                FROM plants_registry 
                WHERE is_active = true 
                ORDER BY name
            """)
            result = await session.execute(query)
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "connection_key": row.connection_key,
                    "database_key": row.database_key
                }
                for row in result.fetchall()
            ]
    except Exception as e:
        logger.error(f"Error getting active plants: {e}")
        return []

async def validate_plant_access(user_id: int, plant_id: str) -> bool:
    """Validate if user has access to a specific plant"""
    try:
        async with CentralSessionLocal() as session:
            query = text("""
                SELECT EXISTS(
                    SELECT 1 
                    FROM user_plant_access upa
                    JOIN plants_registry pr ON upa.plant_id = pr.id
                    WHERE upa.user_id = :user_id 
                    AND pr.id = :plant_id
                    AND upa.is_active = true
                    AND pr.is_active = true
                ) as has_access
            """)
            # Convert plant_id to integer for database query
            result = await session.execute(query, {"user_id": user_id, "plant_id": int(plant_id)})
            return bool(result.scalar())
    except Exception as e:
        logger.error(f"Error validating plant access for user {user_id}, plant {plant_id}: {e}")
        return False

# =============================================================================
# BACKWARD COMPATIBILITY VARIABLES
# =============================================================================

# Keep these for backward compatibility with existing query files
# These point to the central engine by default - query files should be updated
# to use the new plant-specific database functions
engine = central_engine
SessionLocal = CentralSessionLocal

logger.warning("Using deprecated 'engine' and 'SessionLocal' imports. Please update to use plant-specific database functions.")
