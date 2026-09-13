from rest_framework.permissions import BasePermission


class IsRootAdmin(BasePermission):
    """仅 Root Admin 可访问(管理员账户管理接口)。"""

    message = '需要 Root Admin 权限'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_root_admin
        )
