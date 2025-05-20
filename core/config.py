import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('.env', override=True)

class Settings:
    DB_USER: str = os.getenv("DB_USER")  # Match .env
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME")
    SSL_MODE: str = os.getenv("SSL_MODE", "require")  # Optional
    DB_DRIVER: str = os.getenv("DB_DRIVER", "asyncpg")  # اختيار المحرك
    JOBS_SERVICE_URL: str = os.getenv("JOBS_SERVICE_URL")
    @property
    def DATABASE_URL(self):
        if not all([self.DB_USER, self.DB_PASSWORD, self.DB_HOST, self.DB_PORT, self.DB_NAME]):
            raise ValueError("❌ Missing database configuration in .env file")

        # ✅ إزالة `sslmode` إذا كان `asyncpg` مستخدمًا
        if self.DB_DRIVER == "asyncpg":
            return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?sslmode={self.SSL_MODE}"

    @property
    def DB_CONFIG(self):
        required_fields = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]
        if not all(getattr(self, field) for field in required_fields):
            raise ValueError("❌ Missing database configuration in .env file")

        return {
            "dbname": self.DB_NAME,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "host": self.DB_HOST,
            "port": self.DB_PORT,
            "DATABASE_URL": self.DATABASE_URL,  # ✅ أضف DATABASE_URL هنا بدون `sslmode`
        }

settings = Settings()