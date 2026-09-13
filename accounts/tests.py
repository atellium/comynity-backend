from django.contrib import admin
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from unittest.mock import patch

from accounts.services import OTPServiceError, send_otp, verify_otp

from accounts.forms import UserAddForm
from accounts.models import PROFILE_COLORS, User


class OptionalEmailTests(TestCase):
    def test_new_user_receives_profile_color_from_palette(self):
        user = User.objects.create_user(phone="+919876543209")

        self.assertIn(user.profile_color, PROFILE_COLORS)

    def test_multiple_users_can_be_saved_with_blank_email(self):
        first_user = User.objects.create_user(phone="+919876543210", email="")
        second_user = User.objects.create_user(phone="+919876543211", email="  ")

        first_user.refresh_from_db()
        second_user.refresh_from_db()
        self.assertIsNone(first_user.email)
        self.assertIsNone(second_user.email)

    def test_email_is_trimmed_and_normalized(self):
        user = User.objects.create_user(
            phone="+919876543210", email="  USER@Example.COM  "
        )

        user.refresh_from_db()
        self.assertEqual(user.email, "user@example.com")


class PasswordlessUserTests(TestCase):
    def test_directly_saved_user_gets_an_unusable_password(self):
        user = User(phone="+919876543212", full_name="Passwordless User")
        user.save()

        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

    def test_admin_add_form_does_not_require_password(self):
        form = UserAddForm(
            data={
                "phone": "+919876543213",
                "full_name": "Admin-created User",
                "email": "",
                "is_active": True,
                "is_staff": False,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertFalse(user.has_usable_password())

    def test_admin_uses_passwordless_add_form(self):
        self.assertIs(admin.site._registry[User].add_form, UserAddForm)


@override_settings(
    ENVIRONMENT="dev",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    OTP_EXPIRY_SECONDS=300,
    OTP_LENGTH=6,
    OTP_MAX_VERIFY_ATTEMPTS=5,
    SECURE_SSL_REDIRECT=False,
)
class OTPAPITests(APITestCase):
    def test_send_and_verify_otp(self):
        sent = self.client.post(
            reverse("accounts:otp-send"),
            {"identifier": "+919876543210"},
            format="json",
        )
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertEqual(len(sent.data["otp"]), 6)

        verified = self.client.post(
            reverse("accounts:otp-verify"),
            {"req_id": sent.data["req_id"], "otp": sent.data["otp"]},
            format="json",
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.assertEqual(verified.data["type"], "success")
        self.assertIn("access_token", verified.data)
        self.assertIn("refresh_token", verified.data)
        self.assertNotIn("reqId", verified.data)
        self.assertNotIn("identifier", verified.data)
        self.assertEqual(verified.data["user"]["phone"], "+919876543210")
        self.assertTrue(User.objects.filter(phone="+919876543210").exists())

    def test_resend_otp(self):
        sent = self.client.post(
            reverse("accounts:otp-send"),
            {"identifier": "USER@example.com"},
            format="json",
        ).data
        resent = self.client.post(
            reverse("accounts:otp-resend"),
            {"req_id": sent["req_id"]},
            format="json",
        )
        self.assertEqual(resent.status_code, status.HTTP_200_OK)
        self.assertEqual(resent.data["reqId"], sent["req_id"])

    def test_invalid_identifier_is_rejected(self):
        response = self.client.post(
            reverse("accounts:otp-send"),
            {"identifier": "9876543210"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OTP_MAX_VERIFY_ATTEMPTS=2)
    def test_too_many_invalid_attempts_invalidates_request(self):
        sent = self.client.post(
            reverse("accounts:otp-send"),
            {"identifier": "+919876543210"},
            format="json",
        ).data
        payload = {"req_id": sent["req_id"], "otp": "000000"}
        first = self.client.post(reverse("accounts:otp-verify"), payload, format="json")
        second = self.client.post(reverse("accounts:otp-verify"), payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(ENVIRONMENT="prod")
    @patch("accounts.views.send_otp")
    def test_msg91_error_body_is_returned_to_client(self, mocked_send):
        provider_error = {
            "type": "error",
            "message": "Mobile number is invalid",
        }
        mocked_send.side_effect = OTPServiceError(
            provider_error["message"], 400, provider_error
        )

        response = self.client.post(
            reverse("accounts:otp-send"),
            {"identifier": "+919876543210"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, provider_error)

    @override_settings(ENVIRONMENT="prod")
    @patch("accounts.services._msg91_request")
    def test_msg91_message_is_used_as_request_id(self, msg91_request):
        request_id = "3667416a3777353332333130"
        msg91_request.side_effect = [
            {"message": request_id, "type": "success"},
            {"message": "provider-jwt", "type": "success"},
        ]

        sent = send_otp("+919876543210")
        result = verify_otp(request_id, "123456")

        self.assertEqual(sent, {"req_id": request_id, "type": "success"})
        self.assertEqual(result["message"], "OTP verified successfully.")
        self.assertEqual(result["user"]["phone"], "+919876543210")
        self.assertIn("access_token", result)
        self.assertIn("refresh_token", result)


class UserProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919876543210")

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("accounts:user-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("accounts:user-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["id"], str(self.user.id))
        self.assertEqual(response.data["user"]["phone"], self.user.phone)

    def test_update_profile(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            reverse("accounts:user-me"),
            {
                "email": "TEST.USER@example.com",
                "full_name": "Test User",
                "gender": User.GenderChoice.OTHER,
                "date_of_birth": "2000-01-15",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], "test.user@example.com")
        self.assertEqual(response.data["user"]["full_name"], "Test User")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test.user@example.com")
        self.assertEqual(self.user.full_name, "Test User")

    def test_phone_cannot_be_updated(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            reverse("accounts:user-me"),
            {"phone": "+919999999999"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+919876543210")


class RefreshTokenAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919876543210")

    def test_refresh_token_returns_new_access_token(self):
        refresh_token = str(RefreshToken.for_user(self.user))

        response = self.client.post(
            reverse("accounts:token-refresh"),
            {"refresh_token": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        access_token = AccessToken(response.data["access_token"])
        self.assertEqual(str(access_token["user_id"]), str(self.user.id))

    @override_settings(
        SIMPLE_JWT={
            **settings.SIMPLE_JWT,
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": False,
        }
    )
    def test_refresh_token_returns_rotated_refresh_token_when_enabled(self):
        refresh_token = str(RefreshToken.for_user(self.user))

        response = self.client.post(
            reverse("accounts:token-refresh"),
            {"refresh_token": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        self.assertNotEqual(response.data["refresh_token"], refresh_token)

    def test_invalid_refresh_token_is_rejected(self):
        response = self.client.post(
            reverse("accounts:token-refresh"),
            {"refresh_token": "invalid-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_is_required(self):
        response = self.client.post(
            reverse("accounts:token-refresh"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
