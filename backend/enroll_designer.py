"""Enroll or reset a Designer using a verified existing owner ID."""
import argparse
from getpass import getpass
import secrets

from pymongo.errors import DuplicateKeyError

from backend.core.designer_sessions import accounts, password_digest
from backend.data.database import get_designer_database


def configure_account(email, owner_id, name, organization, password, *, reset=False):
    database = get_designer_database()
    database["verified_designer_sessions"].create_index("expires_at", expireAfterSeconds=0)
    database["verified_designer_login_attempts"].create_index("expires_at", expireAfterSeconds=0)
    directory = accounts()
    directory.create_index("owner_id", unique=True)
    salt = secrets.token_hex(16)
    fields = {
        "owner_id": owner_id, "name": name, "organization": organization, "salt": salt,
        "password_digest": password_digest(password, salt),
        "revision": secrets.token_hex(16), "active": True,
    }
    if reset:
        if not directory.update_one({"_id": email, "owner_id": owner_id}, {"$set": fields}).matched_count:
            raise ValueError("The email and owner ID must match the enrolled account.")
    else:
        try:
            directory.insert_one({"_id": email, **fields})
        except DuplicateKeyError as exc:
            raise ValueError("That email or owner ID is already enrolled.") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--owner-id", required=True, help="Existing immutable curriculum owner ID")
    parser.add_argument("--name", required=True)
    parser.add_argument("--organization", default="Curriculum Design Cell")
    parser.add_argument("--reset", action="store_true", help="Reset the matching account and invalidate its sessions")
    args = parser.parse_args()
    email = args.email.strip().lower()
    if "@" not in email or len(email) > 254 or not args.owner_id.strip() or not args.name.strip():
        parser.error("Provide an email, name and stable owner ID.")
    password = getpass("New Designer password (at least 14 characters): ")
    if not 14 <= len(password) <= 256 or password != getpass("Confirm password: "):
        parser.error("Passwords must match and contain 14 to 256 characters.")
    try:
        configure_account(email, args.owner_id.strip(), args.name.strip(), args.organization.strip(), password, reset=args.reset)
    except ValueError as exc:
        parser.error(str(exc))
    print("Verified Designer credentials saved.")


if __name__ == "__main__":
    main()
