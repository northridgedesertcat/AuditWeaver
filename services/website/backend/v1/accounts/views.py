from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User
from .permissions import IsRootAdmin
from .serializers import (
    ActiveUserTokenRefreshSerializer,
    AdminCreateSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)


def blacklist_all_refresh_tokens(user):
    """将用户所有未失效的 refresh token 加入黑名单(改密/重置后强制重登)。"""
    outstanding = OutstandingToken.objects.filter(user=user)
    for token in outstanding:
        BlacklistedToken.objects.get_or_create(token=token)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        return Response({
            'access': ser.validated_data['access'],
            'refresh': ser.validated_data['refresh'],
        })


class ActiveTokenRefreshView(TokenRefreshView):
    """refresh 时二次校验用户仍存在且 is_active。"""
    serializer_class = ActiveUserTokenRefreshSerializer
    permission_classes = [AllowAny]


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class ChangePasswordView(APIView):
    """用户修改自己的密码;成功后作废其全部 refresh token。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        request.user.set_password(ser.validated_data['new_password'])
        request.user.save(update_fields=['password', 'updated_at'])
        blacklist_all_refresh_tokens(request.user)
        return Response({'detail': '密码修改成功,请重新登录'})


class AdminListCreateView(APIView):
    """Root Admin 列出/创建普通 Admin。"""
    permission_classes = [IsRootAdmin]

    def get(self, request):
        admins = User.objects.filter(role=User.Role.ADMIN).order_by('-date_joined')
        return Response(UserSerializer(admins, many=True).data)

    def post(self, request):
        ser = AdminCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class _AdminTargetMixin:
    """统一的目标管理员加载与保护逻辑。"""

    def get_target_admin(self, request, pk):
        """返回 (user, None) 或 (None, error_response)。"""
        try:
            target = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None, Response(
                {'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND,
            )
        if target.role == User.Role.ROOT_ADMIN:
            return None, Response(
                {'detail': 'Root Admin 不可被管理'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.id == request.user.id:
            return None, Response(
                {'detail': '不能对自己执行该操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return target, None


class AdminDisableView(_AdminTargetMixin, APIView):
    permission_classes = [IsRootAdmin]

    def patch(self, request, pk):
        target, err = self.get_target_admin(request, pk)
        if err:
            return err
        if not target.is_active:
            return Response(
                {'detail': '该用户已是禁用状态'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target.is_active = False
        target.save(update_fields=['is_active', 'updated_at'])
        blacklist_all_refresh_tokens(target)
        return Response(UserSerializer(target).data)


class AdminEnableView(_AdminTargetMixin, APIView):
    permission_classes = [IsRootAdmin]

    def patch(self, request, pk):
        target, err = self.get_target_admin(request, pk)
        if err:
            return err
        if target.is_active:
            return Response(
                {'detail': '该用户已是启用状态'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target.is_active = True
        target.save(update_fields=['is_active', 'updated_at'])
        return Response(UserSerializer(target).data)


class AdminResetPasswordView(_AdminTargetMixin, APIView):
    """Root Admin 重置普通 Admin 密码;成功后作废其全部 refresh token。"""
    permission_classes = [IsRootAdmin]

    def post(self, request, pk):
        target, err = self.get_target_admin(request, pk)
        if err:
            return err
        ser = ResetPasswordSerializer(
            data=request.data, context={'target_user': target},
        )
        ser.is_valid(raise_exception=True)
        target.set_password(ser.validated_data['new_password'])
        target.save(update_fields=['password', 'updated_at'])
        blacklist_all_refresh_tokens(target)
        return Response({'detail': '密码已重置'})


class AdminDeleteView(_AdminTargetMixin, APIView):
    """删除普通 Admin(推荐优先使用禁用)。"""
    permission_classes = [IsRootAdmin]

    def delete(self, request, pk):
        target, err = self.get_target_admin(request, pk)
        if err:
            return err
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
