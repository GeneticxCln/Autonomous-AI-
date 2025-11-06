"""
Debug script to understand password authentication
"""
import sys
import hashlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.auth_models import db_manager
from agent_system.auth_service import auth_service

def debug_password_auth():
    """Debug password authentication."""
    print("🔍 Debugging Password Authentication")

    # Initialize
    db_manager.initialize()

    with auth_service.db.get_session() as session:
        from agent_system.auth_models import UserModel

        # Get admin user
        user = session.query(UserModel).filter(UserModel.username == "admin").first()

        if user:
            print(f"✅ Found admin user: {user.username}")
            print(f"   Password hash: {user.hashed_password}")

            # Test password "admin"
            test_password = "admin"
            expected_hash = hashlib.sha256(test_password.encode()).hexdigest()
            print(f"   Expected hash for '{test_password}': {expected_hash}")
            print(f"   Hash match: {user.hashed_password == expected_hash}")

            # Check if user.check_password works
            try:
                check_result = user.check_password(test_password)
                print(f"   user.check_password() result: {check_result}")
            except Exception as e:
                print(f"   user.check_password() error: {e}")

        else:
            print("❌ Admin user not found")

if __name__ == "__main__":
    debug_password_auth()