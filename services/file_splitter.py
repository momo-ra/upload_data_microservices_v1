# services/file_splitter.py
import os
import pandas as pd
from utils.log import setup_logger
import uuid

logger = setup_logger(__name__)

class FileSplitter:
    def __init__(self, base_dir="/tmp/chunks"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def split_file(self, file_path, chunk_size=500000):
        """تقسيم الملف الكبير إلى أجزاء صغيرة"""
        try:
            # إنشاء مجلد للملف
            job_id = str(uuid.uuid4())
            job_dir = os.path.join(self.base_dir, job_id)
            os.makedirs(job_dir, exist_ok=True)
            
            file_extension = os.path.splitext(file_path)[1].lower()
            chunk_files = []
            
            if file_extension in ['.csv']:
                # قراءة CSV على دفعات
                for i, chunk in enumerate(pd.read_csv(file_path, chunksize=chunk_size)):
                    chunk_path = os.path.join(job_dir, f"chunk_{i}.csv")
                    chunk.to_csv(chunk_path, index=False)
                    chunk_files.append(chunk_path)
                    logger.info(f"Saved chunk {i+1} with {len(chunk)} rows")
                    
            elif file_extension in ['.xlsx', '.xls']:
                # قراءة Excel
                xls = pd.ExcelFile(file_path)
                sheet_name = xls.sheet_names[0]
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # تقسيم البيانات إلى أجزاء
                total_rows = len(df)
                for i in range(0, total_rows, chunk_size):
                    chunk = df.iloc[i:i+chunk_size]
                    chunk_path = os.path.join(job_dir, f"chunk_{i//chunk_size}.csv")
                    chunk.to_csv(chunk_path, index=False)
                    chunk_files.append(chunk_path)
                    logger.info(f"Saved chunk {i//chunk_size+1} with {len(chunk)} rows")
            
            logger.success(f"✅ Split file into {len(chunk_files)} chunks")
            return job_id, chunk_files
        
        except Exception as e:
            logger.error(f"❌ Error splitting file: {e}")
            raise