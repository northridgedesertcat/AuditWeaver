from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

UserModel = get_user_model()


class LoginSerializer(TokenObtainPairSerializer):
    """复用 simplejwt 的 username/password 校验,返回 access + refresh。

    ModelBackend.authenticate 内部已校验 is_active,禁用用户无法登录。
    """
    pass


class ActiveUserTokenRefreshSerializer(TokenRefreshSerializer):
    """刷新时再查一次库:用户不存在或已被禁用则拒绝换新 access。"""

    def validate(self, attrs):
        # 构造时即完成签名/过期/黑名单校验,非法 token 在此抛 TokenError
        try:
            refresh = RefreshToken(attrs['refresh'])
        except TokenError:
            raise serializers.ValidationError('refresh token 无效或已过期',
                                              code='token_not_valid')
        user_id = refresh.get(api_settings.USER_ID_CLAIM)
        try:
            user = UserModel.objects.get(id=user_id)
        except UserModel.DoesNotExist:
            raise serializers.ValidationError('用户不存在', code='user_not_found')
        if not user.is_active:
            raise serializers.ValidationError('用户已被禁用', code='user_inactive')
        return super().validate(attrs)


class UserSerializer(serializers.ModelSerializer):
    is_root_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role',
            'display_name', 'is_active', 'is_root_admin',
        ]


class AdminCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'display_name', 'is_active']
        read_only_fields = ['id', 'is_active']

    def validate_password(self, value):
        # 用一个未保存的实例做相似度等校验
        validate_password(value, user=self.instance or UserModel())
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        # 强制普通 Admin 角色,忽略任何外部传入的 role
        validated_data['role'] = User.Role.ADMIN
        user = UserModel(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(style={'input_type': 'password'})
    new_password = serializers.CharField(style={'input_type': 'password'})

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('原密码不正确')
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(style={'input_type': 'password'})

    def validate_new_password(self, value):
        target_user = self.context.get('target_user')
        validate_password(value, user=target_user)
        return value
