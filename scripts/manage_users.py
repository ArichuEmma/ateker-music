"""
Pre-production user cleanup: create a real admin account, then remove
demo/test accounts, without ever touching the admin(s) you want to keep.

Usage (from the project root, venv activated, .env pointing at your
real database):

    python -m scripts.manage_users list
        Lists every user with their role and email - use this first to
        see exactly what's in the database before deleting anything.

    python -m scripts.manage_users create-admin
        Prompts for an email and password and creates a new ADMIN user.

    python -m scripts.manage_users delete-non-admins
        Deletes every user whose role is NOT admin. Shows the full list
        and requires typing 'yes' before doing anything - there is no
        way to run this non-interactively/accidentally.

    python -m scripts.manage_users delete --email someone@example.com
        Deletes one specific user by email, with the same confirmation.
"""
import argparse
import getpass
import sys
from app import create_app
from models import db, User


def list_users(app):
    with app.app_context():
        users = User.query.order_by(User.role.desc(), User.created_at).all()
        if not users:
            print("No users in the database.")
            return
        print(f"{'ROLE':8} {'VERIFIED':9} {'EMAIL'}")
        print("-" * 60)
        for u in users:
            print(f"{u.role:8} {'yes' if u.is_verified else 'no':9} {u.email}")
        print(f"\n{len(users)} user(s) total.")


def create_admin(app):
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password (hidden): ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords don't match. Aborted.")
        return
    if len(password) < 12:
        print("Use a longer password (12+ characters) for an admin account. Aborted.")
        return

    with app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.role = "ADMIN"
            existing.is_verified = True
            existing.set_password(password)
            db.session.commit()
            print(f"Existing user {email} upgraded to ADMIN and password updated.")
            return

        user = User(email=email, role="ADMIN", is_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Admin account created: {email}")


def delete_non_admins(app):
    with app.app_context():
        targets = User.query.filter(User.role != "ADMIN").all()
        if not targets:
            print("No non-admin users found - nothing to delete.")
            return

        print(f"About to PERMANENTLY delete {len(targets)} non-admin user(s):")
        for u in targets:
            print(f"  {u.role:8} {u.email}")

        admins = User.query.filter_by(role="ADMIN").all()
        print(f"\nThese {len(admins)} ADMIN account(s) will be kept untouched:")
        for a in admins:
            print(f"  {a.email}")

        confirm = input(f"\nType 'yes' to permanently delete these {len(targets)} user(s): ")
        if confirm.strip().lower() != "yes":
            print("Aborted - nothing deleted.")
            return

        for u in targets:
            db.session.delete(u)  # cascades to their Profile/Artist/Songs
        db.session.commit()
        print(f"Deleted {len(targets)} user(s).")


def delete_one(app, email):
    with app.app_context():
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            print(f"No user found with email {email}.")
            return
        print(f"About to permanently delete: {user.role} - {user.email}")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("Aborted - nothing deleted.")
            return
        db.session.delete(user)
        db.session.commit()
        print(f"Deleted {user.email}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("create-admin")
    sub.add_parser("delete-non-admins")
    del_parser = sub.add_parser("delete")
    del_parser.add_argument("--email", required=True)

    args = parser.parse_args()
    app = create_app()

    if args.command == "list":
        list_users(app)
    elif args.command == "create-admin":
        create_admin(app)
    elif args.command == "delete-non-admins":
        delete_non_admins(app)
    elif args.command == "delete":
        delete_one(app, args.email)


if __name__ == "__main__":
    main()
