from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from typing import Dict, Any

CentralBase = declarative_base()

class BaseModel(object):
    """Base model with common attributes and methods"""
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class User(CentralBase, BaseModel):
    """Users - Central Database Only"""
    __tablename__ = "users"

    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_is_active', 'is_active'),
    )
    
    # Relationships
    plant_access = relationship("UserPlantAccess", back_populates="user", foreign_keys="[UserPlantAccess.user_id]", cascade="all, delete-orphan")
    granted_access = relationship("UserPlantAccess", back_populates="granted_by_user", foreign_keys="[UserPlantAccess.granted_by]")
    admin_logs = relationship("AdminLogs", back_populates="admin_user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"

class GlobalRole(CentralBase, BaseModel):
    """Global Roles - Central Database Only"""
    __tablename__ = "global_roles"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    __table_args__ = (
        Index('idx_global_roles_name', 'name'),
    )

    # Relationships
    permissions = relationship("GlobalRolePermission", back_populates="role", cascade="all, delete-orphan")
    user_access = relationship("UserPlantAccess", back_populates="global_role")

    def __repr__(self):
        return f"<GlobalRole(id={self.id}, name={self.name})>"

class GlobalPermission(CentralBase, BaseModel):
    """Global Permissions - Central Database Only"""
    __tablename__ = "global_permissions"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    __table_args__ = (
        Index('idx_global_permissions_name', 'name'),
    )

    # Relationships
    roles = relationship("GlobalRolePermission", back_populates="permission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GlobalPermission(id={self.id}, name={self.name})>"

class GlobalRolePermission(CentralBase, BaseModel):
    """Global Role-Permission Mapping - Central Database Only"""
    __tablename__ = "global_role_permissions"

    role_id = Column(Integer, ForeignKey('global_roles.id'), nullable=False)
    permission_id = Column(Integer, ForeignKey('global_permissions.id'), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_global_role_permission'),
        Index('idx_global_role_permission_role_id', 'role_id'),
        Index('idx_global_role_permission_permission_id', 'permission_id'),
    )

    # Relationships
    role = relationship("GlobalRole", back_populates="permissions")
    permission = relationship("GlobalPermission", back_populates="roles")
    
    def __repr__(self):
        return f"<GlobalRolePermission(id={self.id}, role_id={self.role_id}, permission_id={self.permission_id})>"

class PlantsRegistry(CentralBase, BaseModel):
    """Plants Registry - Central Database Only"""
    __tablename__ = "plants_registry"
    
    name = Column(String, nullable=False)
    description = Column(Text)
    connection_key = Column(String(100), unique=True, nullable=False)  # 'CAIRO', 'ALEX', 'SUEZ'
    database_key = Column(String(100), nullable=False)  # Environment variable key
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_plants_registry_connection_key', 'connection_key'),
        Index('idx_plants_registry_is_active', 'is_active'),
    )
    
    # Relationships
    user_access = relationship("UserPlantAccess", back_populates="plant", cascade="all, delete-orphan")
    schema_versions = relationship("PlantSchemaVersion", back_populates="plant", cascade="all, delete-orphan")
    admin_logs = relationship("AdminLogs", back_populates="plant")
    
    def __repr__(self):
        return f"<PlantsRegistry(id={self.id}, name={self.name}, connection_key={self.connection_key})>"

class UserPlantAccess(CentralBase, BaseModel):
    """User Access to Plants - Central Database Only"""
    __tablename__ = "user_plant_access"
    
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    plant_id = Column(Integer, ForeignKey('plants_registry.id'), nullable=False)
    global_role_id = Column(Integer, ForeignKey('global_roles.id'))
    access_level = Column(String(50), default='member')  # admin, member, viewer
    granted_by = Column(Integer, ForeignKey('users.id'))
    granted_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'plant_id', name='uq_user_plant_access'),
        Index('idx_user_plant_access_user', 'user_id'),
        Index('idx_user_plant_access_plant', 'plant_id'),
        Index('idx_user_plant_access_active', 'is_active'),
    )
    
    # Relationships
    user = relationship("User", back_populates="plant_access", foreign_keys=[user_id])
    plant = relationship("PlantsRegistry", back_populates="user_access")
    global_role = relationship("GlobalRole", back_populates="user_access")
    granted_by_user = relationship("User", back_populates="granted_access", foreign_keys=[granted_by])
    
    def __repr__(self):
        return f"<UserPlantAccess(id={self.id}, user_id={self.user_id}, plant_id={self.plant_id})>"

class AdminLogs(CentralBase, BaseModel):
    """Admin Activity Logs - Central Database Only"""
    __tablename__ = "admin_logs"
    
    admin_user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(100), nullable=False)
    target_type = Column(String(50))  # 'PLANT', 'USER', 'ACCESS'
    target_id = Column(Integer)
    plant_id = Column(Integer, ForeignKey('plants_registry.id'))
    details = Column(Text)  # JSON string
    
    __table_args__ = (
        Index('idx_admin_logs_admin_user', 'admin_user_id'),
        Index('idx_admin_logs_created_at', 'created_at'),
        Index('idx_admin_logs_plant', 'plant_id'),
    )
    
    # Relationships
    admin_user = relationship("User", back_populates="admin_logs")
    plant = relationship("PlantsRegistry", back_populates="admin_logs")
    
    def __repr__(self):
        return f"<AdminLogs(id={self.id}, action={self.action}, admin_user_id={self.admin_user_id})>"

class PlantSchemaVersion(CentralBase, BaseModel):
    """Schema Version Tracking for Each Plant - Central Database Only"""
    __tablename__ = "plant_schema_versions"
    
    plant_id = Column(Integer, ForeignKey('plants_registry.id'), nullable=False)
    schema_version = Column(String(20), nullable=False)
    migration_applied_at = Column(DateTime, default=datetime.now)
    migration_status = Column(String(20), default='SUCCESS')  # SUCCESS, FAILED, PENDING
    migration_details = Column(Text)
    
    __table_args__ = (
        Index('idx_plant_schema_versions_plant', 'plant_id'),
        Index('idx_plant_schema_versions_status', 'migration_status'),
    )
    
    # Relationships
    plant = relationship("PlantsRegistry", back_populates="schema_versions")
    
    def __repr__(self):
        return f"<PlantSchemaVersion(id={self.id}, plant_id={self.plant_id}, version={self.schema_version})>"