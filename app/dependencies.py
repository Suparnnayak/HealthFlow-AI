from typing import Optional, List, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.models import User, UserHospitalAccess
from app.auth.security import decode_access_token
from database.session import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user_and_claims(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Tuple[User, dict]:
    """
    Returns (user, token_payload) or raises 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    try:
        user_id = UUID(str(sub))
    except ValueError:
        raise credentials_exception

    user: Optional[User] = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user, payload


def get_current_user(
    user_claims: Tuple[User, dict] = Depends(get_current_user_and_claims),
) -> User:
    """FastAPI dependency returning current active user."""
    return user_claims[0]


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the current user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def get_effective_hospital_ids(
    db: Session,
    user: User,
    token_claims: dict,
) -> List[str]:
    """
    Extract hospital IDs for user:
    - If admin: returns empty list (signaling full network access).
    - If hospital_staff or legacy role: checks token claims first, falls back to DB query.
    - If user has no assignments yet, auto-assigns the first available hospital in DB so they have immediate scoped access.
    """
    if user.role == "admin":
        return []

    token_hospitals = token_claims.get("hospital_ids")
    if token_hospitals:
        return [str(h).strip() for h in token_hospitals if str(h).strip()]

    # Fallback to DB
    records = db.query(UserHospitalAccess.hospital_id).filter(UserHospitalAccess.user_id == user.id).all()
    assigned = [r[0] for r in records]
    if assigned:
        return assigned

    # If staff/user has no assigned hospital yet, assign a default hospital from the database
    from database.models import Hospital
    first_hosp = db.query(Hospital.hospital_id).order_by(Hospital.hospital_id).first()
    if first_hosp:
        default_id = first_hosp[0]
        access = UserHospitalAccess(user_id=user.id, hospital_id=default_id)
        db.add(access)
        db.commit()
        return [default_id]

    return []


def require_hospital_access(
    hospitals: Optional[str] = Query(None, description="Comma-separated hospital IDs"),
    user_claims: Tuple[User, dict] = Depends(get_current_user_and_claims),
    db: Session = Depends(get_db),
) -> Tuple[User, Optional[List[str]]]:
    """
    Hospital-scoped authorization dependency.
    
    Rules:
    1. If user.role == 'admin':
       - If hospitals param passed: returns those hospital IDs.
       - If no param: returns None (all hospitals allowed).
    2. If user.role == 'hospital_staff' (or other non-admin):
       - Allowed list = user's assigned hospital_ids.
       - If hospitals param passed:
         - Parses requested IDs.
         - Checks if any requested hospital is NOT in allowed list.
         - If any unauthorized: raises 403.
         - Otherwise returns the requested IDs.
       - If no hospitals param passed:
         - Automatically scopes query to the user's allowed list!
    """
    user, claims = user_claims

    if user.role == "admin":
        if hospitals:
            requested = [h.strip() for h in hospitals.split(",") if h.strip()]
            return user, requested
        return user, None

    # Staff user
    allowed = get_effective_hospital_ids(db, user, claims)
    if not allowed:
        # Fallback to all if database has no hospitals registered yet
        return user, []

    if hospitals:
        requested = [h.strip() for h in hospitals.split(",") if h.strip()]
        unauthorized = set(requested) - set(allowed)
        if unauthorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to hospitals: {sorted(unauthorized)}",
            )
        return user, requested

    # If no hospital specified, default to user's allowed list
    return user, allowed



