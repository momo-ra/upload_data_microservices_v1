from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from models.models import Base

if "DATABASE_URL" in settings.DB_CONFIG:
    DATABASE_URL = settings.DB_CONFIG["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")
else:
    raise KeyError("❌ DATABASE_URL is missing in settings.DB_CONFIG! Check your configuration.")

async_engine = create_async_engine(
    DATABASE_URL,
    future=True,
    # echo=True  # هنا خليناها True عشان نشوف الإيرور بالتفصيل
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    try:
        async with async_engine.begin() as conn:            
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise e
    
async def get_db_external(url:str):
    async_engine_external = create_async_engine(url)
    SessionLocal = sessionmaker(
        bind=async_engine_external,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
