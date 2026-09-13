from django.urls import path

from .views import (
    ActiveTokenRefreshView,
    AdminDeleteView,
    AdminDisableView,
    AdminEnableView,
    AdminListCreateView,
    AdminResetPasswordView,
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
)

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', ActiveTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),

    # Root Admin 管理普通 Admin(IsRootAdmin)
    path('auth/admins/', AdminListCreateView.as_view(), name='admin_list_create'),
    path('auth/admins/<int:pk>/disable/', AdminDisableView.as_view(), name='admin_disable'),
    path('auth/admins/<int:pk>/enable/', AdminEnableView.as_view(), name='admin_enable'),
    path('auth/admins/<int:pk>/reset-password/', AdminResetPasswordView.as_view(), name='admin_reset_password'),
    path('auth/admins/<int:pk>/', AdminDeleteView.as_view(), name='admin_delete'),
]
