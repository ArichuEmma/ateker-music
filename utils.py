import os
import secrets
import uuid
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse, urljoin
from flask import current_app, flash, redirect, url_for, request, abort
from flask_login import current_user
from flask_mail import Message
from PIL import Image
import bleach

# Redirect safety
def is_safe_url(target):
    """
    True only if `target` resolves to a same-origin, http(s) path.
    Used to validate ?next= redirect targets after login so an attacker
    can't craft a link that bounces a freshly-authenticated user to an
    external phishing site.
    """
    if not target:
        return False
    host_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and host_url.netloc == test_url.netloc

# Role decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def artist_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_artist() or current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def verified_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_verified:
            flash("Please verify your email to access this feature.", "warning")
            return redirect(url_for("auth.profile"))
        return f(*args, **kwargs)
    return decorated_function

# Admin audit logging
def log_admin_action(action, target_type=None, target_id=None, details=None):
    """Record a sensitive admin action to the append-only audit trail."""
    from models import db, AdminActionLog
    entry = AdminActionLog(
        admin_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    # Deliberately not committing here - caller commits alongside its own
    # change so the log entry and the action it describes are atomic.

def send_contact_message(name, email, subject, message):
    """
    Send a contact-form submission to the site's contact inbox.
    Strips CR/LF from anything that ends up in an email header (name,
    email, subject) as defense in depth against header injection, even
    though WTForms' Email() validator already rejects malformed addresses.
    """
    clean = lambda s: s.replace("\r", " ").replace("\n", " ").strip()
    name, email, subject = clean(name), clean(email), clean(subject)

    recipient = current_app.config.get("CONTACT_RECIPIENT_EMAIL")
    if not recipient:
        current_app.logger.error("Contact form submitted but CONTACT_RECIPIENT_EMAIL is not configured.")
        return False

    html = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="color:#F26522;">New Contact Form Message</h2>
        <p><strong>From:</strong> {bleach.clean(name)} &lt;{bleach.clean(email)}&gt;</p>
        <p><strong>Subject:</strong> {bleach.clean(subject)}</p>
        <hr>
        <p style="white-space:pre-wrap;">{bleach.clean(message)}</p>
    </div>
    """
    from flask_mail import Message as MailMessage
    from app import mail
    try:
        msg = MailMessage(f"[Contact] {subject}", recipients=[recipient], reply_to=email)
        msg.html = html
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Contact email failed: {e}")
        return False

# Email helpers
def send_email(subject, recipients, body=None, html=None):
    from app import mail
    msg = Message(subject, recipients=[recipients] if isinstance(recipients, str) else recipients)
    msg.body = body
    msg.html = html
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email failed: {e}")
        return False

def send_verification_email(user, token):
    verify_url = f"{current_app.config['FRONTEND_URL']}/auth/verify-email?token={token}"
    html = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="color:#F26522;">Welcome to Ateker Music</h2>
        <p>Hi {user.profile.first_name or 'there'},</p>
        <p>Click the button below to verify your email address:</p>
        <a href="{verify_url}" style="display:inline-block;background:#F26522;color:white;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:bold;">Verify Email</a>
        <p style="margin-top:20px;color:#666;font-size:14px;">Or copy this link:<br>{verify_url}</p>
        <p style="color:#999;font-size:12px;">This link expires in 24 hours.</p>
    </div>
    """
    return send_email("Verify your Ateker Music account", user.email, html=html)

def send_password_reset_email(user, token):
    reset_url = f"{current_app.config['FRONTEND_URL']}/auth/reset-password?token={token}"
    html = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="color:#F26522;">Password Reset Request</h2>
        <p>Hi {user.profile.first_name or 'there'},</p>
        <p>We received a request to reset your password. Click below to proceed:</p>
        <a href="{reset_url}" style="display:inline-block;background:#F26522;color:white;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:bold;">Reset Password</a>
        <p style="margin-top:20px;color:#666;font-size:14px;">This link expires in 1 hour and can only be used once.</p>
        <p style="color:#999;font-size:12px;">If you didn't request this, you can safely ignore this email.</p>
    </div>
    """
    return send_email("Password Reset - Ateker Music", user.email, html=html)

def send_song_status_email(artist_user, song, status, reason=None):
    if status == "APPROVED":
        subject = f'Your song "{song.title}" has been approved'
        html = f"""
        <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
            <h2 style="color:#22c55e;">Song Approved!</h2>
            <p>Congratulations! Your song <strong>{song.title}</strong> has been approved and is now live on Ateker Music.</p>
            <a href="{current_app.config['FRONTEND_URL']}/songs/{song.slug}" style="display:inline-block;background:#F26522;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;">View Song</a>
        </div>
        """
    else:
        subject = f'Your song "{song.title}" was not approved'
        html = f"""
        <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
            <h2 style="color:#ef4444;">Song Not Approved</h2>
            <p>Your song <strong>{song.title}</strong> was not approved for the following reason:</p>
            <blockquote style="border-left:4px solid #F26522;padding-left:12px;color:#555;">{reason}</blockquote>
            <p>You can edit and resubmit it from your artist dashboard.</p>
        </div>
        """
    return send_email(subject, artist_user.email, html=html)

# File handling
def allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set

def looks_like_audio(file_obj):
    """
    Peek at the file's magic bytes to confirm it's actually one of our
    supported audio containers, independent of the filename extension or
    the client-supplied MIME type (both of which an attacker controls).
    This does NOT verify the file is a *valid, playable* file - just that
    it isn't an executable or arbitrary binary wearing a fake extension.
    """
    pos = file_obj.tell()
    file_obj.seek(0)
    header = file_obj.read(16)
    file_obj.seek(pos)

    if len(header) < 4:
        return False
    if header[:3] == b"ID3":                                   # MP3 w/ ID3 tag
        return True
    if header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):  # MP3 frame sync
        return True
    if header[:4] == b"RIFF" and len(header) >= 12 and header[8:12] == b"WAVE":  # WAV
        return True
    if header[:4] == b"OggS":                                  # OGG
        return True
    if header[:4] == b"fLaC":                                  # FLAC
        return True
    if len(header) >= 8 and header[4:8] == b"ftyp":            # M4A/MP4 container
        return True
    return False

def secure_filename_uuid(filename):
    """Generate a secure random filename preserving extension."""
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

def save_upload(file_obj, folder, allowed_set, max_size):
    if not file_obj or file_obj.filename == "":
        return None
    if not allowed_file(file_obj.filename, allowed_set):
        raise ValueError("Invalid file type.")
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > max_size:
        raise ValueError(f"File too large. Max {max_size // (1024*1024)}MB.")

    filename = secure_filename_uuid(file_obj.filename)
    filepath = os.path.join(current_app.root_path, folder, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_obj.save(filepath)
    return filename

def save_and_resize_image(file_obj, folder, width=800, height=800):
    """Save image and create a resized version."""
    filename = save_upload(file_obj, folder, {"jpg", "jpeg", "png", "webp", "gif"}, 5 * 1024 * 1024)
    if not filename:
        return None
    filepath = os.path.join(current_app.root_path, folder, filename)
    try:
        with Image.open(filepath) as img:
            img.thumbnail((width, height), Image.LANCZOS)
            img = img.convert("RGB")
            img.save(filepath, "JPEG", quality=85, optimize=True)
    except Exception as e:
        current_app.logger.error(f"Image resize error: {e}")
    return filename

# --- Cloudflare R2 uploads ---
# These replace the local-disk helpers above for song audio, cover art, and
# avatars. They validate the file the same way save_upload() does, then push
# the bytes straight to R2 instead of the local filesystem, and return the
# full public URL to store in the DB (audio_url / cover_url / avatar_url).

def upload_audio_to_r2(file_obj, artist_id, allowed_set, max_size):
    """Validate and upload a song's audio file to R2. Returns the public URL."""
    from r2 import upload_bytes_to_r2

    if not file_obj or file_obj.filename == "":
        raise ValueError("No audio file provided.")
    if not allowed_file(file_obj.filename, allowed_set):
        raise ValueError("Invalid file type.")
    if not looks_like_audio(file_obj):
        raise ValueError("This file doesn't look like a valid audio file.")

    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > max_size:
        raise ValueError(f"File too large. Max {max_size // (1024 * 1024)}MB.")

    ext = file_obj.filename.rsplit(".", 1)[1].lower()
    key = f"songs/{artist_id}/{uuid.uuid4().hex}.{ext}"
    content_type = file_obj.mimetype or "application/octet-stream"

    url = upload_bytes_to_r2(file_obj.read(), key, content_type)
    return url


def upload_image_to_r2(file_obj, folder, owner_id, width=800, height=800):
    """
    Validate, resize (in memory), and upload an image (cover art or avatar)
    to R2. `folder` is a short prefix like "covers" or "avatars".
    Returns the public URL, or None if no file was provided.
    """
    from io import BytesIO
    from r2 import upload_bytes_to_r2

    if not file_obj or file_obj.filename == "":
        return None
    if not allowed_file(file_obj.filename, {"jpg", "jpeg", "png", "webp", "gif"}):
        raise ValueError("Images only!")

    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > 5 * 1024 * 1024:
        raise ValueError("Image too large. Max 5MB.")

    try:
        img = Image.open(file_obj)
        img.thumbnail((width, height), Image.LANCZOS)
        img = img.convert("RGB")
        buffer = BytesIO()
        img.save(buffer, "JPEG", quality=85, optimize=True)
        buffer.seek(0)
        data = buffer.read()
    except Exception as e:
        current_app.logger.error(f"Image resize error: {e}")
        raise ValueError("Could not process image.")

    key = f"{folder}/{owner_id}/{uuid.uuid4().hex}.jpg"
    url = upload_bytes_to_r2(data, key, "image/jpeg")
    return url

# --- Local staging for songs awaiting admin review ---
# New song uploads are NOT sent to R2 immediately. Instead the audio/cover
# are saved to a private local folder (outside static/, never web-accessible)
# and the DB field is set to a "pending:<relative path>" marker. Only once
# an admin approves the song does promote_pending_file() move it to R2.

PENDING_PREFIX = "pending:"

def stage_audio_locally(file_obj, artist_id, allowed_set, max_size):
    """Validate and save a song's audio file to local private staging. Returns a 'pending:' marker."""
    if not file_obj or file_obj.filename == "":
        raise ValueError("No audio file provided.")
    if not allowed_file(file_obj.filename, allowed_set):
        raise ValueError("Invalid file type.")
    if not looks_like_audio(file_obj):
        raise ValueError("This file doesn't look like a valid audio file.")

    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > max_size:
        raise ValueError(f"File too large. Max {max_size // (1024 * 1024)}MB.")

    ext = file_obj.filename.rsplit(".", 1)[1].lower()
    rel_path = os.path.join("audio", f"{artist_id}_{uuid.uuid4().hex}.{ext}")
    full_path = os.path.join(current_app.config["PENDING_UPLOAD_FOLDER"], rel_path)
    file_obj.save(full_path)
    return f"{PENDING_PREFIX}{rel_path}"


def stage_image_locally(file_obj, folder, owner_id, width=800, height=800):
    """Validate, resize, and save an image (cover art) to local private staging. Returns a 'pending:' marker, or None."""
    if not file_obj or file_obj.filename == "":
        return None
    if not allowed_file(file_obj.filename, {"jpg", "jpeg", "png", "webp", "gif"}):
        raise ValueError("Images only!")

    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > 5 * 1024 * 1024:
        raise ValueError("Image too large. Max 5MB.")

    rel_path = os.path.join(folder, f"{owner_id}_{uuid.uuid4().hex}.jpg")
    full_path = os.path.join(current_app.config["PENDING_UPLOAD_FOLDER"], rel_path)
    try:
        img = Image.open(file_obj)
        img.thumbnail((width, height), Image.LANCZOS)
        img = img.convert("RGB")
        img.save(full_path, "JPEG", quality=85, optimize=True)
    except Exception as e:
        current_app.logger.error(f"Image resize error: {e}")
        raise ValueError("Could not process image.")

    return f"{PENDING_PREFIX}{rel_path}"


def is_pending_local(marker):
    """True if a DB url field currently holds a local staging marker rather than a real R2 URL."""
    return bool(marker) and marker.startswith(PENDING_PREFIX)


def pending_local_path(marker):
    """Resolve a 'pending:' marker to its absolute path on disk."""
    rel_path = marker[len(PENDING_PREFIX):]
    return os.path.join(current_app.config["PENDING_UPLOAD_FOLDER"], rel_path)


def promote_pending_file(marker, artist_id, r2_folder, content_type=None):
    """
    Move a locally-staged file (approved song) to R2. Returns the public R2 URL.
    Deletes the local copy on success. If the marker isn't a local staging
    marker (already an R2 URL), returns it unchanged.
    """
    import mimetypes
    from r2 import upload_bytes_to_r2

    if not is_pending_local(marker):
        return marker

    full_path = pending_local_path(marker)
    if not os.path.exists(full_path):
        raise ValueError("Staged file is missing on the server; ask the artist to re-upload.")

    ext = full_path.rsplit(".", 1)[-1]
    if not content_type:
        content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
    key = f"{r2_folder}/{artist_id}/{uuid.uuid4().hex}.{ext}"
    with open(full_path, "rb") as f:
        url = upload_bytes_to_r2(f.read(), key, content_type)

    try:
        os.remove(full_path)
    except OSError as e:
        current_app.logger.error(f"Could not remove staged file {full_path}: {e}")

    return url


def discard_pending_file(marker):
    """Delete a locally-staged file without ever sending it to R2 (used on song deletion)."""
    if not is_pending_local(marker):
        return
    full_path = pending_local_path(marker)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except OSError as e:
        current_app.logger.error(f"Could not remove staged file {full_path}: {e}")

# Sanitization
def clean_html(text):
    if not text:
        return ""
    allowed_tags = ["p", "br", "strong", "em", "u", "h1", "h2", "h3", "h4", "ul", "ol", "li"]
    allowed_attrs = {}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def generate_slug(text):
    import re
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:200]
