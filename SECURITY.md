# Security Policy — Ateker Music

## Supported versions
Only the `main` branch / latest deployed version is supported with security fixes.
There are no maintained older release branches.

## Reporting a vulnerability
If you discover a security issue in this codebase, report it privately to the
site administrator rather than opening a public issue. Include:
- A description of the vulnerability and its impact
- Steps to reproduce
- Any relevant request/response examples (redact real user data)

Please allow time for a fix before public disclosure.

## Dependency update policy
- Run `pip list --outdated` monthly against `requirements.txt`.
- Before upgrading, check the release notes for each package for breaking
  changes (not just the security fix) — see each package's GitHub
  Releases/CHANGELOG.
- Patch/minor version bumps (e.g. 3.1.2 → 3.1.3) are generally safe to apply
  directly. Major version bumps (e.g. Pillow 10.x → 12.x) should be tested
  against the upload flow (`/artist/upload`, `/artist/profile`) before
  deploying, since these touch image/audio processing directly.
- Tools worth wiring into CI for this: `pip-audit` (checks installed
  packages against the PyPI advisory database) or GitHub's built-in
  Dependabot security alerts. A weekly `pip-audit` scan is already
  configured at `.github/workflows/security-scan.yml` - it reports
  findings but never auto-upgrades, since a security patch can still
  carry a breaking change.

## Admin action audit log
Song approvals/rejections/deletions and user suspensions are recorded in
the `admin_action_logs` table (see `AdminActionLog` in `models.py`) via
`log_admin_action()` in `utils.py`. This is append-only from the
application's side - nothing deletes or edits these rows.

## R2 orphan cleanup
`scripts/r2_cleanup.py` finds R2 objects with no matching `Song`/`Artist`
row (e.g. left behind by a crash between upload and DB commit) and can
optionally delete them. It's a manual, dry-run-by-default tool - not
scheduled automatically, since an incorrect delete here is a data-loss
bug, not just noise. Run it periodically or after any incident involving
uploads.

## Patch history (this audit)
| Date | Package | From → To | Reason |
|---|---|---|---|
| 2026-09 | Pillow | 10.4.0 → 12.2.0 | Multiple 2026 CVEs in image decoders (PSD OOB write, coordinate-parsing heap overflow, FITS decompression bomb) reachable via user-uploaded cover art/avatars |
| 2026-09 | Werkzeug | 3.0.3 → 3.1.8 | Rolls up fixes after 3.0.3, incl. `safe_join` hardening |
| 2026-09 | Flask | 3.0.3 → 3.1.3 | Includes GHSA-68rp-wp8r-4726 session-handling fix |
| 2026-09 | cryptography | 42.0.8 → 46.0.7 | Multiple releases behind; 46.0.7 fixes CVE-2026-39892 (buffer handling) |

## Production security checklist
- [ ] `.env` is populated with rotated, non-default credentials and is **not** committed to git (`.gitignore` covers this)
- [ ] `SECRET_KEY` is a long random value, unique per environment
- [ ] `SESSION_COOKIE_SECURE` / `REMEMBER_COOKIE_SECURE` are `True` (already set in `config.py`) — requires the app to actually be served over HTTPS
- [ ] App is run via `gunicorn` (already in `requirements.txt`), never the Flask dev server, in production
- [ ] `FLASK_ENV` is `production`
- [ ] Database, mail, and R2 credentials are least-privilege (R2 key scoped to only the one bucket if Cloudflare supports it)
- [ ] Rate limits on `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password` are in place (see `routes/auth.py`)
- [ ] Dependencies checked for known CVEs before each deploy
