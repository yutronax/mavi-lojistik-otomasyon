"""
Role-Based Access Control (RBAC) for Server Operations
"""

from enum import Enum
from typing import List, Dict


class UserRole(Enum):
    """User roles with different permission levels"""
    ADMIN = "admin"  # Full access to everything
    OPERATOR = "operator"  # Can restart, view logs, view metrics
    VIEWER = "viewer"  # Read-only access


class Permission(Enum):
    """Available permissions"""
    # View permissions
    VIEW_STATUS = "view_status"
    VIEW_LOGS = "view_logs"
    VIEW_METRICS = "view_metrics"
    VIEW_OPERATIONS = "view_operations"

    # Control permissions
    RESTART_SERVICE = "restart_service"
    STOP_SERVICE = "stop_service"
    START_SERVICE = "start_service"

    # Deployment permissions
    GIT_PULL = "git_pull"
    VIEW_BACKUPS = "view_backups"
    ROLLBACK = "rollback"

    # Configuration permissions
    MANAGE_SETTINGS = "manage_settings"
    MANAGE_USERS = "manage_users"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.VIEW_STATUS,
        Permission.VIEW_LOGS,
        Permission.VIEW_METRICS,
        Permission.VIEW_OPERATIONS,
        Permission.RESTART_SERVICE,
        Permission.STOP_SERVICE,
        Permission.START_SERVICE,
        Permission.GIT_PULL,
        Permission.VIEW_BACKUPS,
        Permission.ROLLBACK,
        Permission.MANAGE_SETTINGS,
        Permission.MANAGE_USERS,
    ],
    UserRole.OPERATOR: [
        Permission.VIEW_STATUS,
        Permission.VIEW_LOGS,
        Permission.VIEW_METRICS,
        Permission.VIEW_OPERATIONS,
        Permission.RESTART_SERVICE,
        Permission.STOP_SERVICE,
        Permission.START_SERVICE,
        Permission.VIEW_BACKUPS,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_STATUS,
        Permission.VIEW_LOGS,
        Permission.VIEW_METRICS,
        Permission.VIEW_OPERATIONS,
    ],
}


class AccessControl:
    """Manage user roles and permissions"""

    def __init__(self):
        self.current_user_role = UserRole.ADMIN  # Default to admin for backward compatibility

    def has_permission(self, permission: Permission) -> bool:
        """Check if current user has permission"""
        permissions = ROLE_PERMISSIONS.get(self.current_user_role, [])
        return permission in permissions

    def require_permission(self, permission: Permission) -> bool:
        """Require permission, return True if allowed, False otherwise"""
        if not self.has_permission(permission):
            raise PermissionError(f"Permission denied: {permission.value}")
        return True

    def set_user_role(self, role: UserRole):
        """Set current user role"""
        self.current_user_role = role

    def get_allowed_operations(self) -> List[str]:
        """Get list of allowed operations for current role"""
        operations = []

        if self.has_permission(Permission.RESTART_SERVICE):
            operations.append("restart")
        if self.has_permission(Permission.STOP_SERVICE):
            operations.append("stop")
        if self.has_permission(Permission.START_SERVICE):
            operations.append("start")
        if self.has_permission(Permission.GIT_PULL):
            operations.append("git_pull")
        if self.has_permission(Permission.ROLLBACK):
            operations.append("rollback")

        return operations

    def get_role_description(self) -> Dict[str, str]:
        """Get description of current role and its permissions"""
        permissions = ROLE_PERMISSIONS.get(self.current_user_role, [])
        permission_names = [p.value for p in permissions]

        descriptions = {
            UserRole.ADMIN: "Sistem yöneticisi - Tüm işlemlere erişim",
            UserRole.OPERATOR: "Operatör - Servis kontrolü ve deployment",
            UserRole.VIEWER: "İzleyici - Sadece okuma erişimi"
        }

        return {
            "role": self.current_user_role.value,
            "description": descriptions.get(self.current_user_role, "Unknown"),
            "permissions": permission_names
        }


# Global instance
_access_control = None


def get_access_control():
    global _access_control
    if _access_control is None:
        _access_control = AccessControl()
    return _access_control
