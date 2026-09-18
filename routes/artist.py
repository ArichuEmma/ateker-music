from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Song, Artist, Download
from forms import ArtistProfileForm, UploadSongForm
from utils import artist_required, verified_required, upload_image_to_r2, stage_audio_locally, stage_image_locally, discard_pending_file, clean_html, generate_slug, send_song_status_email
from r2 import delete_from_r2
import secrets

bp = Blueprint("artist", __name__)

@bp.route("/dashboard")
@login_required
@artist_required
def dashboard():
    artist = current_user.artist
    if not artist:
        flash("Artist profile not found.", "error")
        return redirect(url_for("public.home"))

    total_songs = Song.query.filter_by(artist_id=artist.id).count()
    pending = Song.query.filter_by(artist_id=artist.id, status="PENDING").count()
    approved = Song.query.filter_by(artist_id=artist.id, status="APPROVED").count()
    rejected = Song.query.filter_by(artist_id=artist.id, status="REJECTED").count()
    total_downloads = db.session.query(func.sum(Song.download_count)).filter_by(artist_id=artist.id).scalar() or 0

    recent_songs = Song.query.filter_by(artist_id=artist.id).order_by(Song.created_at.desc()).limit(5).all()

    return render_template("artist/dashboard.html",
        artist=artist,
        stats={"total": total_songs, "pending": pending, "approved": approved, "rejected": rejected, "downloads": total_downloads},
        recent_songs=recent_songs
    )

@bp.route("/profile", methods=["GET", "POST"])
@login_required
@artist_required
def profile():
    artist = current_user.artist
    if not artist:
        flash("Artist profile not found.", "error")
        return redirect(url_for("public.home"))

    form = ArtistProfileForm(obj=artist)
    if form.validate_on_submit():
        artist.stage_name = form.stage_name.data
        artist.bio = clean_html(form.bio.data)
        artist.genre = form.genre.data
        artist.location = form.location.data
        artist.facebook = form.facebook.data
        artist.twitter = form.twitter.data
        artist.instagram = form.instagram.data
        artist.youtube = form.youtube.data
        artist.website = form.website.data

        if form.avatar.data:
            try:
                new_avatar_url = upload_image_to_r2(form.avatar.data, "avatars", artist.id, 400, 400)
                if new_avatar_url:
                    old_avatar_url = artist.avatar_url
                    artist.avatar_url = new_avatar_url
                    if old_avatar_url:
                        delete_from_r2(old_avatar_url)
            except ValueError as e:
                flash(str(e), "error")
                return render_template("artist/profile.html", form=form, artist=artist)

        if form.cover.data:
            try:
                new_cover_url = upload_image_to_r2(form.cover.data, "artist-covers", artist.id, 1600, 500)
                if new_cover_url:
                    old_cover_url = artist.cover_url
                    artist.cover_url = new_cover_url
                    if old_cover_url:
                        delete_from_r2(old_cover_url)
            except ValueError as e:
                flash(str(e), "error")
                return render_template("artist/profile.html", form=form, artist=artist)

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("artist.profile"))

    return render_template("artist/profile.html", form=form, artist=artist)

@bp.route("/upload", methods=["GET", "POST"])
@login_required
@artist_required
@verified_required
def upload():
    artist = current_user.artist
    if not artist.terms_agreed:
        flash("You must agree to the Terms and Conditions before uploading.", "warning")
        return redirect(url_for("artist.terms_agreement"))

    form = UploadSongForm()
    if form.validate_on_submit():
        base_slug = generate_slug(form.title.data)
        unique_slug = f"{base_slug}-{secrets.token_hex(4)}"

        # Stage audio locally - NOT sent to R2 until an admin approves it
        try:
            audio_url = stage_audio_locally(
                form.audio.data,
                artist.id,
                current_app.config["ALLOWED_AUDIO"],
                current_app.config["MAX_AUDIO_SIZE"]
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("artist/upload.html", form=form)
        except Exception as e:
            current_app.logger.error(f"Audio staging error: {e}")
            flash("Upload failed. Please try again.", "error")
            return render_template("artist/upload.html", form=form)

        # Stage cover locally too (optional)
        cover_url = None
        if form.cover.data:
            try:
                cover_url = stage_image_locally(form.cover.data, "covers", artist.id, 800, 800)
            except ValueError as e:
                flash(f"Cover image not uploaded: {e}", "warning")

        song = Song(
            artist_id=artist.id,
            title=form.title.data.strip(),
            slug=unique_slug,
            genre=form.genre.data,
            album=form.album.data.strip() if form.album.data else None,
            description=clean_html(form.description.data),
            audio_url=audio_url,
            cover_url=cover_url,
            status="PENDING"
        )
        db.session.add(song)
        db.session.commit()

        flash("Song uploaded successfully and is pending approval.", "success")
        return redirect(url_for("artist.my_songs"))

    return render_template("artist/upload.html", form=form)

@bp.route("/terms-agreement", methods=["GET", "POST"])
@login_required
@artist_required
def terms_agreement():
    artist = current_user.artist
    if request.method == "POST":
        if request.form.get("agree") == "yes":
            artist.terms_agreed = True
            db.session.commit()
            flash("Terms accepted. You can now upload music.", "success")
            return redirect(url_for("artist.upload"))
        flash("You must agree to the terms to continue.", "error")
    return render_template("artist/terms_agreement.html")

@bp.route("/my-songs")
@login_required
@artist_required
def my_songs():
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    artist = current_user.artist
    query = Song.query.filter_by(artist_id=artist.id)
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(Song.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("artist/my_songs.html", pagination=pagination, songs=pagination.items, current_status=status)

@bp.route("/songs/<song_id>/edit", methods=["GET", "POST"])
@login_required
@artist_required
def edit_song(song_id):
    song = Song.query.get_or_404(song_id)
    if song.artist_id != current_user.artist.id:
        flash("Unauthorized.", "error")
        return redirect(url_for("artist.my_songs"))

    if song.status == "APPROVED":
        flash("Approved songs cannot be edited. Contact admin.", "warning")
        return redirect(url_for("artist.my_songs"))

    if request.method == "POST":
        song.title = request.form.get("title", song.title).strip()
        song.genre = request.form.get("genre", song.genre)
        song.album = request.form.get("album", song.album)
        song.description = clean_html(request.form.get("description", ""))

        if "cover" in request.files and request.files["cover"].filename:
            try:
                new_cover_url = upload_image_to_r2(request.files["cover"], "covers", song.artist_id, 800, 800)
                if new_cover_url:
                    old_cover_url = song.cover_url
                    song.cover_url = new_cover_url
                    if old_cover_url:
                        delete_from_r2(old_cover_url)
            except ValueError as e:
                flash(f"Cover image not updated: {e}", "warning")

        db.session.commit()
        flash("Song updated.", "success")
        return redirect(url_for("artist.my_songs"))

    return render_template("artist/edit_song.html", song=song)

@bp.route("/songs/<song_id>/delete", methods=["POST"])
@login_required
@artist_required
def delete_song(song_id):
    song = Song.query.get_or_404(song_id)
    if song.artist_id != current_user.artist.id:
        flash("Unauthorized.", "error")
        return redirect(url_for("artist.my_songs"))

    # Delete files - could be a local staging marker (never reached R2) or a real R2 URL
    discard_pending_file(song.audio_url)
    delete_from_r2(song.audio_url)
    if song.cover_url:
        discard_pending_file(song.cover_url)
        delete_from_r2(song.cover_url)

    db.session.delete(song)
    db.session.commit()
    flash("Song deleted.", "success")
    return redirect(url_for("artist.my_songs"))

@bp.route("/statistics")
@login_required
@artist_required
def statistics():
    artist = current_user.artist
    songs = Song.query.filter_by(artist_id=artist.id).order_by(Song.download_count.desc()).all()
    total_downloads = sum(s.download_count for s in songs)
    return render_template("artist/statistics.html", songs=songs, total_downloads=total_downloads)
