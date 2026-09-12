import os
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
import boto3
from botocore.config import Config
from ..config import config

class StorageManager:
    """
    Hybrid Cloud Storage Provider supporting:
    1. Cloudflare R2 (10GB Free Tier, $0 Egress fees, S3-Compatible)
    2. AWS S3 / MinIO
    3. Local File System Fallback
    """
    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        public_url: Optional[str] = None
    ):
        self.account_id = account_id or config.r2_account_id
        self.access_key = access_key or config.r2_access_key_id
        self.secret_key = secret_key or config.r2_secret_access_key
        self.bucket_name = bucket_name or config.r2_bucket_name
        self.public_url = public_url or config.r2_public_url
        self._s3_client = None

        if self.is_configured():
            self._init_s3()

    def is_configured(self) -> bool:
        return bool(self.account_id and self.access_key and self.secret_key and self.bucket_name)

    def _init_s3(self):
        try:
            endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(signature_version="s3v4")
            )
            print(f"[StorageManager] Connected to Cloudflare R2: bucket={self.bucket_name}")
        except Exception as e:
            print(f"[StorageManager] Failed to initialize R2 client: {e}")
            self._s3_client = None

    def test_connection(self) -> Tuple[bool, str]:
        """Tests if the provided Cloudflare R2 credentials can list/access the bucket"""
        if not self.is_configured():
            return False, "بيانات الاعتماد غير مكتملة (Missing Account ID, Keys, or Bucket Name)"
        try:
            if not self._s3_client:
                self._init_s3()
            self._s3_client.head_bucket(Bucket=self.bucket_name)
            return True, f"تم الاتصال بنجاح بمستودع Cloudflare R2: {self.bucket_name}"
        except Exception as e:
            return False, f"فشل الاتصال بـ Cloudflare R2: {str(e)}"

    def upload_file(self, local_file_path: Path, remote_key: str) -> str:
        """
        Uploads local video clip or image snapshot to Cloudflare R2.
        Returns the accessible URL (Public CDN / Presigned / Local Static).
        """
        if self._s3_client and self.is_configured() and local_file_path.exists():
            try:
                mime_type, _ = mimetypes.guess_type(str(local_file_path))
                extra_args = {}
                if mime_type:
                    extra_args["ContentType"] = mime_type

                self._s3_client.upload_file(
                    Filename=str(local_file_path),
                    Bucket=self.bucket_name,
                    Key=remote_key,
                    ExtraArgs=extra_args
                )
                print(f"[StorageManager] Uploaded to Cloudflare R2: {remote_key}")

                if self.public_url:
                    base = self.public_url.rstrip('/')
                    return f"{base}/{remote_key}"
                
                # Generate a presigned URL valid for 7 days
                presigned = self._s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': remote_key},
                    ExpiresIn=60 * 60 * 24 * 7
                )
                return presigned
            except Exception as e:
                print(f"[StorageManager] R2 upload failed, falling back to local storage: {e}")

        # Local fallback URL
        filename = local_file_path.name
        return f"/api/alerts/{filename}"

storage_manager = StorageManager()
