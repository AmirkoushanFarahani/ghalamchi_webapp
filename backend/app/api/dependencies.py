from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.tokens import InvalidAccessTokenError, decode_access_claims
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id, session_version = decode_access_claims(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise unauthorized from exc
    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active or user.session_version != session_version:
        raise unauthorized
    return user


def require_authenticated_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


def require_permission(permission: str) -> Callable[[User], User]:
    def permission_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if permission not in current_user.permission_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )
        return current_user

    return permission_dependency
