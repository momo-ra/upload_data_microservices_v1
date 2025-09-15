# upload_service/services/jobs_client.py
from httpx import AsyncClient
from typing import Optional, Dict, Any
from utils.log import setup_logger

logger = setup_logger(__name__)

class JobsClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = AsyncClient(base_url=base_url)

    async def create_job(self, file_path: str, original_filename: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """إنشاء job جديد"""
        file_handle = None
        try:
            file_handle = open(file_path, 'rb')
            files = {'file': file_handle}
            data = {}
            if metadata:
                # Ensure metadata is JSON serializable
                import json
                try:
                    # Test if metadata is JSON serializable
                    json.dumps(metadata)
                    data['metadata'] = json.dumps(metadata)  # Convert to JSON string
                except (TypeError, ValueError) as json_error:
                    logger.error(f"Metadata not JSON serializable: {json_error}")
                    # Create a simplified metadata structure
                    data['metadata'] = json.dumps({
                        "frequency": metadata.get("frequency", "unknown"),
                        "plant_id": metadata.get("plant_id", "unknown"),
                        "duplicates": "found" if metadata.get("duplicates") else "none"
                    })
            response = await self.client.post("/api/v1/jobs/upload", files=files, data=data)
            response.raise_for_status()
            return response.json()['id']
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            raise
        finally:
            if file_handle:
                file_handle.close()

    async def get_job_status(self, job_id: str) -> dict:
        """الحصول على حالة الـ job"""
        try:
            response = await self.client.get(f"/api/v1/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            raise

    async def make_decision(self, job_id: str, decision: str, frequency: str = None) -> dict:
        """إرسال قرار بخصوص البيانات المكررة"""
        try:
            data = {
                "decision": decision
            }
            if frequency:
                data["frequency"] = frequency
            response = await self.client.post(f"/api/v1/jobs/{job_id}/decide", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error making decision: {str(e)}")
            raise