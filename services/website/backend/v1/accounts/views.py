from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, UserSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        return Response({
            'access': ser.validated_data['access'],
            'refresh': ser.validated_data['refresh'],
        })


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
