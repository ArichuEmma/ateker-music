import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required
from sqlalchemy import func
from models import db, User, Artist, Song, Download, Profile
from forms import SongReviewForm
from utils import admin_required, send_song_status_email, discard_pending_file, promote_pending_file, log_admin_action
from r2 import delete_from_r2

bp = Blueprint("admin", __name__)

@bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "total_artists": Artist.query.count(),
        "total_songs": Song.query.count(),
        "pending_songs": Song.query.filter_by(status="PENDING").count(),
        "approved_songs": Song.query.filter_by(status="APPROVED").count(),
        "rejected_songs": Song.query.filter_by(status="REJECTED").count(),
        "total_downloads": db.session.query(func.sum(Song.download_count)).scalar() or 0,
    }
    recent_downloads = Download.query.order_by(Download.created_at.desc()).limit(10).all()
    pending_songs = Song.query.filter_by(status="PENDING").order_by(Song.created_at.asc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, recent_downloads=recent_downloads, pending_songs=pending_songs)

@bp.route("/users")
@login_required
@admin_required
def manage_users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")
    query = User.query
    if search:
        query = query.join(Profile).filter(
            db.or_(
                User.email.ilike(f"%{search}%"),
                Profile.first_name.ilike(f"%{search}%"),
                Profile.last_name.ilike(f"%{search}%")
            )
        )
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/users.html", pagination=pagination, search=search)

@bp.route("/users/<user_id>/suspend", methods=["POST"])
@login_required
@admin_required
def suspend_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_suspended = not user.is_suspended
    log_admin_action(
        "suspend_user" if user.is_suspended else "unsuspend_user",
        target_type="User", target_id=user.id, details=user.email
    )
    db.session.commit()
    flash(f"User {'suspended' if user.is_suspended else 'unsuspended'}.", "success")
    return redirect(url_for("admin.manage_users"))

@bp.route("/artists")
@login_required
@admin_required
def manage_artists():
    page = request.args.get("page", 1, type=int)
    pagination = Artist.query.order_by(Artist.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/artists.html", pagination=pagination)

@bp.route("/pending-songs")
@login_required
@admin_required
def pending_songs():
    page = request.args.get("page", 1, type=int)
    pagination = Song.query.filter_by(status="PENDING").order_by(Song.created_at.asc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/pending_songs.html", pagination=pagination)

@bp.route("/songs/<song_id>/review", methods=["GET", "POST"])
@login_required
@admin_required
def review_song(song_id):
    song = Song.query.get_or_404(song_id)
    form = SongReviewForm()
    if form.validate_on_submit():
        new_status = form.status.data

        if new_status == "APPROVED":
            # Only now do the files actually get uploaded to R2
            try:
                song.audio_url = promote_pending_file(song.audio_url, song.artist_id, "songs")
                if song.cover_url:
                    song.cover_url = promote_pending_file(song.cover_url, song.artist_id, "covers", "image/jpeg")
            except ValueError as e:
                flash(str(e), "error")
                return render_template("admin/review_song.html", song=song, form=form)
            except Exception as e:
                current_app.logger.error(f"R2 promote error: {e}")
                flash("Could not upload approved song to storage. Please try again.", "error")
                return render_template("admin/review_song.html", song=song, form=form)

        song.status = new_status
        song.rejection_reason = form.rejection_reason.data if new_status == "REJECTED" else None
        log_admin_action(
            f"song_{new_status.lower()}",
            target_type="Song", target_id=song.id,
            details=form.rejection_reason.data if new_status == "REJECTED" else song.title
        )
        db.session.commit()

        # Notify artist
        send_song_status_email(song.artist.user, song, new_status, form.rejection_reason.data)

        flash(f"Song {new_status.lower()}.", "success")
        return redirect(url_for("admin.pending_songs"))
    return render_template("admin/review_song.html", song=song, form=form)

@bp.route("/songs/<song_id>/preview/<kind>")
@login_required
@admin_required
def preview_pending_file(song_id, kind):
    """Stream a not-yet-approved song's locally-staged audio/cover so an admin can review it before it ever reaches R2."""
    from flask import send_file, abort
    from utils import is_pending_local, pending_local_path

    song = Song.query.get_or_404(song_id)
    marker = song.audio_url if kind == "audio" else song.cover_url

    if not is_pending_local(marker):
        # Already promoted to R2 - just send them to the real URL
        return redirect(marker)

    full_path = pending_local_path(marker)
    if not os.path.exists(full_path):
        abort(404)
    return send_file(full_path)

@bp.route("/approved-songs")
@login_required
@admin_required
def approved_songs():
    page = request.args.get("page", 1, type=int)
    pagination = Song.query.filter_by(status="APPROVED").order_by(Song.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/approved_songs.html", pagination=pagination)

@bp.route("/rejected-songs")
@login_required
@admin_required
def rejected_songs():
    page = request.args.get("page", 1, type=int)
    pagination = Song.query.filter_by(status="REJECTED").order_by(Song.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/rejected_songs.html", pagination=pagination)

@bp.route("/songs/<song_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_song(song_id):
    song = Song.query.get_or_404(song_id)

    discard_pending_file(song.audio_url)
    delete_from_r2(song.audio_url)
    if song.cover_url:
        discard_pending_file(song.cover_url)
        delete_from_r2(song.cover_url)

    log_admin_action("song_delete", target_type="Song", target_id=song.id, details=song.title)
    db.session.delete(song)
    db.session.commit()
    flash("Song deleted.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))

@bp.route("/reports")
@login_required
@admin_required
def reports():
    # Simple download statistics
    top_songs = Song.query.filter_by(status="APPROVED").order_by(Song.download_count.desc()).limit(20).all()
    top_artists = Artist.query.join(Song).filter(Song.status=="APPROVED").group_by(Artist.id).order_by(func.sum(Song.download_count).desc()).limit(20).all()
    return render_template("admin/reports.html", top_songs=top_songs, top_artists=top_artists)
