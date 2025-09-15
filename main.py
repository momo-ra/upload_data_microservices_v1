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
load_dotenv(".env", override=True)

app = FastAPI()
logger = setup_logger(__name__)

# Custom CORS middleware for better file upload handling
class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = JSONResponse(content={"message": "OK"})
        else:
            response = await call_next(request)
        
        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "http://localhost:3039"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Content-Language, Content-Type, Authorization, plant-id, X-Requested-With, Origin, Access-Control-Request-Method, Access-Control-Request-Headers"
        response.headers["Access-Control-Expose-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "600"
        
        return response

# Custom exception handler to ensure all HTTP errors follow our response format
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException and return standardized error response"""
    return JSONResponse(
        status_code=exc.status_code,
        content=fail_response(message=exc.detail)
    )

# Add custom CORS middleware first
app.add_middleware(CustomCORSMiddleware)

# Add standard CORS middleware as backup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3039",
        "http://127.0.0.1:3039",
        "http://localhost:3000",
        "http://172.27.26.127:3000",
        "http://10.10.10.78:3039",  # Add your specific origins
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "plant-id",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
    max_age=600,
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