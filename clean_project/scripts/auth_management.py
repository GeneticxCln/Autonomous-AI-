"""
Authentication management utility.

Usage examples:
  PYTHONPATH=clean_project/src python clean_project/scripts/auth_management.py report-legacy
  PYTHONPATH=clean_project/src python clean_project/scripts/auth_management.py create-reset-tokens --limit 100 --output reset_tokens.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime, timedelta
from typing import List, Tuple

from agent_system.auth_models import (
    PasswordResetModel,
    UserModel,
    generate_secure_token,
    hash_token,
)
from agent_system.auth_models import (
    db_manager as auth_db,
)


def _hash_type(hashed_password: str) -> str:
    if not hashed_password:
        return "empty"
    if hashed_password.startswith("$argon2"):
        return "argon2"
    if hashed_password.startswith("$5$"):
        return "sha256_crypt"
    if len(hashed_password) == 64 and all(c in "0123456789abcdefABCDEF" for c in hashed_password):
        return "hex_sha256"
    return "unknown"


def report_legacy() -> Tuple[int, List[Tuple[str, str, str]]]:
    auth_db.initialize()
    legacy: List[Tuple[str, str, str]] = []
    with auth_db.get_session() as session:
        for user in session.query(UserModel).all():
            ht = _hash_type(user.hashed_password or "")
            if ht != "argon2":
                legacy.append((user.id, user.username, ht))
    print(f"Total users: {len(legacy)} legacy users listed below (id, username, type):")
    for uid, uname, ht in legacy:
        print(uid, uname, ht)
    return len(legacy), legacy


def create_reset_tokens(limit: int | None, output: str | None) -> int:
    auth_db.initialize()
    created = 0
    rows: List[Tuple[str, str, str]] = []
    with auth_db.get_session() as session:
        q = session.query(UserModel).all()
        for user in q:
            if limit is not None and created >= limit:
                break
            ht = _hash_type(user.hashed_password or "")
            if ht == "argon2":
                continue
            # Create a reset token (24h expiry)
            raw_token = generate_secure_token(32)
            token_h = hash_token(raw_token)
            pr = PasswordResetModel(
                user_id=user.id,
                token_hash=token_h,
                email=user.email,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
            session.add(pr)
            session.commit()
            rows.append((user.username, user.email, raw_token))
            created += 1

    if output:
        with open(output, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["username", "email", "reset_token"])
            w.writerows(rows)
        print(f"Wrote {len(rows)} reset tokens to {output}")
    else:
        print("username,email,reset_token")
        for r in rows:
            print(",".join(r))
    return created


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description="Authentication Management Utility")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("report-legacy", help="Report users whose password hashes are not argon2")

    c = sub.add_parser(
        "create-reset-tokens",
        help="Create password reset tokens for legacy users and output CSV",
    )
    c.add_argument("--limit", type=int, default=None, help="Max users to process")
    c.add_argument("--output", type=str, default=None, help="Output CSV filepath")

    args = p.parse_args(argv)
    if args.cmd == "report-legacy":
        count, _ = report_legacy()
        return 0 if count >= 0 else 1
    if args.cmd == "create-reset-tokens":
        created = create_reset_tokens(args.limit, args.output)
        return 0 if created >= 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
