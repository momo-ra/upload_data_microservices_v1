import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from routers.endpoints import router as file_upload_router
from utils.response import fail_response
from database import init_db
from utils.log import setup_logger

# Load environment variables
load_dotenv("./../.env", override=True)

app = FastAPI()
logger = setup_logger(__name__)

# Custom exception handler to ensure all HTTP errors follow our response format
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException and return standardized error response"""
    return JSONResponse(
        status_code=exc.status_code,
        content=fail_response(message=exc.detail)
    )

# Add standard CORS middleware as backup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ✅ Run `init_db()` when the application starts
@app.on_event("startup")
async def startup_db_client():
    try:
        await init_db()
        logger.success("Database initialization completed successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Continue anyway, don't crash the application

app.include_router(file_upload_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    

    