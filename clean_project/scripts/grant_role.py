#!/usr/bin/env python3
from __future__ import annotations

"""
Grant a role to a user (RBAC helper for development).

Usage:
  python clean_project/scripts/grant_role.py --username <name> --role <admin|manager|user|guest>

Notes:
  - Uses environment DATABASE_URL / AUTH_DATABASE_URL if set; otherwise defaults to SQLite files.
  - Initializes default roles/permissions if missing.
"""

import argparse
import os
import sys


def ensure_sys_path() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(here, ".."))
    src_dir = os.path.join(project_root, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def main() -> int:
    ensure_sys_path()
    from agent_system.auth_models import RoleModel, UserModel
    from agent_system.auth_models import db_manager as auth_db
    from agent_system.auth_service import auth_service

    parser = argparse.ArgumentParser(description="Grant a role to a user")
    parser.add_argument("--username", required=True, help="Username (or email)")
    parser.add_argument(
        "--role",
        required=True,
        choices=["admin", "manager", "user", "guest"],
        help="Role to grant",
    )
    args = parser.parse_args()

    # Initialize auth database
    auth_db.database_url = os.getenv("AUTH_DATABASE_URL") or os.getenv(
        "DATABASE_URL", "sqlite:///./agent_enterprise.db"
    )
    auth_db.initialize()
    auth_service.initialize()

    with auth_db.get_session() as session:
        user = (
            session.query(UserModel)
            .filter((UserModel.username == args.username) | (UserModel.email == args.username))
            .first()
        )
        if not user:
            print(f"❌ User not found: {args.username}")
            return 1

        role = session.query(RoleModel).filter(RoleModel.name == args.role).first()
        if not role:
            print(f"❌ Role not found: {args.role}")
            return 1

        # Check if already has role
        if any(r.name == args.role for r in user.roles or []):
            print(f"ℹ️  User '{args.username}' already has role '{args.role}'")
            return 0

        user.roles.append(role)
        session.commit()
        print(f"✅ Granted role '{args.role}' to user '{args.username}'")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

