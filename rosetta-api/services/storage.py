import os
import json
import boto3
import cachetools
from botocore.exceptions import ClientError
from typing import Dict, Any, List
from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-storage")

# --- Ephemeral report cache (latest full run, in-memory) ---
_REPORTS_DIR = "export/reports"
os.makedirs(_REPORTS_DIR, exist_ok=True)
_RESULT_CACHE = cachetools.TTLCache(maxsize=10, ttl=3600)

def save_report_to_disk(data: list):
    _RESULT_CACHE["latest_full_report"] = data
    if settings.STORAGE_MODE == "memory":
        logger.info("STORAGE_MODE=memory: Skipping saving report to disk.")
        return
    try:
        with open(os.path.join(_REPORTS_DIR, "latest_full_report.json"), "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write report to disk: {e}")

def get_latest_report_path() -> str:
    return os.path.join(_REPORTS_DIR, "latest_full_report.json")

# Mock S3 Storage for local container environments
MOCK_S3_DIR = os.getenv("S3_LOCAL_DIR", "./data/s3_storage_mock")
os.makedirs(MOCK_S3_DIR, exist_ok=True)

from botocore.config import Config

s3_client = None
if settings.STORAGE_MODE == "s3":
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version='s3v4')
    )

def _remove_statevectors(data: Any) -> Any:
    """Recursively remove 'statevector' lists from dictionaries to save storage space."""
    if isinstance(data, dict):
        return {k: _remove_statevectors(v) for k, v in data.items() if k != 'statevector'}
    elif isinstance(data, list):
        return [_remove_statevectors(item) for item in data]
    return data

def save_run_report(user_id: int, run_id: str, report_data: dict) -> str:
    """
    Strips large statevectors from the report data and saves it locally or to S3.
    Returns the file path acting as an S3 object key.
    """
    clean_data = _remove_statevectors(report_data)
    object_key = f"users/{user_id}/runs/{run_id}.json"
    
    if settings.STORAGE_MODE == "s3":
        try:
            s3_client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                s3_client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
        
        json_bytes = json.dumps(clean_data).encode('utf-8')
        
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
            Body=json_bytes,
            ContentLength=len(json_bytes),
            ContentType="application/json"
        )
        return object_key
    else:
        full_path = os.path.join(MOCK_S3_DIR, object_key)
        
        # Ensure nested directories exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(clean_data, f)
            
        return object_key

def fetch_run_report(s3_object_key: str) -> dict:
    """
    Retrieves a JSON report from the local file system or S3 using the key.
    """
    if settings.STORAGE_MODE == "s3":
        try:
            response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_object_key)
            json_data = response['Body'].read().decode('utf-8')
            return json.loads(json_data)
        except ClientError as e:
            raise RuntimeError(f"Failed to fetch run report from S3: {e}")
    else:
        full_path = os.path.join(MOCK_S3_DIR, s3_object_key)
        
        if not os.path.exists(full_path):
            raise RuntimeError(f"Failed to fetch run report: File not found at {full_path}")
            
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)

def delete_run_reports(s3_object_keys: List[str]):
    """
    Deletes a list of JSON reports from S3 or local storage.
    """
    if not s3_object_keys:
        return
        
    if settings.STORAGE_MODE == "s3":
        objects_to_delete = [{'Key': key} for key in s3_object_keys]
        try:
            s3_client.delete_objects(
                Bucket=settings.S3_BUCKET_NAME,
                Delete={'Objects': objects_to_delete}
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to batch delete run reports from S3: {e}")
    else:
        for key in s3_object_keys:
            full_path = os.path.join(MOCK_S3_DIR, key)
            if os.path.exists(full_path):
                os.remove(full_path)
