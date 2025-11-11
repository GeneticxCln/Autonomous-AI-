"""
Authentication System Setup Script
Creates auth tables and initializes default data
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional, cast

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.auth_models import Base, UserModel, db_manager
from agent_system.auth_service import auth_service

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def setup_authentication_system() -> None:
    """Setup authentication system with default data."""
    logger.info("Setting up authentication system...")

    try:
        # Initialize database connection
        db_manager.initialize()
        logger.info("✅ Database connection established")

        # Create all auth tables
        Base.metadata.create_all(bind=db_manager.engine)
        logger.info("✅ Authentication tables created")

        # Initialize default roles and permissions
        auth_service.initialize()
        logger.info("✅ Default roles and permissions created")

        # Create default admin user
        admin_user = create_default_admin()
        if admin_user is None:
            logger.error("Failed to create admin user")
            raise RuntimeError("Failed to create admin user")
        
        logger.info(f"✅ Default admin user created: {admin_user.username}")

        # Create API token for admin
        api_token = auth_service.create_api_token(
            admin_user.id, "Default Admin Token", ["read", "write", "admin"]
        )
        logger.info(f"✅ Admin API token created: {api_token[:8]}...")

        logger.info("🎉 Authentication system setup completed successfully!")

        print_auth_info(admin_user, api_token)

    except Exception as e:
        logger.error(f"❌ Authentication system setup failed: {e}")
        raise


def create_default_admin() -> Optional[UserModel]:
    """Create default admin user."""
    try:
        # Check if admin user already exists
        with db_manager.get_session() as session:
            existing_admin = session.query(UserModel).filter(UserModel.username == "admin").first()
            if existing_admin:
                logger.info("Admin user already exists")
                return cast(Optional[UserModel], existing_admin)

        # Create admin user
        admin_user = auth_service.create_user(
            username="admin",
            email="admin@example.com",
            password="admin",  # Simple password
            full_name="System Administrator",
            role_names=["admin"],
        )

        return admin_user

    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        raise


def print_auth_info(admin_user: UserModel, api_token: str) -> None:
    """Print authentication system information."""
    print("\n" + "=" * 60)
    print("🔐 AUTHENTICATION SYSTEM SETUP COMPLETE")
    print("=" * 60)
    print(f"Admin Username: {admin_user.username}")
    print(f"Admin Email: {admin_user.email}")
    print("Admin Password: admin (CHANGE THIS IMMEDIATELY)")
    print(f"Admin API Token: {api_token}")
    print(f"API Token Prefix: {api_token[:8]}")
    print("\n⚠️  SECURITY REMINDERS:")
    print("1. Change admin password immediately after first login")
    print("2. Store API tokens securely - they are only shown once")
    print("3. Use environment variables for JWT secret in production")
    print("4. Enable HTTPS for all authentication endpoints")
    print("=" * 60)
    print("\n📋 Available Roles:")
    print("• admin - Full system access")
    print("• manager - Elevated privileges")
    print("• user - Standard access")
    print("• guest - Limited access")
    print("\n🔑 Default Permissions:")
    print("• agent.read/write/execute/admin")
    print("• goals.read/write/delete")
    print("• actions.read/write")
    print("• system.read/write/admin")
    print("• users.read/write/delete/admin")
    print("=" * 60)


if __name__ == "__main__":
    setup_authentication_system()
