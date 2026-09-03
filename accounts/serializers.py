import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class SendOTPSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)

    def validate_identifier(self, value):
        value = value.strip()
        if "@" in value:
            try:
                validate_email(value)
            except DjangoValidationError as exc:
                raise serializers.ValidationError("Enter a valid email address.") from exc
            return value.lower()

        normalized = re.sub(r"[\s()\-]", "", value)
        if not PHONE_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError(
                "Enter a phone number in international E.164 format."
            )
        return normalized


class ResendOTPSerializer(serializers.Serializer):
    req_id = serializers.CharField(max_length=255)
    retry_channel = serializers.CharField(
        max_length=100, required=False, allow_blank=False
    )


class VerifyOTPSerializer(serializers.Serializer):
    req_id = serializers.CharField(max_length=255)
    otp = serializers.RegexField(regex=r"^\d+$", max_length=10, min_length=4)


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, attrs):
        serializer = TokenRefreshSerializer(data={"refresh": attrs["refresh_token"]})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc
        tokens = {"access_token": serializer.validated_data["access"]}
        if "refresh" in serializer.validated_data:
            tokens["refresh_token"] = serializer.validated_data["refresh"]
        return tokens


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def save(self, **kwargs):
        try:
            RefreshToken(self.validated_data["refresh_token"]).blacklist()
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc


class AuthUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone",
            "full_name",
            "gender",
            "date_of_birth",
            "profile_color",
        )
        read_only_fields = ("profile_color",)


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "full_name", "gender", "date_of_birth")
        extra_kwargs = {
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            "full_name": {"required": False, "allow_null": True, "allow_blank": True},
            "gender": {"required": False, "allow_null": True},
            "date_of_birth": {"required": False, "allow_null": True},
        }
