"""
Standalone R2 connection test - run this directly to isolate whether the
"connection closed" error is about your R2 config/network, separate from
the Flask app entirely.

Usage (from the project folder, with your venv activated):
    python test_r2_connection.py
"""
import os
import sys
import uuid
from dotenv import load_dotenv

load_dotenv()

required = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print(f"Missing from .env: {', '.join(missing)}")
    sys.exit(1)

import boto3
from botocore.client import Config as BotoConfig

account_id = os.environ["R2_ACCOUNT_ID"]
bucket = os.environ["R2_BUCKET_NAME"]

print(f"Account ID: {account_id}")
print(f"Bucket:     {bucket}")
print(f"Endpoint:   https://{account_id}.r2.cloudflarestorage.com")
print()

client = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    config=BotoConfig(signature_version="s3v4", connect_timeout=10, read_timeout=30, retries={"max_attempts": 1}),
    region_name="auto",
)

print("Step 1: Listing bucket (small request, tests basic connectivity + auth)...")
try:
    resp = client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    print("  OK - connected and authenticated successfully.")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

print()
print("Step 2: Uploading a tiny test file (~1KB, tests PUT specifically)...")
test_key = f"connection-test/{uuid.uuid4().hex}.txt"
try:
    client.put_object(Bucket=bucket, Key=test_key, Body=b"hello from ateker music" * 40, ContentType="text/plain")
    print(f"  OK - uploaded test object: {test_key}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

print()
print("Step 3: Cleaning up test file...")
try:
    client.delete_object(Bucket=bucket, Key=test_key)
    print("  OK - deleted test object.")
except Exception as e:
    print(f"  Cleanup failed (not critical): {e}")

print()
print("ALL TESTS PASSED. R2 connectivity is working fine outside Flask.")
