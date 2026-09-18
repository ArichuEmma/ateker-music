from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
from models import db, User, Profile, Artist, EmailVerification, PasswordReset
from forms import RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from utils import send_verification_email, send_password_reset_email, generate_slug, is_safe_url
from sqlalchemy import func
from app import limiter
import secrets

bp = Blueprint("auth", __name__)

def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower().strip(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        # Create profile
        profile = Profile(
            user_id=user.id,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
        )
        db.session.add(profile)

        # Create artist record if applicable
        if form.role.data == "ARTIST":
            base_slug = generate_slug(form.first_name.data or form.email.data.split("@")[0])
            unique_slug = f"{base_slug}-{secrets.token_hex(4)}"
            artist = Artist(
                user_id=user.id,
                stage_name=form.first_name.data or form.email.data.split("@")[0],
                slug=unique_slug,
            )
            db.session.add(artist)

        db.session.commit()

        # Send verification email
        token = secrets.token_urlsafe(32)
        ev = EmailVerification(user_id=user.id, token=token, expires_at=datetime.utcnow() + timedelta(hours=24))
        db.session.add(ev)
        db.session.commit()
        send_verification_email(user, token)

        flash("Account created! Please check your email to verify your account.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if user.is_suspended:
                flash("Your account has been suspended. Contact support.", "error")
                return render_template("auth/login.html", form=form)
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            flash("Welcome back!", "success")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("public.home"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html", form=form)

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("public.home"))

@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            token = secrets.token_urlsafe(32)
            pr = PasswordReset(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(pr)
            db.session.commit()
            send_password_reset_email(user, token)
        # Same message regardless of email existence (security)
        flash("If an account exists with that email, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)

@bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("15 per hour")
def reset_password():
    token = request.args.get("token")
    if not token:
        flash("Invalid reset link.", "error")
        return redirect(url_for("auth.forgot_password"))

    pr = PasswordReset.query.filter_by(token=token).first()
    if not pr or pr.used_at or pr.expires_at < datetime.utcnow():
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        pr.user.set_password(form.password.data)
        pr.used_at = datetime.utcnow()
        db.session.commit()
        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)

@bp.route("/verify-email")
def verify_email():
    token = request.args.get("token")
    if not token:
        flash("Invalid verification link.", "error")
        return redirect(url_for("public.home"))

    ev = EmailVerification.query.filter_by(token=token).first()
    if not ev or ev.used_at or ev.expires_at < datetime.utcnow():
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("public.home"))

    ev.user.is_verified = True
    ev.used_at = datetime.utcnow()
    db.session.commit()
    flash("Email verified successfully! You can now log in.", "success")
    return redirect(url_for("auth.login"))

@bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")

@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        if current_password and new_password:
            if current_user.check_password(current_password):
                if len(new_password) >= 8:
                    current_user.set_password(new_password)
                    db.session.commit()
                    flash("Password updated successfully.", "success")
                else:
                    flash("New password must be at least 8 characters.", "error")
            else:
                flash("Current password is incorrect.", "error")
        return redirect(url_for("auth.settings"))
    return render_template("auth/settings.html")
