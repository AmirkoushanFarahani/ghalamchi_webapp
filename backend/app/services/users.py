from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.db.models import Role, User
from backend.app.repositories.audit import AuditRepository
from backend.app.repositories.roles import RoleRepository
from backend.app.repositories.users import UserRepository
from backend.app.schemas.users import UserRolesUpdate, UserStatusUpdate


class UserManagementError(ValueError):
    pass


class UserNotFoundError(UserManagementError):
    pass


class UnknownRoleError(UserManagementError):
    pass


class UserManagementConflictError(UserManagementError):
    pass


class UserService:
    def __init__(self, session: Session, actor: User | None = None) -> None:
        self.session = session
        self.actor = actor
        self.repository = UserRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditRepository(session)

    def list_users(self) -> list[User]:
        if self.actor is not None and "ADMIN" not in self.actor.role_names:
            return list(
                self.session.scalars(
                    select(User)
                    .where(
                        or_(
                            User.id == self.actor.id,
                            User.school_manager_id == self.actor.id,
                        )
                    )
                    .order_by(User.created_at)
                )
            )
        return self.repository.list_users()

    def get_user(self, user_id: UUID) -> User:
        user = self.repository.get_by_id(user_id)
        if user is None or (
            self.actor is not None
            and "ADMIN" not in self.actor.role_names
            and user.id != self.actor.id
            and user.school_manager_id != self.actor.id
        ):
            raise UserNotFoundError("User not found")
        return user

    def replace_roles(self, user_id: UUID, data: UserRolesUpdate) -> User:
        self._lock_admin_role()
        user = self._get_for_update(user_id)
        requested_names = set(data.roles)
        roles = self.roles.get_by_names(requested_names)
        found_names = {role.name for role in roles}
        missing = sorted(requested_names - found_names)
        if missing:
            raise UnknownRoleError(f"Unknown role: {', '.join(missing)}")

        old_roles = user.role_names
        removing_admin = user.is_active and "ADMIN" in old_roles and "ADMIN" not in found_names
        if removing_admin and self.repository.active_admin_count() <= 1:
            raise UserManagementConflictError(
                "The system must retain at least one active administrator"
            )

        user.roles = roles
        user.session_version += 1
        self._audit_roles_changed(user, old_roles, sorted(found_names))
        self.session.commit()
        return user

    def set_status(self, user_id: UUID, data: UserStatusUpdate) -> User:
        self._lock_admin_role()
        user = self._get_for_update(user_id)
        if not data.is_active and self.actor is not None and user.id == self.actor.id:
            raise UserManagementConflictError("Administrators cannot deactivate their own account")
        if (
            user.is_active
            and not data.is_active
            and "ADMIN" in user.role_names
            and self.repository.active_admin_count() <= 1
        ):
            raise UserManagementConflictError(
                "The system must retain at least one active administrator"
            )

        old_status = user.is_active
        user.is_active = data.is_active
        user.session_version += 1
        self._audit_status_changed(user, old_status, data.is_active)
        self.session.commit()
        return user

    def _lock_admin_role(self) -> Role:
        role = self.roles.get_admin_for_update()
        if role is None:
            raise RuntimeError("The ADMIN role has not been bootstrapped")
        return role

    def _get_for_update(self, user_id: UUID) -> User:
        user = self.repository.get_by_id_for_update(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        return user

    def _audit_roles_changed(self, user: User, old_roles: list[str], new_roles: list[str]) -> None:
        self.audit.record(
            action="identity.user.roles_changed",
            resource_type="user",
            resource_id=str(user.id),
            actor_id=self.actor.id if self.actor is not None else None,
            success=True,
            details={
                "performed_by": str(self.actor.id) if self.actor is not None else None,
                "affected_user_id": str(user.id),
                "old_roles": old_roles,
                "new_roles": new_roles,
            },
        )

    def _audit_status_changed(self, user: User, old_status: bool, new_status: bool) -> None:
        self.audit.record(
            action="identity.user.status_changed",
            resource_type="user",
            resource_id=str(user.id),
            actor_id=self.actor.id if self.actor is not None else None,
            success=True,
            details={
                "performed_by": str(self.actor.id) if self.actor is not None else None,
                "affected_user_id": str(user.id),
                "old_is_active": old_status,
                "new_is_active": new_status,
            },
        )
