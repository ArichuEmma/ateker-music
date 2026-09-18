from datetime import datetime, timedelta
import uuid
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import secrets

db = SQLAlchemy()

# Association tables

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("USER", "ARTIST", "ADMIN", name="user_role"), default="USER", nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_suspended = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = db.relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    artist = db.relationship("Artist", back_populates="user", uselist=False, cascade="all, delete-orphan")
    downloads = db.relationship("Download", back_populates="user", lazy="dynamic")
    password_resets = db.relationship("PasswordReset", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "ADMIN"

    def is_artist(self):
        return self.role == "ARTIST"

class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    avatar_url = db.Column(db.String(500))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(200))

    user = db.relationship("User", back_populates="profile")

class Artist(db.Model):
    __tablename__ = "artists"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    stage_name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text)
    genre = db.Column(db.String(100))
    location = db.Column(db.String(200))
    avatar_url = db.Column(db.String(500))
    cover_url = db.Column(db.String(500))
    facebook = db.Column(db.String(500))
    twitter = db.Column(db.String(500))
    instagram = db.Column(db.String(500))
    youtube = db.Column(db.String(500))
    website = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)
    terms_agreed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="artist")
    songs = db.relationship("Song", back_populates="artist", lazy="dynamic", cascade="all, delete-orphan")
    downloads = db.relationship("Download", back_populates="artist", lazy="dynamic")

class Song(db.Model):
    __tablename__ = "songs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artist_id = db.Column(db.String(36), db.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(350), unique=True, nullable=False, index=True)
    genre = db.Column(db.String(100), nullable=False, index=True)
    album = db.Column(db.String(300))
    description = db.Column(db.Text)
    cover_url = db.Column(db.String(500))
    audio_url = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Integer)  # seconds
    file_size = db.Column(db.Integer)  # bytes
    status = db.Column(db.Enum("PENDING", "APPROVED", "REJECTED", name="song_status"), default="PENDING", nullable=False, index=True)
    rejection_reason = db.Column(db.Text)
    download_count = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    artist = db.relationship("Artist", back_populates="songs")
    downloads = db.relationship("Download", back_populates="song", lazy="dynamic", cascade="all, delete-orphan")

class Download(db.Model):
    __tablename__ = "downloads"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    song_id = db.Column(db.String(36), db.ForeignKey("songs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    artist_id = db.Column(db.String(36), db.ForeignKey("artists.id", ondelete="SET NULL"), nullable=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    song = db.relationship("Song", back_populates="downloads")
    user = db.relationship("User", back_populates="downloads")
    artist = db.relationship("Artist", back_populates="downloads")

class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="password_resets")

class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailVerification(db.Model):
    __tablename__ = "email_verifications"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = db.Column(db.String(128), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")

class AdminActionLog(db.Model):
    """
    Audit trail for sensitive admin actions (song approval/rejection/deletion,
    user suspension, etc). Append-only - nothing here should ever be updated
    or deleted by application code.
    """
    __tablename__ = "admin_action_logs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(36), index=True)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    admin = db.relationship("User")
