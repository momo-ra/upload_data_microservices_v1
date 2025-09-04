from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, get_central_db, get_plant_db_with_context
from utils.log import setup_logger
from fastapi import Depends, HTTPException, Request
from middleware.auth_middleware import authenticate_user, get_user_id, is_admin
from sqlalchemy import text
from typing import List, Dict, Any, Optional, Set, Union
import asyncio

logger = setup_logger(__name__)

# Define common permission names for reuse
class Permissions:
    VIEW_ANY_USER_CARDS = "view_any_user_cards"
    CREATE_ANY_USER_CARDS = "create_any_user_cards"
    DELETE_ANY_USER_CARDS = "delete_any_user_cards"
    EDIT_ANY_USER_CARDS = "edit_any_user_cards"
    ADMIN_ACCESS = "admin_access"
    VIEW_PLANT_DATA = "view_plant_data"
    EDIT_PLANT_DATA = "edit_plant_data"
    MANAGE_USERS = "manage_users"
    MANAGE_WORKSPACES = "manage_workspaces"

async def check_first_time_system_access(db: AsyncSession) -> bool:
    """
    Check if this is the first time the system is being accessed (no users exist).
    Returns True if system is empty (first time), False otherwise.
    """
    try:
        query = text("SELECT COUNT(*) as user_count FROM users")
        result = await db.execute(query)
        user_count = result.scalar()
        
        is_first_time = user_count == 0
        if is_first_time:
            logger.info("System is empty - allowing access for first time setup")
        return is_first_time
    except Exception as e:
        logger.error(f"Error checking first time system access: {e}")
        return False

async def get_user_global_permissions(db: AsyncSession, user_id: int, plant_id: Optional[int] = None) -> List[str]:
    """
    Get user's global permissions based on their role and plant access.
    Returns a list of permission names.
    """
    try:
        if plant_id:
            # Plant-specific permissions
            query = text("""
                SELECT DISTINCT gp.name 
                FROM global_permissions gp
                JOIN global_role_permissions grp ON gp.id = grp.permission_id
                JOIN global_roles gr ON grp.role_id = gr.id
                JOIN user_plant_access upa ON upa.global_role_id = gr.id
                WHERE upa.user_id = :user_id 
                AND upa.plant_id = :plant_id 
                AND upa.is_active = true
                AND gr.is_active = true
            """)
            result = await db.execute(query, {"user_id": user_id, "plant_id": plant_id})
        else:
            # Global permissions (any plant access)
            query = text("""
                SELECT DISTINCT gp.name 
                FROM global_permissions gp
                JOIN global_role_permissions grp ON gp.id = grp.permission_id
                JOIN global_roles gr ON grp.role_id = gr.id
                JOIN user_plant_access upa ON upa.global_role_id = gr.id
                WHERE upa.user_id = :user_id 
                AND upa.is_active = true
                AND gr.is_active = true
            """)
            result = await db.execute(query, {"user_id": user_id})
        
        permissions = [row[0] for row in result.all()]
        logger.info(f"User {user_id} has {'plant-specific' if plant_id else 'global'} permissions: {permissions}")
        return permissions
    except Exception as e:
        logger.error(f"Error fetching global permissions for user {user_id}: {e}")
        return []

async def check_global_permission(permission_name: str, db: AsyncSession, user_id: int, plant_id: Optional[int] = None) -> bool:
    """
    Check if a user has a specific global permission.
    Returns True if permission exists, False otherwise.
    """
    if not user_id:
        logger.warning("No user_id provided to check_global_permission")
        return False
        
    try:
        # First check if system is empty (first time access)
        is_first_time = await check_first_time_system_access(db)
        if is_first_time:
            logger.info(f"First time system access - allowing permission: {permission_name}")
            return True
        
        # Get user's permissions
        user_permissions = await get_user_global_permissions(db, user_id, plant_id)
        has_permission = permission_name in user_permissions
        
        if has_permission:
            logger.info(f"User {user_id} has global permission: {permission_name}")
        else:
            logger.warning(f"User {user_id} does NOT have global permission: {permission_name}")
            
        return has_permission
    except Exception as e:
        logger.error(f"Error checking global permission for user {user_id}: {e}")
        return False

async def get_user_permissions(db: AsyncSession, user_id: int) -> List[str]:
    """
    Get all permissions for a specific user (legacy function for backward compatibility).
    Returns a list of permission names.
    """
    try:
        query = text("""
            SELECT p.name FROM permission p
            JOIN role_permission rp ON p.id = rp.permission_id
            JOIN role r ON rp.role_id = r.id
            JOIN "user" u ON u.role_id = r.id
            WHERE u.id = :user_id
        """)
        result = await db.execute(query, {"user_id": user_id})
        permissions = [row[0] for row in result.all()]
        logger.info(f"User {user_id} has legacy permissions: {permissions}")
        return permissions
    except Exception as e:
        logger.error(f"Error fetching legacy permissions for user {user_id}: {e}")
        return []

async def check_permission(permission_name: str, db: AsyncSession = Depends(get_db), user_id: int = None):
    """
    Check if a user has a specific permission (legacy function for backward compatibility).
    Returns True if permission exists, False otherwise.
    """
    if not user_id:
        logger.warning("No user_id provided to check_permission")
        return False
        
    try:
        query = text("""
            SELECT 1 FROM permission p
            JOIN role_permission rp ON p.id = rp.permission_id
            JOIN role r ON rp.role_id = r.id
            JOIN "user" u ON u.role_id = r.id
            WHERE u.id = :user_id AND p.name = :permission_name
        """)
        result = await db.execute(query, {"user_id": user_id, "permission_name": permission_name})
        has_permission = result.scalar_one_or_none() is not None
        
        if has_permission:
            logger.info(f"User {user_id} has legacy permission: {permission_name}")
        else:
            logger.warning(f"User {user_id} does NOT have legacy permission: {permission_name}")
            
        return has_permission
    except Exception as e:
        logger.error(f"Error checking legacy permission for user {user_id}: {e}")
        return False

async def get_user_role(db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the role information for a specific user.
    Returns a dictionary with role details or None if not found.
    """
    try:
        query = text("""
            SELECT r.id, r.name, r.description FROM role r
            JOIN "user" u ON u.role_id = r.id
            WHERE u.id = :user_id
        """)
        result = await db.execute(query, {"user_id": user_id})
        role_row = result.first()
        
        if not role_row:
            logger.warning(f"No role found for user {user_id}")
            return None
            
        role = {
            "id": role_row[0],
            "name": role_row[1],
            "description": role_row[2]
        }
        logger.info(f"User {user_id} has role: {role['name']}")
        return role
    except Exception as e:
        logger.error(f"Error fetching role for user {user_id}: {e}")
        return None

def extract_plant_id_from_request(request: Request) -> Optional[int]:
    """
    Extract plant ID from request parameters, body, or headers.
    Returns plant_id as integer or None if not found.
    """
    try:
        # Check path parameters
        plant_id = request.path_params.get("plant_id") or request.path_params.get("plantId")
        if plant_id:
            return int(plant_id)
        
        # Check query parameters
        plant_id = request.query_params.get("plant_id") or request.query_params.get("plantId")
        if plant_id:
            return int(plant_id)
        
        # Check headers
        plant_id = request.headers.get("plant-id") or request.headers.get("plantId")
        if plant_id:
            return int(plant_id)
        
        return None
    except (ValueError, TypeError):
        logger.warning(f"Invalid plant_id format: {plant_id}")
        return None

# FastAPI dependency for requiring specific permissions (Updated)
class RequirePermission:
    """
    FastAPI dependency for requiring specific permissions.
    Updated to support both global and plant-specific permissions.
    """
    def __init__(self, permission_name: str, allow_first_time: bool = True):
        self.permission_name = permission_name
        self.allow_first_time = allow_first_time
        
    async def __call__(
        self, 
        request: Request,
        db: AsyncSession = Depends(get_central_db), 
        auth_data: Dict[str, Any] = Depends(authenticate_user)
    ) -> Dict[str, Any]:
        user_id = get_user_id(auth_data)
        
        # Always allow admins to bypass permission checks
        if is_admin(auth_data):
            return auth_data
        
        # Check for first time system access
        if self.allow_first_time:
            is_first_time = await check_first_time_system_access(db)
            if is_first_time:
                logger.info(f"First time system access - allowing permission: {self.permission_name}")
                return auth_data
        
        # Extract plant ID from request
        plant_id = extract_plant_id_from_request(request)
        
        # Check permission based on whether plant_id is provided
        if plant_id:
            # Plant-specific permission check
            has_permission = await check_global_permission(self.permission_name, db, user_id, plant_id)
            if not has_permission:
                logger.warning(f"Plant-specific permission denied: User {user_id} lacks {self.permission_name} for plant {plant_id}")
                raise HTTPException(
                    status_code=403, 
                    detail=f"Forbidden: No access to this plant or insufficient permissions"
                )
        else:
            # Global permission check
            has_permission = await check_global_permission(self.permission_name, db, user_id)
            if not has_permission:
                logger.warning(f"Global permission denied: User {user_id} lacks {self.permission_name}")
                raise HTTPException(
                    status_code=403, 
                    detail=f"Forbidden: Insufficient permissions"
                )
            
        return auth_data

# Convenience function for checking ownership
async def is_card_owner(db: AsyncSession, card_id: int, user_id: int) -> bool:
    """
    Check if a user is the owner of a specific card.
    Returns True if user owns the card, False otherwise.
    """
    try:
        query = text("""
            SELECT 1 FROM card_data
            WHERE id = :card_id AND user_id = :user_id
        """)
        result = await db.execute(query, {"card_id": card_id, "user_id": user_id})
        is_owner = result.scalar_one_or_none() is not None
        
        if is_owner:
            logger.info(f"User {user_id} is owner of card {card_id}")
        else:
            logger.info(f"User {user_id} is NOT owner of card {card_id}")
            
        return is_owner
    except Exception as e:
        logger.error(f"Error checking card ownership for user {user_id}, card {card_id}: {e}")
        return False

# Helper for authorization logic
async def can_access_card(db: AsyncSession, card_id: int, auth_data: Dict[str, Any]) -> bool:
    """
    Check if the authenticated user can access a specific card.
    Returns True if access is allowed, False otherwise.
    
    Access rules:
    1. User is the card owner
    2. User has admin role
    3. User has view_any_user_cards permission
    4. User has access to the workspace containing the card
    """
    user_id = get_user_id(auth_data)
    
    # Admin can access any card
    if is_admin(auth_data):
        return True
        
    # Check if user is card owner
    is_owner = await is_card_owner(db, card_id, user_id)
    if is_owner:
        return True
        
    # Check workspace access for the card
    has_workspace_access = await can_access_card_via_workspace(db, card_id, user_id)
    if has_workspace_access:
        return True
        
    # Check for specific permission
    has_permission = await check_permission(Permissions.VIEW_ANY_USER_CARDS, db, user_id)
    return has_permission

# ================================
# WORKSPACE PERMISSION FUNCTIONS
# ================================

async def is_workspace_owner(db: AsyncSession, workspace_id: int, user_id: int) -> bool:
    """
    Check if a user is the owner of a specific workspace.
    Returns True if user owns the workspace, False otherwise.
    """
    try:
        query = text("""
            SELECT 1 FROM workspaces
            WHERE id = :workspace_id AND owner_id = :user_id AND is_active = true
        """)
        result = await db.execute(query, {"workspace_id": workspace_id, "user_id": user_id})
        is_owner = result.scalar_one_or_none() is not None
        
        if is_owner:
            logger.info(f"User {user_id} is owner of workspace {workspace_id}")
        else:
            logger.info(f"User {user_id} is NOT owner of workspace {workspace_id}")
            
        return is_owner
    except Exception as e:
        logger.error(f"Error checking workspace ownership for user {user_id}, workspace {workspace_id}: {e}")
        return False

async def is_workspace_member(db: AsyncSession, workspace_id: int, user_id: int) -> bool:
    """
    Check if a user is a member of a specific workspace.
    Returns True if user is a member, False otherwise.
    """
    try:
        query = text("""
            SELECT 1 FROM workspace_members wm
            JOIN workspace w ON wm.workspace_id = w.id
            WHERE wm.workspace_id = :workspace_id AND wm.user_id = :user_id
            AND w.is_active = true
        """)
        result = await db.execute(query, {"workspace_id": workspace_id, "user_id": user_id})
        is_member = result.scalar_one_or_none() is not None
        
        if is_member:
            logger.info(f"User {user_id} is member of workspace {workspace_id}")
        else:
            logger.info(f"User {user_id} is NOT member of workspace {workspace_id}")
            
        return is_member
    except Exception as e:
        logger.error(f"Error checking workspace membership for user {user_id}, workspace {workspace_id}: {e}")
        return False

async def has_workspace_access(user_id: int, workspace_id: int, plant_id: str = "1") -> bool:
    """
    Check if a user has access to a workspace using multi-database approach.
    Returns True if user has access, False otherwise.
    
    This function now provides better handling for plant switching scenarios.
    """
    try:
        from database import get_plant_db
        # Get database sessions using async for since both are async generators
        async for central_db in get_central_db():
            async for plant_db in get_plant_db(plant_id):
                # First verify user exists and is active in central database
                user_query = text("""
                    SELECT EXISTS(
                        SELECT 1 FROM users 
                        WHERE id = :user_id AND is_active = true
                    ) as user_exists
                """)
                
                user_result = await central_db.execute(user_query, {"user_id": user_id})
                user_exists = user_result.scalar()
                
                if not user_exists:
                    logger.warning(f"User {user_id} not found or inactive in central database")
                    return False
                
                # Check if workspace exists in this plant first
                workspace_exists_query = text("""
                    SELECT EXISTS (
                        SELECT 1 FROM workspaces 
                        WHERE id = :workspace_id AND is_active = true
                    ) as workspace_exists
                """)
                
                workspace_exists_result = await plant_db.execute(workspace_exists_query, {
                    "workspace_id": workspace_id
                })
                workspace_exists = workspace_exists_result.scalar()
                
                if not workspace_exists:
                    logger.warning(f"Workspace {workspace_id} does not exist in plant {plant_id}")
                    return False
                
                # Check workspace access in plant database
                workspace_query = text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM workspaces w
                        LEFT JOIN workspace_members wm ON w.id = wm.workspace_id AND wm.user_id = :user_id
                        WHERE w.id = :workspace_id 
                        AND w.is_active = true
                        AND (w.owner_id = :user_id OR wm.user_id IS NOT NULL)
                    ) as has_access
                """)
                
                workspace_result = await plant_db.execute(workspace_query, {
                    "workspace_id": workspace_id, 
                    "user_id": user_id
                })
                has_access = workspace_result.scalar()
                
                # Additional verification: check plant access in central database
                if has_access:
                    plant_access_query = text("""
                        SELECT EXISTS(
                            SELECT 1 
                            FROM user_plant_access upa
                            JOIN plants_registry pr ON upa.plant_id = pr.id
                            WHERE upa.user_id = :user_id 
                            AND pr.id = :plant_id
                            AND upa.is_active = true
                            AND pr.is_active = true
                        ) as has_plant_access
                    """)
                    
                    plant_access_result = await central_db.execute(plant_access_query, {
                        "user_id": user_id, 
                        "plant_id": int(plant_id)  # Convert to integer for database query
                    })
                    has_plant_access = plant_access_result.scalar()
                    
                    if not has_plant_access:
                        logger.warning(f"User {user_id} has no access to plant {plant_id}")
                        return False
                
                if has_access:
                    logger.info(f"User {user_id} has access to workspace {workspace_id} in plant {plant_id}")
                else:
                    logger.info(f"User {user_id} does NOT have access to workspace {workspace_id} in plant {plant_id}")
                    
                return bool(has_access)
                # Note: we break here after first iteration since async for only gives us one session
                
    except Exception as e:
        logger.error(f"Error checking workspace access for user {user_id}, workspace {workspace_id}: {e}")
        return False

async def get_user_accessible_workspaces_in_plant(user_id: int, plant_id: str) -> List[Dict[str, Any]]:
    """
    Get all workspaces accessible to a user in a specific plant.
    Returns a list of workspace dictionaries or empty list if none found.
    """
    try:
        from database import get_plant_db
        async for central_db in get_central_db():
            async for plant_db in get_plant_db(plant_id):
                # First verify user exists and is active in central database
                user_query = text("""
                    SELECT EXISTS(
                        SELECT 1 FROM users 
                        WHERE id = :user_id AND is_active = true
                    ) as user_exists
                """)
                
                user_result = await central_db.execute(user_query, {"user_id": user_id})
                user_exists = user_result.scalar()
                
                if not user_exists:
                    logger.warning(f"User {user_id} not found or inactive in central database")
                    return []
                
                # Check plant access in central database
                plant_access_query = text("""
                    SELECT EXISTS(
                        SELECT 1 
                        FROM user_plant_access upa
                        JOIN plants_registry pr ON upa.plant_id = pr.id
                        WHERE upa.user_id = :user_id 
                        AND pr.id = :plant_id
                        AND upa.is_active = true
                        AND pr.is_active = true
                    ) as has_plant_access
                """)
                
                plant_access_result = await central_db.execute(plant_access_query, {
                    "user_id": user_id, 
                    "plant_id": int(plant_id)
                })
                has_plant_access = plant_access_result.scalar()
                
                if not has_plant_access:
                    logger.warning(f"User {user_id} has no access to plant {plant_id}")
                    return []
                
                # Get accessible workspaces in this plant
                workspaces_query = text("""
                    SELECT DISTINCT w.id, w.name, w.description, w.owner_id,
                           CASE WHEN w.owner_id = :user_id THEN 'owner' ELSE 'member' END as user_role
                    FROM workspaces w
                    LEFT JOIN workspace_members wm ON w.id = wm.workspace_id AND wm.user_id = :user_id
                    WHERE w.is_active = true
                    AND (w.owner_id = :user_id OR wm.user_id IS NOT NULL)
                    ORDER BY w.name
                """)
                
                workspaces_result = await plant_db.execute(workspaces_query, {
                    "user_id": user_id
                })
                
                workspaces = []
                for row in workspaces_result.mappings().all():
                    workspace = {
                        "id": row["id"],
                        "name": row["name"],
                        "description": row["description"],
                        "owner_id": row["owner_id"],
                        "user_role": row["user_role"],
                        "plant_id": plant_id
                    }
                    workspaces.append(workspace)
                
                logger.info(f"User {user_id} has access to {len(workspaces)} workspaces in plant {plant_id}")
                return workspaces
                
    except Exception as e:
        logger.error(f"Error getting user workspaces in plant {plant_id} for user {user_id}: {e}")
        return []

async def validate_workspace_access_with_fallback(user_id: int, workspace_id: int, plant_id: str) -> Dict[str, Any]:
    """
    Validate workspace access and provide fallback information if access is denied.
    Returns a dictionary with access status and fallback data.
    """
    try:
        # First check if user has access to the requested workspace
        has_access = await has_workspace_access(user_id, workspace_id, plant_id)
        
        if has_access:
            return {
                "has_access": True,
                "workspace_id": workspace_id,
                "plant_id": plant_id,
                "message": "Access granted"
            }
        
        # If no access, get available workspaces in this plant
        available_workspaces = await get_user_accessible_workspaces_in_plant(user_id, plant_id)
        
        if available_workspaces:
            # User has access to other workspaces in this plant
            return {
                "has_access": False,
                "workspace_id": workspace_id,
                "plant_id": plant_id,
                "available_workspaces": available_workspaces,
                "message": f"Workspace {workspace_id} not accessible in plant {plant_id}. Available workspaces: {[w['id'] for w in available_workspaces]}"
            }
        else:
            # User has no access to any workspaces in this plant
            return {
                "has_access": False,
                "workspace_id": workspace_id,
                "plant_id": plant_id,
                "available_workspaces": [],
                "message": f"No workspace access in plant {plant_id}"
            }
            
    except Exception as e:
        logger.error(f"Error in validate_workspace_access_with_fallback: {e}")
        return {
            "has_access": False,
            "workspace_id": workspace_id,
            "plant_id": plant_id,
            "available_workspaces": [],
            "message": f"Error validating access: {str(e)}"
        }

# Wrapper function to maintain backward compatibility
async def has_workspace_access_legacy(db: AsyncSession, workspace_id: int, user_id: int, plant_id: str = "1") -> bool:
    """Legacy function wrapper for backward compatibility"""
    return await has_workspace_access(user_id, workspace_id, plant_id)

async def can_access_card_via_workspace(db: AsyncSession, card_id: int, user_id: int) -> bool:
    """
    Check if a user can access a card through workspace membership/ownership.
    Returns True if user has workspace access to the card, False otherwise.
    """
    try:
        query = text("""
            SELECT w.id FROM card_data cd
            JOIN workspaces w ON cd.workspace_id = w.id
            LEFT JOIN workspace_members wm ON w.id = wm.workspace_id
            WHERE cd.id = :card_id 
            AND (w.owner_id = :user_id OR wm.user_id = :user_id)
            AND cd.is_active = true AND w.is_active = true
            LIMIT 1
        """)
        result = await db.execute(query, {"card_id": card_id, "user_id": user_id})
        has_access = result.scalar_one_or_none() is not None
        
        if has_access:
            logger.info(f"User {user_id} can access card {card_id} via workspace")
        else:
            logger.info(f"User {user_id} cannot access card {card_id} via workspace")
            
        return has_access
    except Exception as e:
        logger.error(f"Error checking card workspace access for user {user_id}, card {card_id}: {e}")
        return False

async def get_user_workspaces(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all workspaces accessible to a user (owned or member).
    Returns a list of workspace dictionaries.
    """
    try:
        query = text("""
            SELECT DISTINCT w.id, w.name, w.description, w.plant_id, w.owner_id,
                   CASE WHEN w.owner_id = :user_id THEN 'owner' ELSE 'member' END as role
            FROM workspaces w
            LEFT JOIN workspace_members wm ON w.id = wm.workspace_id
            WHERE (w.owner_id = :user_id OR wm.user_id = :user_id)
            AND w.is_active = true
            ORDER BY w.name
        """)
        result = await db.execute(query, {"user_id": user_id})
        
        workspaces = []
        for row in result.all():
            workspace = {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "plant_id": row[3],
                "owner_id": row[4],
                "user_role": row[5]
            }
            workspaces.append(workspace)
        
        logger.info(f"User {user_id} has access to {len(workspaces)} workspaces")
        return workspaces
    except Exception as e:
        logger.error(f"Error getting user workspaces for user {user_id}: {e}")
        return []

# Workspace permission dependency classes
class RequireWorkspaceAccess:
    """FastAPI dependency for requiring workspace access (owner or member)"""
    def __init__(self, workspace_id_param: str = "workspace_id"):
        self.workspace_id_param = workspace_id_param
        
    async def __call__(
        self, 
        workspace_id: int,
        plant_id: str,
        auth_data: Dict[str, Any] = Depends(authenticate_user)
    ) -> Dict[str, Any]:
        user_id = get_user_id(auth_data)
        
        # Always allow admins
        if is_admin(auth_data):
            return auth_data
            
        has_access = await has_workspace_access(user_id, workspace_id, plant_id)
        if not has_access:
            logger.warning(f"Workspace access denied: User {user_id} cannot access workspace {workspace_id} in plant {plant_id}")
            raise HTTPException(
                status_code=403, 
                detail="Access denied: You don't have permission to access this workspace"
            )
            
        return auth_data

class RequireWorkspaceOwnership:
    """FastAPI dependency for requiring workspace ownership"""
    def __init__(self, workspace_id_param: str = "workspace_id"):
        self.workspace_id_param = workspace_id_param
        
    async def __call__(
        self, 
        workspace_id: int,
        db: AsyncSession = Depends(get_db), 
        auth_data: Dict[str, Any] = Depends(authenticate_user)
    ) -> Dict[str, Any]:
        user_id = get_user_id(auth_data)
        
        # Always allow admins
        if is_admin(auth_data):
            return auth_data
            
        is_owner = await is_workspace_owner(db, workspace_id, user_id)
        if not is_owner:
            logger.warning(f"Workspace ownership denied: User {user_id} is not owner of workspace {workspace_id}")
            raise HTTPException(
                status_code=403, 
                detail="Access denied: You must be the workspace owner to perform this action"
            )
            
        return auth_data

# ================================
# CONVENIENCE PERMISSION FUNCTIONS
# ================================

async def require_view_permission(
    request: Request,
    db: AsyncSession = Depends(get_central_db),
    auth_data: Dict[str, Any] = Depends(authenticate_user)
) -> Dict[str, Any]:
    """Convenience function for requiring view permissions"""
    return await RequirePermission(Permissions.VIEW_PLANT_DATA)(request, db, auth_data)

async def require_edit_permission(
    request: Request,
    db: AsyncSession = Depends(get_central_db),
    auth_data: Dict[str, Any] = Depends(authenticate_user)
) -> Dict[str, Any]:
    """Convenience function for requiring edit permissions"""
    return await RequirePermission(Permissions.EDIT_PLANT_DATA)(request, db, auth_data)

async def require_admin_permission(
    request: Request,
    db: AsyncSession = Depends(get_central_db),
    auth_data: Dict[str, Any] = Depends(authenticate_user)
) -> Dict[str, Any]:
    """Convenience function for requiring admin permissions"""
    return await RequirePermission(Permissions.ADMIN_ACCESS, allow_first_time=False)(request, db, auth_data)

# ================================
# USAGE EXAMPLES AND DOCUMENTATION
# ================================

"""
UPDATED PERMISSION MIDDLEWARE USAGE EXAMPLES

This middleware has been updated to align with the JavaScript implementation and provides
better support for global vs plant-specific permissions, first-time system access, and
improved error handling.

1. BASIC USAGE IN ROUTERS:

from middleware.permission_middleware import RequirePermission, Permissions

@router.get("/plants/{plant_id}/data")
async def get_plant_data(
    plant_id: int,
    request: Request,
    auth_data: Dict[str, Any] = Depends(RequirePermission(Permissions.VIEW_PLANT_DATA))
):
    # This will automatically check if user has VIEW_PLANT_DATA permission for the specific plant
    return {"data": "plant data"}

@router.post("/global/users")
async def create_user(
    request: Request,
    auth_data: Dict[str, Any] = Depends(RequirePermission(Permissions.MANAGE_USERS))
):
    # This will check global permissions (any plant access)
    return {"message": "user created"}

2. USING CONVENIENCE FUNCTIONS:

from middleware.permission_middleware import require_view_permission, require_edit_permission

@router.get("/data")
async def get_data(
    auth_data: Dict[str, Any] = Depends(require_view_permission)
):
    return {"data": "viewable data"}

@router.put("/data")
async def update_data(
    auth_data: Dict[str, Any] = Depends(require_edit_permission)
):
    return {"message": "data updated"}

3. FIRST-TIME SYSTEM ACCESS:

The middleware automatically allows access when the system is empty (no users exist).
This is useful for initial setup and configuration.

4. PLANT ID EXTRACTION:

The middleware automatically extracts plant_id from:
- Path parameters: /plants/{plant_id}/data
- Query parameters: ?plant_id=123
- Headers: plant-id: 123

5. ERROR HANDLING:

- 401: Unauthorized (user not authenticated)
- 403: Forbidden (insufficient permissions or no plant access)
- 500: Internal server error

6. LEGACY COMPATIBILITY:

All existing functions are maintained for backward compatibility:
- check_permission() - Legacy permission checking
- get_user_permissions() - Legacy permission fetching
- RequireWorkspaceAccess - Workspace access control
- RequireWorkspaceOwnership - Workspace ownership control

7. NEW FEATURES:

- check_first_time_system_access() - Check if system is empty
- get_user_global_permissions() - Get global permissions
- check_global_permission() - Check global permissions
- extract_plant_id_from_request() - Extract plant ID from request
- Convenience functions for common permissions

8. PERMISSION NAMES:

Available permission constants:
- Permissions.VIEW_PLANT_DATA
- Permissions.EDIT_PLANT_DATA
- Permissions.MANAGE_USERS
- Permissions.MANAGE_WORKSPACES
- Permissions.ADMIN_ACCESS
- Permissions.VIEW_ANY_USER_CARDS
- Permissions.CREATE_ANY_USER_CARDS
- Permissions.DELETE_ANY_USER_CARDS
- Permissions.EDIT_ANY_USER_CARDS
"""
