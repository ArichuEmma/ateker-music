import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # MySQL Database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or         "mysql+pymysql://root@localhost/ateker_music"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # File Uploads
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    UPLOAD_FOLDER_AUDIO = "static/uploads/audio"
    UPLOAD_FOLDER_COVERS = "static/uploads/covers"
    UPLOAD_FOLDER_AVATARS = "static/uploads/avatars"

    # Private local staging area for song uploads awaiting admin review.
    # NOT inside static/, so it's never web-accessible directly - only the
    # admin-only preview route can read these files. Files here are moved
    # to R2 only once an admin approves the song.
    PENDING_UPLOAD_FOLDER = os.environ.get(
        "PENDING_UPLOAD_FOLDER",
        os.path.join(os.path.abspath(os.path.dirname(__file__)), "instance", "pending_uploads")
    )

    # Cloudflare R2 (S3-compatible object storage)
    # Songs, cover art, and avatars are uploaded here instead of local disk.
    R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
    # Public base URL for the bucket — either the r2.dev subdomain Cloudflare
    # gives you, or a custom domain you've mapped to the bucket. No trailing slash.
    R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")

    # Allowed extensions
    ALLOWED_AUDIO = {"mp3", "wav", "ogg", "m4a", "flac"}
    ALLOWED_IMAGES = {"jpg", "jpeg", "png", "webp", "gif"}
    MAX_AUDIO_SIZE = 50 * 1024 * 1024   # 50MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024    # 5MB

    # Email
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
    CONTACT_RECIPIENT_EMAIL = os.environ.get("CONTACT_RECIPIENT_EMAIL") or os.environ.get("MAIL_DEFAULT_SENDER")

    # URLs
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5000")

    # Security
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True          # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
