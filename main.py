import os
from dotenv import load_dotenv
from fastapi import FastAPI
from routers.endpoints import router as file_upload_router
from database import init_db
from database import async_engine
from models.models import Base
from utils.db_init import initialize_timescaledb, verify_hypertable
import asyncio
from utils.log import setup_logger

# Load environment variables
load_dotenv(".env", override=True)

app = FastAPI()
logger = setup_logger(__name__)

# ✅ Run `init_db()` when the application starts
@app.on_event("startup")
async def startup_db_client():
    try:
        await init_db()
        await initialize_timescaledb()
        await verify_hypertable()
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        # Continue anyway, don't crash the application

app.include_router(file_upload_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)