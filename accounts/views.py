from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AuthUserSerializer,
    LogoutSerializer,
    RefreshTokenSerializer,
    ResendOTPSerializer,
    SendOTPSerializer,
    UserProfileUpdateSerializer,
    VerifyOTPSerializer,
)
from .services import OTPServiceError, resend_otp, send_otp, verify_otp
from core.throttles import (
    OTPResendThrottle,
    OTPSendThrottle,
    OTPVerifyThrottle,
    TokenRefreshThrottle,
)


def _run(serializer_class, request, operation):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        return Response(operation(**serializer.validated_data))
    except OTPServiceError as exc:
        body = exc.data or {"type": "error", "message": str(exc)}
        return Response(body, status=exc.status_code)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OTPSendThrottle])
def send(request):
    return _run(SendOTPSerializer, request, send_otp)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OTPResendThrottle])
def resend(request):
    return _run(ResendOTPSerializer, request, resend_otp)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OTPVerifyThrottle])
def verify(request):
    return _run(VerifyOTPSerializer, request, verify_otp)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([TokenRefreshThrottle])
def refresh_token(request):
    serializer = RefreshTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    serializer = LogoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(status=204)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": AuthUserSerializer(request.user).data})

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Profile updated successfully.",
                "user": AuthUserSerializer(user).data,
            }
        )
