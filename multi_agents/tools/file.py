import boto3
import os

from langchain.tools import tool

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("MINIO_PASSWORD"),
    region_name="us-east-1",
)


@tool(description="A tool to upload files to S3")
def upload_file(key: str, content: str, content_type="text/html"):
    """
    Tool used to upload HTML or text file to S3 bucket
    :param key: str - The file name or key
    :param content: str - The data or bytes of the file
    :param content_type: str - Type of content to be saved, by default text/html
    """
    s3_client.put_object(
        Bucket=os.getenv("REPORT_BUCKET"),
        Key=key,
        Body=content,
        ContentType=content_type,
    )


# import boto3
# import os
#
# s3_client = boto3.client(
#     's3',
#     endpoint_url=os.getenv("MINIO_ENDPOINT"),
#     aws_access_key_id=os.getenv("MINIO_ACCESS_KEY_ID"),
#     aws_secret_access_key=os.getenv("MINIO_PASSWORD"),
#     region_name='us-east-1'
# )
# s3_client.create_bucket(Bucket=os.getenv("REPORT_BUCKET"))
