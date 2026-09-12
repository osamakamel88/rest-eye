from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional
from ..db.session import get_db
from ..db.models import User, Organization
from ..db.crud import get_user_by_email, get_organization
from .security import decode_token

def get_token_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization

def get_current_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        # Fallback to default demo user if unauthenticated for local testing
        user = db.query(User).first()
        if user:
            return user
        raise credentials_exception

    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise credentials_exception

    email = payload.get("sub")
    user = get_user_by_email(db, email)
    if not user:
        raise credentials_exception
    return user

def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Organization:
    org = get_organization(db, current_user.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant organization not found"
        )
    return org

def get_optional_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not token:
        return db.query(User).first()
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    return get_user_by_email(db, payload.get("sub"))
