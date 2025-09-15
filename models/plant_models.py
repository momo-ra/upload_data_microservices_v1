from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, PrimaryKeyConstraint, Index, Table, Boolean, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from sqlalchemy.sql import func
from typing import Dict, Any
from sqlalchemy.dialects.postgresql import JSON

PlantBase = declarative_base()

class BaseModel(object):
    """Base model with common attributes and methods"""
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# Association table for many-to-many relationship between CardData and Tag
card_data_tags = Table(
    'card_data_tags',
    PlantBase.metadata,
    Column('card_data_id', Integer, ForeignKey('card_data.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True),
    Index('idx_card_data_tags_card_id', 'card_data_id'),
    Index('idx_card_data_tags_tag_id', 'tag_id')
)

# =============================================================================
# PLANT-LEVEL PERMISSIONS (Plant-specific roles and permissions)
# =============================================================================

class PlantRole(PlantBase, BaseModel):
    """Plant-Level Roles - Plant Database Only"""
    __tablename__ = "plant_roles"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    __table_args__ = (
        Index('idx_plant_roles_name', 'name'),
    )

    # Relationships
    permissions = relationship("PlantRolePermission", back_populates="role", cascade="all, delete-orphan")
    workspace_members = relationship("WorkspaceMembers", back_populates="plant_role")

    def __repr__(self):
        return f"<PlantRole(id={self.id}, name={self.name})>"

class PlantPermission(PlantBase, BaseModel):
    """Plant-Level Permissions - Plant Database Only"""
    __tablename__ = "plant_permissions"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    __table_args__ = (
        Index('idx_plant_permissions_name', 'name'),
    )

    # Relationships
    roles = relationship("PlantRolePermission", back_populates="permission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PlantPermission(id={self.id}, name={self.name})>"

class PlantRolePermission(PlantBase, BaseModel):
    """Plant Role-Permission Mapping - Plant Database Only"""
    __tablename__ = "plant_role_permissions"

    role_id = Column(Integer, ForeignKey('plant_roles.id'), nullable=False)
    permission_id = Column(Integer, ForeignKey('plant_permissions.id'), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_plant_role_permission'),
        Index('idx_plant_role_permission_role_id', 'role_id'),
        Index('idx_plant_role_permission_permission_id', 'permission_id'),
    )

    # Relationships
    role = relationship("PlantRole", back_populates="permissions")
    permission = relationship("PlantPermission", back_populates="roles")
    
    def __repr__(self):
        return f"<PlantRolePermission(id={self.id}, role_id={self.role_id}, permission_id={self.permission_id})>"

# =============================================================================
# WORKSPACES (Plant-scoped)
# =============================================================================

class Workspace(PlantBase, BaseModel):
    """Workspaces - Plant Database Only"""
    __tablename__ = "workspaces"
    
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    owner_id = Column(Integer, nullable=False)  # References users.id from central DB (no FK constraint)
    owner_name = Column(String, nullable=True)  # Cache for display
    plant_id = Column(Integer, nullable=False)  # Plant reference for cross-database operations
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_workspaces_owner_id', 'owner_id'),
        Index('idx_workspaces_plant_id', 'plant_id'),
        Index('idx_workspaces_is_active', 'is_active'),
    )
    
    # Relationships
    members = relationship("WorkspaceMembers", back_populates="workspace", cascade="all, delete-orphan")
    cards = relationship("CardData", back_populates="workspace", cascade="all, delete-orphan")
    alerts = relationship("Alerts", back_populates="workspace", cascade="all, delete-orphan")
    alerting_formulas = relationship("AlertingFormula", back_populates="workspace", cascade="all, delete-orphan")
    subscription_tasks = relationship("SubscriptionTasks", back_populates="workspace", cascade="all, delete-orphan")
    alerting_data = relationship("AlertingData", back_populates="workspace", cascade="all, delete-orphan")
    layouts = relationship("Layout", back_populates="workspace", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Workspace(id={self.id}, name={self.name}, plant_id={self.plant_id})>"

class WorkspaceMembers(PlantBase, BaseModel):
    """Workspace Members - Plant Database Only"""
    __tablename__ = "workspace_members"
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(Integer, nullable=False)  # References users.id from central DB (no FK constraint)
    user_name = Column(String, nullable=True)  # Cache for display
    plant_role_id = Column(Integer, ForeignKey("plant_roles.id"), nullable=False)
    invited_by = Column(Integer, nullable=False)  # References users.id from central DB
    joined_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_members_workspace_user'),
        Index('idx_workspace_members_workspace_id', 'workspace_id'),
        Index('idx_workspace_members_user_id', 'user_id'),
        Index('idx_workspace_members_plant_role_id', 'plant_role_id'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    plant_role = relationship("PlantRole", back_populates="workspace_members")
    
    def __repr__(self):
        return f"<WorkspaceMembers(id={self.id}, workspace_id={self.workspace_id}, user_id={self.user_id})>"

# =============================================================================
# PLANT-LEVEL SHARED RESOURCES (No workspace_id)
# =============================================================================

class Tag(PlantBase, BaseModel):
    """Tags - Plant Database, Shared Across Workspaces"""
    __tablename__ = "tags"
    
    name = Column(String, nullable=False, unique=True)
    connection_string = Column(String, nullable=True)
    description = Column(String, nullable=True)
    unit_of_measure = Column(String, nullable=True)
    plant_id = Column(Integer, nullable=False)  # Plant reference for cross-database operations
    is_active = Column(Boolean, default=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    
    __table_args__ = (
        Index('idx_tags_name', 'name'),
        Index('idx_tags_plant_id', 'plant_id'),
        Index('idx_tags_is_active', 'is_active'),
        Index('idx_tags_data_source_id', 'data_source_id'),
    )
    
    # Relationships
    subscriptions = relationship("SubscriptionTasks", back_populates="tag", cascade="all, delete-orphan")
    cards = relationship("CardData", secondary=card_data_tags, back_populates="tags")
    time_series = relationship("TimeSeries", back_populates="tag", cascade="all, delete-orphan")
    alerts = relationship("Alerts", back_populates="tag", cascade="all, delete-orphan")
    polling_tasks = relationship("PollingTasks", back_populates="tag", cascade="all, delete-orphan")
    alerting_formulas_tag1 = relationship("AlertingFormula", foreign_keys="AlertingFormula.tag_1", back_populates="tag_1_ref")
    alerting_formulas_tag2 = relationship("AlertingFormula", foreign_keys="AlertingFormula.tag_2", back_populates="tag_2_ref")
    data_source = relationship("DataSource", back_populates="tags")
    
    def __repr__(self):
        return f"<Tag(id={self.id}, name={self.name}, plant_id={self.plant_id})>"

class GraphType(PlantBase, BaseModel):
    """Graph Types - Plant Database, Shared Configuration"""
    __tablename__ = "graph_types"
    
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=False)
    
    __table_args__ = (
        Index('idx_graph_types_name', 'name'),
    )
    
    # Relationships
    cards = relationship("CardData", back_populates="graph_type")
    
    def __repr__(self):
        return f"<GraphType(id={self.id}, name={self.name})>"

class MathOperation(PlantBase, BaseModel):
    """Math Operations - Plant Database, Shared Configuration"""
    __tablename__ = "math_operations"

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    operator = Column(String, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('name', 'operator', name="uq_math_operation_name_operator"),
        Index('idx_math_operations_name', 'name'),
        Index('idx_math_operations_operator', 'operator'),
    )
    
    # Relationships
    alerting_formulas = relationship("AlertingFormula", back_populates="math_operation")
    
    def __repr__(self):
        return f"<MathOperation(id={self.id}, name={self.name}, operator={self.operator})>"

# =============================================================================
# AI CHAT SYSTEM (Plant-wide, no workspace restriction)
# =============================================================================

class ChatSession(PlantBase, BaseModel):
    """Chat Sessions - Plant Database, Plant-wide AI Access"""
    __tablename__ = 'chat_sessions'
    
    session_id = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, nullable=False)  # References users.id from central DB (no FK constraint)
    user_name = Column(String, nullable=True)  # Cache for display
    
    __table_args__ = (
        Index('idx_chat_sessions_user_id', 'user_id'),
        Index('idx_chat_sessions_session_id', 'session_id'),
    )
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id={self.session_id}, user_id={self.user_id})>"

class ChatMessage(PlantBase, BaseModel):
    """Chat Messages - Plant Database, Plant-wide AI Access"""
    __tablename__ = 'chat_messages'
    
    session_id = Column(String, ForeignKey('chat_sessions.session_id'), nullable=False)
    user_id = Column(Integer, nullable=False)  # References users.id from central DB (no FK constraint)
    message = Column(Text, nullable=False)
    query = Column(String, nullable=True)
    response = Column(String, nullable=True)
    execution_time = Column(Float, nullable=True)
    is_from_user = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_chat_messages_session_id', 'session_id'),
        Index('idx_chat_messages_user_id', 'user_id'),
        Index('idx_chat_messages_created_at', 'created_at'),
        Index('idx_chat_messages_is_from_user', 'is_from_user'),
    )
    
    # Relationship
    session = relationship("ChatSession", back_populates="messages")
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session_id={self.session_id})>"

# =============================================================================
# WORKSPACE-SCOPED OPERATIONAL DATA
# =============================================================================

class TimeSeries(PlantBase):
    """Time Series - Plant Database, Plant-wide"""
    __tablename__ = "time_series"
    
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    value = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    quality = Column(String(20), default='GOOD')  # Data quality indicator

    # Composite primary key
    __table_args__ = (
        PrimaryKeyConstraint('tag_id', 'timestamp'),
        Index('idx_time_series_tag', 'tag_id'),
        Index('idx_time_series_timestamp', 'timestamp'),
        Index('idx_time_series_frequency', 'frequency', 'timestamp'),
    )
    
    # Relationships
    tag = relationship("Tag", back_populates="time_series")
    
    def __repr__(self):
        return f"<TimeSeries(tag_id={self.tag_id}, timestamp={self.timestamp}, value={self.value})>"

class CardData(PlantBase, BaseModel):
    """Card Data - Plant Database, Workspace-Scoped"""
    __tablename__ = "card_data"

    workspace_id = Column(Integer, ForeignKey('workspaces.id'), nullable=False)
    user_id = Column(Integer, nullable=False)  # References users.id from central DB (no FK constraint)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_active = Column(Boolean, nullable=False)
    graph_type_id = Column(Integer, ForeignKey('graph_types.id'), nullable=False)
    
    __table_args__ = (
        Index('idx_card_data_workspace_id', 'workspace_id'),
        Index('idx_card_data_user_id', 'user_id'),
        Index('idx_card_data_graph_type_id', 'graph_type_id'),
        Index('idx_card_data_time_range', 'start_time', 'end_time'),
    )
    
    # Relationships
    tags = relationship("Tag", secondary=card_data_tags, back_populates="cards")
    workspace = relationship("Workspace", back_populates="cards")
    graph_type = relationship("GraphType", back_populates="cards")

    def __repr__(self):
        return f"<CardData(id={self.id}, workspace_id={self.workspace_id}, user_id={self.user_id})>"

class Alerts(PlantBase, BaseModel):
    """Alerts - Plant Database, Workspace-Scoped"""
    __tablename__ = "alerts"
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    message = Column(String, nullable=False)
    severity = Column(String, nullable=True)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, nullable=True)  # References users.id from central DB
    acknowledged_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_alerts_workspace_id', 'workspace_id'),
        Index('idx_alerts_tag_id', 'tag_id'),
        Index('idx_alerts_timestamp', 'timestamp'),
        Index('idx_alerts_severity', 'severity'),
        Index('idx_alerts_acknowledged', 'is_acknowledged'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="alerts")
    tag = relationship("Tag", back_populates="alerts")
    
    def __repr__(self):
        return f"<Alert(id={self.id}, workspace_id={self.workspace_id}, tag_id={self.tag_id}, severity={self.severity})>"

class AlertingFormula(PlantBase, BaseModel):
    """Alerting Formulas - Plant Database, Workspace-Scoped"""
    __tablename__ = "alerting_formulas"

    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    tag_1 = Column(Integer, ForeignKey("tags.id"), nullable=False)
    tag_2 = Column(Integer, ForeignKey("tags.id"), nullable=True)
    math_operation_id = Column(Integer, ForeignKey("math_operations.id"), nullable=False)
    threshold = Column(Float, nullable=True)
    bucket_size = Column(Integer, nullable=False)
    time_window = Column(Integer, nullable=False)  # in seconds
    is_active = Column(Boolean, default=True)
    frequency = Column(Integer, nullable=False)  # in seconds  
    last_check_time = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_alerting_formulas_workspace_id', 'workspace_id'),
        Index('idx_alerting_formulas_tag_1', 'tag_1'),
        Index('idx_alerting_formulas_tag_2', 'tag_2'),
        Index('idx_alerting_formulas_math_operation_id', 'math_operation_id'),
        Index('idx_alerting_formulas_is_active', 'is_active'),
        Index('idx_alerting_formulas_last_check_time', 'last_check_time'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="alerting_formulas")
    tag_1_ref = relationship("Tag", foreign_keys=[tag_1], back_populates="alerting_formulas_tag1")
    tag_2_ref = relationship("Tag", foreign_keys=[tag_2], back_populates="alerting_formulas_tag2")
    math_operation = relationship("MathOperation", back_populates="alerting_formulas")
    alerting_data = relationship("AlertingData", back_populates="formula", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AlertingFormula(id={self.id}, workspace_id={self.workspace_id}, name={self.name})>"

class AlertingData(PlantBase, BaseModel):
    """Alerting Data - Plant Database, Workspace-Scoped"""
    __tablename__ = "alerting_data"

    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    formula_id = Column(Integer, ForeignKey("alerting_formulas.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    message = Column(Text, nullable=True)
    start_condition_time = Column(DateTime, nullable=True)
    end_condition_time = Column(DateTime, nullable=True)
    fingerprint = Column(String(64), nullable=True)
    
    __table_args__ = (
        Index('idx_alerting_data_workspace_id', 'workspace_id'),
        Index('idx_alerting_data_formula_id', 'formula_id'),
        Index('idx_alerting_data_timestamp', 'timestamp'),
        Index('idx_alerting_data_fingerprint', 'fingerprint'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="alerting_data")
    formula = relationship("AlertingFormula", back_populates="alerting_data")
    
    def __repr__(self):
        return f"<AlertingData(id={self.id}, workspace_id={self.workspace_id}, formula_id={self.formula_id})>"

class PollingTasks(PlantBase, BaseModel):
    """Polling Tasks - Plant Database, Plant-wide"""
    __tablename__ = "polling_tasks"
    
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    time_interval = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_polled = Column(DateTime, nullable=True)
    next_polled = Column(DateTime, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('tag_id', 'time_interval', name='uq_polling_tasks_tag_interval'),
        Index('idx_polling_tasks_tag_id', 'tag_id'),
        Index('idx_polling_tasks_next_polled', 'next_polled'),
        Index('idx_polling_tasks_is_active', 'is_active'),
    )
    
    # Relationships
    tag = relationship("Tag", back_populates="polling_tasks")
    
    def __repr__(self):
        return f"<PollingTasks(id={self.id}, tag_id={self.tag_id})>"

class SubscriptionTasks(PlantBase, BaseModel):
    """Subscription Tasks - Plant Database, Workspace-Scoped"""
    __tablename__ = "subscription_tasks"
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        Index('idx_subscription_tasks_workspace_id', 'workspace_id'),
        Index('idx_subscription_tasks_tag_id', 'tag_id'),
        Index('idx_subscription_tasks_is_active', 'is_active'),
    )
    
    # Relationships
    workspace = relationship("Workspace", back_populates="subscription_tasks")
    tag = relationship("Tag", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<SubscriptionTasks(id={self.id}, workspace_id={self.workspace_id}, tag_id={self.tag_id})>"

# =============================================================================
# SCHEMA VERSION TRACKING
# =============================================================================

class SchemaVersion(PlantBase, BaseModel):
    """Schema Version Tracking - Plant Database"""
    __tablename__ = "schema_version"
    
    version = Column(String(20), nullable=False)
    migration_file = Column(String, nullable=True)
    checksum = Column(String(64), nullable=True)
    applied_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<SchemaVersion(id={self.id}, version={self.version})>"
    
# =============================================================================
# DATA SOURCES (Plant-wide, no workspace restriction)
# =============================================================================

class DataSource(PlantBase, BaseModel):
    """Data Sources - Plant Database, Plant-wide"""
    __tablename__ = "data_sources"
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type_id = Column(Integer, ForeignKey("data_source_types.id"), nullable=False)
    plant_id = Column(Integer, nullable=False)
    connection_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_data_sources_name', 'name'),
        Index('idx_data_sources_type_id', 'type_id'),
        Index('idx_data_sources_plant_id', 'plant_id'),
        Index('idx_data_sources_is_active', 'is_active'),
    )
    
    # Relationships
    data_source_type = relationship("DataSourceType", back_populates="data_sources")
    tags = relationship("Tag", back_populates="data_source", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DataSource(id={self.id}, name={self.name}, type_id={self.type_id}, plant_id={self.plant_id})>"

class DataSourceType(PlantBase, BaseModel):
    """Data Source Types - Plant Database, Plant-wide"""
    __tablename__ = "data_source_types"
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_data_source_types_name', 'name'),
        Index('idx_data_source_types_is_active', 'is_active'),
    )
    
    # Relationships
    data_sources = relationship("DataSource", back_populates="data_source_type", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DataSourceType(id={self.id}, name={self.name})>"


# =============================================================================
# HIERARCHY CONFIGURATION (Plant-wide, no workspace restriction)
# =============================================================================

class HierarchyConfig(PlantBase, BaseModel):
    """Hierarchy Configuration - Plant Database Only"""
    __tablename__ = 'hierarchy_config'
    
    label = Column(String, nullable=False)
    path = Column(String, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    parent_label = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    icon = Column(String, nullable=True, default='file')
    
    __table_args__ = (
        Index('idx_hierarchy_config_label', 'label'),
        Index('idx_hierarchy_config_path', 'path'),
        Index('idx_hierarchy_config_parent_label', 'parent_label'),
        Index('idx_hierarchy_config_is_active', 'is_active'),
        Index('idx_hierarchy_config_icon', 'icon'),
        # Composite unique constraint: label + path must be unique together
        UniqueConstraint('label', 'path', name='uq_hierarchy_config_label_path'),
    )
    
    def __repr__(self):
        return f"<HierarchyConfig(label={self.label}, path={self.path}, display_order={self.display_order}, icon={self.icon})>"
    
class CustomView(PlantBase, BaseModel):
    """Custom View - Plant Database Only"""
    __tablename__ = 'custom_views'
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_favorite = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True)  # Array of tags
    filter_config = Column(JSON, nullable=False)  # The advanced filter configuration
    results = Column(JSON, nullable=False)  # The actual nodes/relationships data
    created_by = Column(Integer, nullable=False)  # User who created the view
    
    __table_args__ = (
        Index('idx_custom_views_favorite', 'is_favorite'),
        Index('idx_custom_views_created_by', 'created_by'),
        Index('idx_custom_views_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<CustomView(id={self.id}, name={self.name})>"
    
    
# =============================================================================
# LAYOUT PERSISTENCE (Workspace-scoped)
# =============================================================================

class Layout(PlantBase, BaseModel):
    """Persisted React Flow layouts per user/workspace/level - Plant Database, Workspace-Scoped"""
    __tablename__ = "layouts"

    user_id = Column(Integer, nullable=False)  # References users.id from central DB (no FK constraint)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    level = Column(String(100), nullable=False)
    layout_data = Column(JSON, nullable=False)
    version = Column(String(10), nullable=True, default="1.0")

    __table_args__ = (
        UniqueConstraint('user_id', 'workspace_id', 'level', name='uq_layout_user_workspace_level'),
        Index('idx_layouts_lookup', 'user_id', 'workspace_id', 'level'),
        Index('idx_layouts_workspace', 'workspace_id'),
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="layouts")

    def __repr__(self):
        return f"<Layout(id={self.id}, user_id={self.user_id}, workspace_id={self.workspace_id}, level={self.level})>"
    