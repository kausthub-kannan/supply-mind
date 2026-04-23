import boto3
import os
from botocore.client import Config
from botocore.exceptions import ClientError

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


if __name__ == "__main__":
    import uuid

    test_bucket = os.getenv("REPORT_BUCKET", "inventory-optimization-reports")
    test_key = f"test/{uuid.uuid4()}.html"
    test_content = "<h1>Test Report</h1>"

    print("=== MinIO Upload Tests ===\n")

    # Test 1: Create bucket (first time)
    print("Test 1: Create bucket")
    create_bucket(test_bucket)
    s3_client.head_bucket(Bucket=test_bucket)  # raises if doesn't exist
    print(f"  ✓ Bucket '{test_bucket}' exists\n")

    # Test 3: Upload a file
    print("Test 3: Upload file")
    upload_file(test_key, test_content)
    response = s3_client.head_object(Bucket=test_bucket, Key=test_key)
    assert response["ContentType"] == "text/html", "Content-Type mismatch"
    print(f"  ✓ Uploaded '{test_key}'\n")

    # Test 4: Verify content
    print("Test 4: Verify content")
    obj = s3_client.get_object(Bucket=test_bucket, Key=test_key)
    body = obj["Body"].read().decode("utf-8")
    assert body == test_content, f"Content mismatch: {body!r}"
    print(f"  ✓ Content matches: {body!r}\n")

    # Test 5: Upload with custom content type
    print("Test 5: Upload JSON content type")
    json_key = f"test/{uuid.uuid4()}.json"
    upload_file(json_key, '{"status": "ok"}', content_type="application/json")
    json_response = s3_client.head_object(Bucket=test_bucket, Key=json_key)
    assert json_response["ContentType"] == "application/json", "Content-Type mismatch"
    print(f"  ✓ JSON file uploaded with correct content type\n")

    # Cleanup
    print("Cleaning up test objects...")
    s3_client.delete_object(Bucket=test_bucket, Key=test_key)
    s3_client.delete_object(Bucket=test_bucket, Key=json_key)
    print("  ✓ Test objects deleted\n")

    print("=== All tests passed ✓ ===")
