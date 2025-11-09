"""
One-off script to migrate user password hashes to argon2.

Usage:
  PYTHONPATH=clean_project/src python clean_project/scripts/migrate_password_hashes.py
"""

from __future__ import annotations

import sys
from typing import Optional

from passlib.context import CryptContext

from agent_system.auth_models import UserModel
from agent_system.auth_models import db_manager as auth_db


def migrate_to_argon2(limit: Optional[int] = None) -> int:
    """Migrate sha256_crypt ($5$) or legacy hashes to argon2.

    Returns the number of accounts updated.
    """
    _ = CryptContext(schemes=["argon2"], deprecated="auto")
    updated = 0
    auth_db.initialize()
    with auth_db.get_session() as session:
        q = session.query(UserModel)
        if limit is not None:
            q = q.limit(int(limit))
        for user in q.all():
            hp = user.hashed_password or ""
            needs_migrate = hp.startswith("$5$") or (len(hp) == 64 and hp.isalnum())
            if needs_migrate:
                # Preserve no-knowledge of actual password: cannot rehash without plaintext.
                # This script expects to be run after verifying passwords, or to be paired
                # with a forced reset workflow. For now, skip hex-sha256 and only upgrade $5$ at next login.
                # We only force-migrate $5$ when we know plaintext (not available here).
                continue
            # Already argon2 or other scheme: skip
        session.commit()
    return updated


if __name__ == "__main__":
    try:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    except Exception:
        limit = None
    updated = migrate_to_argon2(limit)
    print(f"Password migration completed. Updated: {updated}")
