from flask import Blueprint, render_template, request, flash, current_app, redirect, url_for, jsonify
from sqlalchemy import or_, func
from models import db, Song, Artist, Download
from utils import clean_html
from r2 import presigned_download_url
from app import limiter
import re

bp = Blueprint("public", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@bp.route("/api/contact", methods=["POST"])
@limiter.limit("5 per hour")
def api_contact():
    """
    JSON contact endpoint for the standalone contact.html page (or any
    other same-origin static page) to POST to directly via fetch().
    Deliberately outside ContactForm/CSRF since a plain static HTML file
    has no session to carry a CSRF token in - rate limiting plus the
    honeypot field below are this endpoint's abuse defenses instead.
    Must be called from the same origin the app is served on; browsers'
    same-origin policy blocks it from anywhere else by default since no
    CORS headers are set here.
    """
    from utils import send_contact_message
    data = request.get_json(silent=True) or request.form

    # Honeypot: real users never fill this hidden field, bots often do.
    if (data.get("_gotcha") or "").strip():
        return jsonify({"success": True})  # pretend success, drop silently

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    errors = {}
    if not name or len(name) > 200:
        errors["name"] = "Please enter your name."
    if not email or not EMAIL_RE.match(email) or len(email) > 200:
        errors["email"] = "Please enter a valid email address."
    if not subject or len(subject) > 300:
        errors["subject"] = "Please enter a subject."
    if not message or len(message) > 5000:
        errors["message"] = "Please enter a message (max 5000 characters)."

    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    sent = send_contact_message(name, email, subject, message)
    if sent:
        return jsonify({"success": True})
    return jsonify({"success": False, "errors": {"_general": "Failed to send. Please try emailing us directly."}}), 500

@bp.route("/")
def home():
    featured_artists = Artist.query.filter_by(is_verified=True).order_by(func.random()).limit(8).all()
    latest_songs = Song.query.filter_by(status="APPROVED").order_by(Song.created_at.desc()).limit(10).all()
    trending_songs = Song.query.filter_by(status="APPROVED").order_by(Song.download_count.desc()).limit(10).all()
    popular_artists = Artist.query.join(Song).filter(Song.status=="APPROVED").group_by(Artist.id).order_by(func.sum(Song.download_count).desc()).limit(8).all()

    total_songs = Song.query.filter_by(status="APPROVED").count()
    total_artists = Artist.query.count()
    total_downloads = db.session.query(func.sum(Song.download_count)).scalar() or 0

    return render_template("home.html",
        featured_artists=featured_artists,
        latest_songs=latest_songs,
        trending_songs=trending_songs,
        popular_artists=popular_artists,
        stats={"songs": total_songs, "artists": total_artists, "downloads": total_downloads}
    )

@bp.route("/artists")
def artists():
    page = request.args.get("page", 1, type=int)
    pagination = Artist.query.order_by(Artist.stage_name).paginate(page=page, per_page=24, error_out=False)
    return render_template("artists.html", pagination=pagination)

@bp.route("/artists/<slug>")
def artist_profile(slug):
    artist = Artist.query.filter_by(slug=slug).first_or_404()
    songs = Song.query.filter_by(artist_id=artist.id, status="APPROVED").order_by(Song.created_at.desc()).all()
    stats = {
        "song_count": len(songs),
        "total_downloads": sum(s.download_count for s in songs),
    }
    return render_template("artist_profile.html", artist=artist, songs=songs, stats=stats)

@bp.route("/songs")
def all_songs():
    page = request.args.get("page", 1, type=int)
    genre = request.args.get("genre", "")
    search = request.args.get("q", "")
    sort = request.args.get("sort", "latest")

    query = Song.query.filter_by(status="APPROVED")
    if genre:
        query = query.filter(Song.genre.ilike(genre))
    if search:
        query = query.join(Artist).filter(or_(
            Song.title.ilike(f"%{search}%"),
            Artist.stage_name.ilike(f"%{search}%"),
            Song.album.ilike(f"%{search}%"),
            Song.genre.ilike(f"%{search}%")
        ))
    if sort == "popular":
        query = query.order_by(Song.download_count.desc())
    else:
        query = query.order_by(Song.created_at.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template("songs.html", pagination=pagination, genre=genre, search=search, sort=sort)

@bp.route("/songs/<slug>")
def song_detail(slug):
    song = Song.query.filter_by(slug=slug, status="APPROVED").first_or_404()
    return render_template("song_detail.html", song=song)

@bp.route("/songs/<slug>/download")
@limiter.limit("30 per minute")
def download_song(slug):
    from flask_login import current_user
    song = Song.query.filter_by(slug=slug, status="APPROVED").first_or_404()

    download = Download(
        song_id=song.id,
        user_id=current_user.id if current_user.is_authenticated else None,
        artist_id=song.artist_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:500] if request.user_agent else None
    )
    song.download_count += 1
    db.session.add(download)
    db.session.commit()

    from werkzeug.utils import secure_filename
    ext = song.audio_url.rsplit(".", 1)[-1] if "." in song.audio_url else "mp3"
    filename = secure_filename(f"{song.artist.stage_name} - {song.title}.{ext}")

    url = presigned_download_url(song.audio_url, filename, expires_in=60)
    if url:
        return redirect(url)

    flash("File not found.", "error")
    return redirect(url_for("public.song_detail", slug=slug))

@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return render_template("search.html", q=q, songs=[], artists=[])
    songs = Song.query.filter_by(status="APPROVED").join(Artist).filter(or_(
        Song.title.ilike(f"%{q}%"),
        Artist.stage_name.ilike(f"%{q}%"),
        Song.album.ilike(f"%{q}%")
    )).limit(20).all()
    artists = Artist.query.filter(Artist.stage_name.ilike(f"%{q}%")).limit(12).all()
    return render_template("search.html", q=q, songs=songs, artists=artists)

@bp.route("/about")
def about():
    return render_template("about.html")

@bp.route("/contact", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def contact():
    from forms import ContactForm
    from utils import send_contact_message
    form = ContactForm()
    if form.validate_on_submit():
        sent = send_contact_message(form.name.data, form.email.data, form.subject.data, form.message.data)
        if sent:
            flash("Message sent! We'll get back to you soon.", "success")
        else:
            flash("Sorry, something went wrong sending your message. Please try emailing us directly.", "error")
        return redirect(url_for("public.contact"))
    return render_template("contact.html", form=form)

@bp.route("/terms")
def terms():
    return render_template("terms.html")

@bp.route("/privacy")
def privacy():
    return render_template("privacy.html")

@bp.route("/data-privacy")
def data_privacy():
    return render_template("data_privacy.html")

@bp.route("/copyright")
def copyright_policy():
    return render_template("copyright.html")

@bp.route("/latest")
def latest_releases():
    songs = Song.query.filter_by(status="APPROVED").order_by(Song.created_at.desc()).limit(50).all()
    return render_template("latest.html", songs=songs)

@bp.route("/robots.txt")
def robots():
    return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", 200, {"Content-Type": "text/plain"}

@bp.route("/sitemap.xml")
def sitemap():
    from datetime import datetime
    songs = Song.query.filter_by(status="APPROVED").all()
    artists = Artist.query.all()
    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for route in ["public.home", "public.artists", "public.all_songs", "public.about", "public.contact", "public.terms", "public.privacy"]:
        xml.append(f"<url><loc>{url_for(route, _external=True)}</loc><priority>0.8</priority></url>")
    for song in songs:
        xml.append(f"<url><loc>{url_for('public.song_detail', slug=song.slug, _external=True)}</loc><lastmod>{song.updated_at.strftime('%Y-%m-%d')}</lastmod><priority>0.6</priority></url>")
    for artist in artists:
        xml.append(f"<url><loc>{url_for('public.artist_profile', slug=artist.slug, _external=True)}</loc><lastmod>{artist.updated_at.strftime('%Y-%m-%d')}</lastmod><priority>0.7</priority></url>")
    xml.append("</urlset>")
    return "\n".join(xml), 200, {"Content-Type": "application/xml"}
