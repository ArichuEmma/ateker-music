# Ateker Music Download

A fully functional music download website built with Python, Flask, MySQL, HTML, CSS, and JavaScript.

## Features

- **3 User Roles**: Normal Users, Artists, Administrators
- **Authentication**: Registration, Login, Logout, Email Verification
- **Password Reset**: Secure email-only reset with expiring single-use tokens
- **Artist Dashboard**: Profile management, song upload, status tracking, download stats
- **Admin Dashboard**: User/artist management, song approval/rejection, statistics
- **SEO**: Dynamic meta tags, Open Graph, Schema.org JSON-LD, XML sitemap, robots.txt
- **Security**: Bcrypt password hashing, CSRF protection, rate limiting, secure headers, input sanitization, role-based access control
- **File Uploads**: MIME type validation, size limits, randomized filenames, image resizing

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, Flask |
| ORM | Flask-SQLAlchemy |
| Database | MySQL (via PyMySQL) |
| Auth | Flask-Login, Werkzeug (bcrypt) |
| Forms | Flask-WTF (CSRF protected) |
| Email | Flask-Mail |
| Rate Limiting | Flask-Limiter |
| Frontend | HTML, Tailwind CSS, Vanilla JS |

## Setup

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database and SMTP credentials
```

### 3. Create MySQL Database

```sql
CREATE DATABASE ateker_music CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ateker_user'@'localhost' IDENTIFIED BY 'StrongPassword123';
GRANT ALL PRIVILEGES ON ateker_music.* TO 'ateker_user'@'localhost';
FLUSH PRIVILEGES;
```

### 4. Run the Application

```bash
python run.py
```

The app will be available at `http://localhost:5000`.

### 5. Create First Admin

Register a user, then manually update their role in MySQL:

```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'your-email@example.com';
```

## Production Deployment

1. Set `FLASK_ENV=production`
2. Use a strong `SECRET_KEY`
3. Set `SESSION_COOKIE_SECURE=True` (requires HTTPS)
4. Use Gunicorn: `gunicorn -w 4 -b 0.0.0.0:5000 run:app`
5. Place behind Nginx with SSL
6. Move uploads to AWS S3 or similar object storage for scalability

## File Upload Security

- Audio: MP3, WAV, OGG, M4A, FLAC (max 50MB)
- Images: JPG, PNG, WebP, GIF (max 5MB)
- Files are saved with random UUID filenames
- Images are resized and converted to JPEG
- No executable file uploads allowed

## Project Structure

```
ateker_music/
├── app.py              # Flask app factory
├── config.py           # Configuration
├── models.py           # SQLAlchemy models
├── forms.py            # WTForms
├── utils.py            # Helpers & decorators
├── run.py              # Entry point
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
├── routes/
│   ├── public.py       # Public pages
│   ├── auth.py         # Authentication
│   ├── artist.py       # Artist dashboard
│   └── admin.py        # Admin dashboard
├── templates/          # Jinja2 HTML templates
└── static/             # CSS, JS, uploads
```

## License

MIT
