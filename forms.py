from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField,     BooleanField, FileField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional,     ValidationError, Regexp
from flask_wtf.file import FileAllowed, FileSize
from models import User

class RegistrationForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters"),
        Regexp(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)", 
               message="Password must contain uppercase, lowercase, and a number")
    ])
    confirm_password = PasswordField("Confirm Password", validators=[
        DataRequired(), EqualTo("password", message="Passwords must match")
    ])
    first_name = StringField("First Name", validators=[Optional(), Length(max=100)])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=100)])
    role = SelectField("Account Type", choices=[("USER", "Listener"), ("ARTIST", "Artist")], default="USER")
    submit = SubmitField("Create Account")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower().strip()).first()
        if user:
            raise ValidationError("Email already registered.")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Log In")

class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")

class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[
        DataRequired(), Length(min=8),
        Regexp(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)",
               message="Password must contain uppercase, lowercase, and a number")
    ])
    confirm_password = PasswordField("Confirm Password", validators=[
        DataRequired(), EqualTo("password")
    ])
    submit = SubmitField("Reset Password")

class ArtistProfileForm(FlaskForm):
    stage_name = StringField("Stage Name", validators=[DataRequired(), Length(max=200)])
    bio = TextAreaField("Biography", validators=[Optional(), Length(max=5000)])
    genre = SelectField("Primary Genre", choices=[
        ("", "Select Genre"),
        ("Afrobeat", "Afrobeat"),
        ("Gospel", "Gospel"),
        ("Hip Hop", "Hip Hop"),
        ("Dancehall", "Dancehall"),
        ("R&B", "R&B"),
        ("Traditional", "Traditional"),
        ("DJ Mix", "DJ Mix"),
        ("Other", "Other"),
    ])
    location = StringField("Location", validators=[Optional(), Length(max=200)])
    facebook = StringField("Facebook", validators=[Optional(), Length(max=500)])
    twitter = StringField("Twitter / X", validators=[Optional(), Length(max=500)])
    instagram = StringField("Instagram", validators=[Optional(), Length(max=500)])
    youtube = StringField("YouTube", validators=[Optional(), Length(max=500)])
    website = StringField("Website", validators=[Optional(), Length(max=500)])
    avatar = FileField("Profile Picture", validators=[
        Optional(),
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only!"),
        FileSize(max_size=5 * 1024 * 1024, message="Max 5MB")
    ])
    cover = FileField("Cover Banner", validators=[
        Optional(),
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only!"),
        FileSize(max_size=5 * 1024 * 1024, message="Max 5MB")
    ])
    submit = SubmitField("Save Profile")

class UploadSongForm(FlaskForm):
    title = StringField("Song Title", validators=[DataRequired(), Length(max=300)])
    genre = SelectField("Genre", choices=[
        ("Afrobeat", "Afrobeat"),
        ("Gospel", "Gospel"),
        ("Hip Hop", "Hip Hop"),
        ("Dancehall", "Dancehall"),
        ("R&B", "R&B"),
        ("Traditional", "Traditional"),
        ("DJ Mix", "DJ Mix"),
        ("Other", "Other"),
    ], validators=[DataRequired()])
    album = StringField("Album (Optional)", validators=[Optional(), Length(max=300)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    cover = FileField("Cover Image", validators=[
        Optional(),
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only!"),
        FileSize(max_size=5 * 1024 * 1024)
    ])
    audio = FileField("Audio File", validators=[
        DataRequired(),
        FileAllowed(["mp3", "wav", "ogg", "m4a", "flac"], "Audio files only!"),
        FileSize(max_size=50 * 1024 * 1024, message="Max 50MB")
    ])
    terms_agreed = BooleanField("I agree to the Terms and Conditions", validators=[DataRequired()])
    submit = SubmitField("Upload Song")

class SongReviewForm(FlaskForm):
    status = SelectField("Decision", choices=[
        ("APPROVED", "Approve"),
        ("REJECTED", "Reject"),
    ], validators=[DataRequired()])
    rejection_reason = TextAreaField("Rejection Reason (required if rejecting)", validators=[Optional()])
    submit = SubmitField("Submit Review")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        if self.status.data == "REJECTED" and not self.rejection_reason.data.strip():
            self.rejection_reason.errors.append("Rejection reason is required.")
            return False
        return True

class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    subject = StringField("Subject", validators=[DataRequired(), Length(max=300)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=5000)])
    submit = SubmitField("Send Message")
