import os
from dotenv import load_dotenv
from utils.log import setup_logger

logger = setup_logger(__name__)

# Load environment variables from .env file
load_dotenv('.env', override=True)

class Settings:
    # Central database settings
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME")
    
    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    
    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your_secret_key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    
    # Jobs service settings
    JOBS_SERVICE_URL: str = os.getenv("JOBS_SERVICE_URL", "http://localhost:8001")

    @property
    def CENTRAL_DATABASE_URL(self):
        if not all([self.DB_USER, self.DB_PASSWORD, self.DB_HOST, self.DB_PORT, self.DB_NAME]):
            logger.error("Missing required environment variables for central database")
            raise ValueError("Missing required environment variables for central database")
        logger.success(f"Central database configuration loaded")
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    def get_plant_database_url(self, database_key: str) -> str:
        """Get database URL for a specific plant using its database key"""
        db_user = os.getenv(f"{database_key}_USER")
        db_password = os.getenv(f"{database_key}_PASSWORD")
        db_host = os.getenv(f"{database_key}_HOST")
        db_port = os.getenv(f"{database_key}_PORT", "5432")
        db_name = os.getenv(f"{database_key}_NAME")
        
        if not all([db_user, db_password, db_host, db_port, db_name]):
            logger.error(f"Missing required environment variables for plant database: {database_key}")
            raise ValueError(f"Missing required environment variables for plant database: {database_key}")
        
        logger.success(f"Plant database configuration loaded for {database_key}")
        return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
settings = Settings()