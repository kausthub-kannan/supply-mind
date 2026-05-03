import boto3
import os
from botocore.client import Config
from botocore.exceptions import ClientError

from multi_agents.utils.logger import setup_logger

logger = setup_logger()
s3_client = boto3.client(
    "s3",
    endpoint_url=f"http://localhost:{os.getenv("MINIO_API_PORT")}",
    aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
    aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"),
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def create_bucket(bucket_name):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            raise


def upload_file(key: str, content: str, content_type="text/html"):
    create_bucket(os.getenv("REPORT_BUCKET", "inventory-optimization-reports"))
    s3_client.put_object(
        Bucket=os.getenv("REPORT_BUCKET", "inventory-optimization-reports"),
        Key=key,
        Body=content,
        ContentType=content_type,
    )
