"""Test authentication utilities for audit tests."""

from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User
from app.crud.common import require_by_id
from app.models.enums import UserRole, UserStatus


def get_or_create_test_user(db: Session, role: UserRole = UserRole.MANAGER) -> User:
    """Get or create a test user for audit tests.
    
    In Supabase mode, this retrieves an existing user from the database.
    In local_test mode, this creates a temporary test user.
    
    Args:
        db: Database session
        role: User role (default: MANAGER)
    
    Returns:
        User object suitable for testing
    """
    from app.core.config import settings
    from app.models.cooperative import Cooperative
    
    test_user: Optional[User] = None

    # In Supabase mode, try to get first active manager/admin
    if settings.is_supabase_mode:
        try:
            # First try to get existing active user
            user = db.query(User).filter(
                User.role.in_([UserRole.ADMIN, UserRole.MANAGER]),
                User.status == UserStatus.ACTIVE
            ).first()
            
            if user:
                return user
            
            # If no active users, get any user with a cooperative
            user = db.query(User).filter(
                User.status == UserStatus.ACTIVE,
                User.cooperative_id.isnot(None)
            ).first()
            
            if user:
                return user
        except Exception:
            pass
    
    # Fallback: create temporary user with proper cooperative assignment
    try:
        # Get or create a test cooperative
        coop = db.query(Cooperative).first()
        if not coop:
            coop = Cooperative(
                name="Test Cooperative",
                region="Test",
                address="Test Address",
                phone="+221770000000",
            )
            db.add(coop)
            db.flush()
        
        test_user = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            full_name="Test Audit User",
            email="audit-test@test.local",
            password_hash="$2b$12$test",
            phone="+221770000000",
            role=role,
            status=UserStatus.ACTIVE,
            cooperative_id=coop.id,
        )
        
        # Try to add to session (may fail if user already exists)
        db.add(test_user)
        db.commit()
    except Exception:
        # User likely exists, retrieve it
        try:
            test_user = require_by_id(db, User, UUID("00000000-0000-0000-0000-000000000001"), "User")
        except Exception:
            test_user = (
                db.query(User)
                .filter(User.status == UserStatus.ACTIVE, User.cooperative_id.isnot(None))
                .first()
            )

    if test_user is None:
        raise RuntimeError("Unable to resolve a valid audit test user for authenticated /chat/agent calls.")

    return test_user


def create_test_token(user_id: str | UUID, expires_delta: Optional[timedelta] = None) -> str:
    """Create a valid JWT token for testing.
    
    Args:
        user_id: User ID as string or UUID
        expires_delta: Token expiration time (default: 1 hour)
    
    Returns:
        Valid JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=1)
    
    return create_access_token(str(user_id), expires_delta=expires_delta)


def get_test_auth_header(user_id: str | UUID) -> dict[str, str]:
    """Get Authorization header for test requests.
    
    Args:
        user_id: User ID as string or UUID
    
    Returns:
        Dict with "Authorization" key containing Bearer token
    """
    token = create_test_token(user_id)
    return {"Authorization": f"Bearer {token}"}
