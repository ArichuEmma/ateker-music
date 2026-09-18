"""
Find (and optionally delete) R2 objects that no longer have a matching
row in the database - e.g. left behind by a crash between an upload and
a commit, or a manual DB edit.

Usage (from the project root, with your .env / venv active):

    python -m scripts.r2_cleanup                # dry run - lists orphans only
    python -m scripts.r2_cleanup --delete        # actually deletes orphans
    python -m scripts.r2_cleanup --prefix songs/ # limit the scan to one prefix

This is intentionally a dry-run-by-default, manually-invoked script rather
than something that runs automatically - deleting the wrong object because
of a bug here would be a real data-loss incident, so a human should review
the orphan list before anything is removed.
"""
import argparse
import sys
from app import create_app
from models import db, Song, Artist
from r2 import get_r2_client, extract_r2_key

PREFIXES = ["songs/", "covers/", "artist-covers/", "avatars/"]


def referenced_keys(app):
    """All R2 keys currently referenced by a DB row."""
    keys = set()
    with app.app_context():
        for song in Song.query.all():
            for url in (song.audio_url, song.cover_url):
                key = extract_r2_key(url)
                if key:
                    keys.add(key)
        for artist in Artist.query.all():
            for url in (artist.avatar_url, artist.cover_url):
                key = extract_r2_key(url)
                if key:
                    keys.add(key)
    return keys


def list_r2_objects(app, prefix):
    with app.app_context():
        client = get_r2_client()
        bucket = app.config["R2_BUCKET_NAME"]
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"], obj["Size"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="Actually delete orphaned objects (default: dry run)")
    parser.add_argument("--prefix", action="append", help="Limit scan to this R2 key prefix (repeatable). Defaults to all known prefixes.")
    args = parser.parse_args()

    prefixes = args.prefix or PREFIXES
    app = create_app()

    print("Loading referenced keys from the database...")
    referenced = referenced_keys(app)
    print(f"  {len(referenced)} objects are referenced by a DB row.\n")

    orphans = []
    total_size = 0
    for prefix in prefixes:
        print(f"Scanning R2 prefix '{prefix}'...")
        for key, size in list_r2_objects(app, prefix):
            if key not in referenced:
                orphans.append((key, size))
                total_size += size

    if not orphans:
        print("\nNo orphaned objects found.")
        return

    print(f"\nFound {len(orphans)} orphaned object(s), {total_size / (1024*1024):.1f} MB total:")
    for key, size in orphans:
        print(f"  {key}  ({size / 1024:.1f} KB)")

    if not args.delete:
        print("\nDry run only - nothing deleted. Re-run with --delete to remove these.")
        return

    confirm = input(f"\nType 'yes' to permanently delete these {len(orphans)} object(s): ")
    if confirm.strip().lower() != "yes":
        print("Aborted - nothing deleted.")
        return

    with app.app_context():
        client = get_r2_client()
        bucket = app.config["R2_BUCKET_NAME"]
        for key, _ in orphans:
            try:
                client.delete_object(Bucket=bucket, Key=key)
                print(f"  deleted {key}")
            except Exception as e:
                print(f"  FAILED to delete {key}: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
