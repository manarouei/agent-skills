import boto3
from pathlib import Path
from typing import BinaryIO, Optional
from fastapi import UploadFile

class FileStorageService:
    def __init__(self, storage_type: str = "local", **kwargs):
        self.storage_type = storage_type
        if storage_type == "s3":
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=kwargs.get('aws_access_key_id'),
                aws_secret_access_key=kwargs.get('aws_secret_access_key')
            )
            self.bucket = kwargs.get('bucket')
        else:
            self.base_path = Path(kwargs.get('base_path', '/tmp/n8n-files'))
            self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file: UploadFile, path: str) -> str:
        if self.storage_type == "s3":
            await self.s3_client.upload_fileobj(file.file, self.bucket, path)
            return f"s3://{self.bucket}/{path}"
        else:
            file_path = self.base_path / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(await file.read())
            return str(file_path)

    async def get_file(self, path: str) -> BinaryIO:
        if self.storage_type == "s3":
            response = await self.s3_client.get_object(Bucket=self.bucket, Key=path)
            return response['Body']
        else:
            return open(self.base_path / path, "rb")
