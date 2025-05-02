# upload_service/services/jobs_client.py
from httpx import AsyncClient
from typing import Optional
from utils.log import setup_logger

logger = setup_logger(__name__)

class JobsClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = AsyncClient(base_url=base_url)

    async def create_job(self, file_path: str, original_filename: str) -> Optional[str]:
        """إنشاء job جديد"""
        try:
            files = {'file': open(file_path, 'rb')}
            response = await self.client.post("/api/v1/jobs/upload", files=files)
            response.raise_for_status()
            return response.json()['id']
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            raise

    async def get_job_status(self, job_id: str) -> dict:
        """الحصول على حالة الـ job"""
        try:
            response = await self.client.get(f"/api/v1/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            raise

    async def make_decision(self, job_id: str, decision: str, frequency: str) -> dict:
        """إرسال قرار بخصوص البيانات المكررة"""
        try:
            data = {
                "decision": decision,
                "frequency": frequency
            }
            response = await self.client.post(f"/api/v1/jobs/{job_id}/decide", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error making decision: {str(e)}")
            raise