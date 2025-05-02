import logging
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, PrimaryKeyConstraint, Index, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from core.config import settings

Base = declarative_base()

class Tag(Base):
    __tablename__ = "tag"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    unit_of_measure = Column(String, nullable=True)

class TimeSeries(Base):
    __tablename__ = "time_series"
    # شيلنا id column لأننا هنستخدم composite primary key
    tag_id = Column(Integer, ForeignKey("tag.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    value = Column(String, nullable=False)
    frequency = Column(String, nullable=False)

    # عملنا primary key مركب من tag_id و timestamp
    __table_args__ = (
        PrimaryKeyConstraint('tag_id', 'timestamp'),
        Index('idx_time_series_tag_time', 'tag_id', 'timestamp', unique=True),
        Index('idx_time_series_frequency', 'frequency', 'timestamp'),
    )

class Alerts(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_id = Column(Integer, ForeignKey("tag.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    message = Column(String, nullable=False)

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create tables and log the process
# try:
#     Base.metadata.create_all(engine)
#     logging.info("✅ All tables created successfully.")
# except Exception as e:
#     logging.error(f"❌ Error creating tables: {e}")