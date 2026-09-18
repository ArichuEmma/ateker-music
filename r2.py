"""
Cloudflare R2 storage helpers.

R2 is S3-compatible, so we talk to it with boto3's standard S3 client
pointed at the R2 account endpoint. All song audio, cover art, and
artist avatars are uploaded here instead of the local filesystem.
"""
import boto3
from botocore.client import Config as BotoConfig
from flask import current_app


def get_r2_client():
    """Create a boto3 S3 client configured for the Cloudflare R2 endpoint."""
    account_id = current_app.config.get("R2_ACCOUNT_ID")
    if not account_id or not current_app.config.get("R2_ACCESS_KEY_ID") or not current_app.config.get("R2_SECRET_ACCESS_KEY") or not current_app.config.get("R2_BUCKET_NAME"):
        raise RuntimeError(
            "R2 is not configured: check R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME in your .env file."
        )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=current_app.config["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["R2_SECRET_ACCESS_KEY"],
        config=BotoConfig(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=300,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
        region_name="auto",
    )


def upload_bytes_to_r2(data, key, content_type):
    """
    Upload raw bytes to R2 under the given object key.
    Returns the public URL the object can be reached at.
    Objects get a long-lived, immutable cache header: every key is a fresh
    UUID that's never reused or overwritten, so it's always safe for
    browsers/CDNs to cache the response indefinitely.
    """
    client = get_r2_client()
    client.put_object(
        Bucket=current_app.config["R2_BUCKET_NAME"],
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )
    base = current_app.config["R2_PUBLIC_URL"].rstrip("/")
    return f"{base}/{key}"


def extract_r2_key(url_or_key):
    """
    Given either a full public R2 URL (what we store in the DB) or a bare
    object key, return the bare key. Returns None for falsy input.
    """
    if not url_or_key:
        return None
    base = current_app.config["R2_PUBLIC_URL"].rstrip("/") + "/"
    if url_or_key.startswith(base):
        return url_or_key[len(base):]
    if url_or_key.startswith("pending:"):
        # A local staging marker that never reached R2 - nothing to delete there.
        return None
    if url_or_key.startswith("http://") or url_or_key.startswith("https://"):
        # A full URL that doesn't match our configured public base —
        # don't guess, just skip deletion rather than delete the wrong thing.
        return None
    return url_or_key


def delete_from_r2(url_or_key):
    """Delete an object from R2 given its public URL or bare key. Best-effort."""
    key = extract_r2_key(url_or_key)
    if not key:
        return
    client = get_r2_client()
    try:
        client.delete_object(Bucket=current_app.config["R2_BUCKET_NAME"], Key=key)
    except Exception as e:
        current_app.logger.error(f"R2 delete error for key '{key}': {e}")


def presigned_download_url(url_or_key, download_filename, content_type=None, expires_in=60):
    """
    Generate a short-lived presigned GET URL that forces a "Save As" download
    with a friendly filename, regardless of the bucket's default disposition.
    Used for the public download endpoint; playback uses the plain public URL.
    """
    key = extract_r2_key(url_or_key)
    if not key:
        return None
    client = get_r2_client()
    params = {
        "Bucket": current_app.config["R2_BUCKET_NAME"],
        "Key": key,
        "ResponseContentDisposition": f'attachment; filename="{download_filename}"',
    }
    if content_type:
        params["ResponseContentType"] = content_type
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )
