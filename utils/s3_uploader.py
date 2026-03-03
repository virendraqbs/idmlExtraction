"""
utils/s3_uploader.py — S3 upload helper.

Uses boto3 multipart upload for files > 5 MB and uploads up to 4 images
concurrently. Requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
S3_BUCKET to be set in the environment / config.
"""
from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
from typing import TypedDict

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import config

# Multipart threshold: 5 MB
_MULTIPART_THRESHOLD = 5 * 1024 * 1024
_MAX_WORKERS = 4


class UploadResult(TypedDict):
    imageId: str
    s3Key: str
    s3Url: str


class UploadError(TypedDict):
    imageId: str
    error: str


class S3Uploader:
    def __init__(self) -> None:
        self.bucket = config.S3_BUCKET
        self.client = boto3.client(
            "s3",
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION,
        )

    def upload_file(self, local_path: str, s3_key: str) -> str:
        """Upload a single file (multipart if > 5 MB). Returns the public S3 URL."""
        file_size = os.path.getsize(local_path)
        transfer_config = boto3.s3.transfer.TransferConfig(
            multipart_threshold=_MULTIPART_THRESHOLD,
            multipart_chunksize=_MULTIPART_THRESHOLD,
        )
        self.client.upload_file(
            local_path,
            self.bucket,
            s3_key,
            Config=transfer_config,
        )
        return f"https://{self.bucket}.s3.amazonaws.com/{s3_key}"

    def upload_batch(
        self,
        items: list[dict],  # each: {"imageId": str, "localPath": str, "s3Key": str}
    ) -> tuple[list[UploadResult], list[UploadError]]:
        """Upload items in parallel (up to _MAX_WORKERS at a time)."""
        uploaded: list[UploadResult] = []
        errors: list[UploadError] = []

        def _upload_one(item: dict):
            image_id = item["imageId"]
            local_path = item["localPath"]
            s3_key = item["s3Key"]
            if not Path(local_path).exists():
                return None, {"imageId": image_id, "error": "File not found on disk"}
            try:
                url = self.upload_file(local_path, s3_key)
                return {"imageId": image_id, "s3Key": s3_key, "s3Url": url}, None
            except (BotoCoreError, ClientError, OSError) as exc:
                return None, {"imageId": image_id, "error": str(exc)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_upload_one, item): item for item in items}
            for future in concurrent.futures.as_completed(futures):
                ok, err = future.result()
                if ok:
                    uploaded.append(ok)
                else:
                    errors.append(err)

        return uploaded, errors
