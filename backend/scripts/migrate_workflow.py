"""Safely create workflow indexes and migrate legacy demo identities.

This migration only adds missing workflow collections/indexes and inserts
missing demo users with password hashes. It does not create institution links
or update existing records.
"""

from backend.routers.demo import USERS
from backend.services.workflow_service import ensure_workflow_indexes, migrate_demo_accounts


def main() -> None:
    ensure_workflow_indexes()
    migrate_demo_accounts(USERS)
    print("Workflow indexes ready; legacy demo identity migration completed.")
    print("Institution assignments were left unset for explicit administrator mapping.")


if __name__ == "__main__":
    main()
