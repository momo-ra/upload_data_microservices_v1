import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.endpoints import router as file_upload_router
from database import init_db
from utils.log import setup_logger

# Load environment variables
load_dotenv(".env", override=True)

app = FastAPI()
logger = setup_logger(__name__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods including OPTIONS
    allow_headers=["*"],  # Allows all headers
)

# ✅ Run `init_db()` when the application starts
@app.on_event("startup")
async def startup_db_client():
    try:
        await init_db()
        logger.success("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Continue anyway, don't crash the application

app.include_router(file_upload_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)