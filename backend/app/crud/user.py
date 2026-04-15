from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))
