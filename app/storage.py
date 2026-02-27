import os
import json

import boto3

S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

if not S3_BUCKET:
    raise RuntimeError("S3_BUCKET is required")

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


def model_prefix(tenant_id: str, project_id: str, model_id: str) -> str:
    return f"tenant/{tenant_id}/project/{project_id}/model/{model_id}"


def put_bytes(key: str, data: bytes, content_type: str):
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def put_json(key: str, payload: dict):
    put_bytes(
        key=key,
        data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
    )


def get_bytes(key: str) -> bytes:
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read()


def presigned_get_url(key: str, expires_in: int = 3600) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )


def original_ifc_key(tenant_id: str, project_id: str, model_id: str) -> str:
    return f"{model_prefix(tenant_id, project_id, model_id)}/original.ifc"


def summary_json_key(tenant_id: str, project_id: str, model_id: str) -> str:
    return f"{model_prefix(tenant_id, project_id, model_id)}/parsed/summary.json"


def export_glb_key(tenant_id: str, project_id: str, model_id: str) -> str:
    return f"{model_prefix(tenant_id, project_id, model_id)}/exports/model.glb"
