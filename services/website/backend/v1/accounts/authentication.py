from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class ActiveUserJWTAuthentication(JWTAuthentication):
    """JWT 认证后额外校验用户存在且 is_active。

    被 Root Admin 禁用的用户,即使其旧 access token 尚未过期,也立即无法访问。
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user.is_active:
            raise AuthenticationFailed('用户已被禁用', code='user_inactive')
        return user
