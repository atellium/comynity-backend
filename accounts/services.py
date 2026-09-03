import json
import secrets
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import AuthUserSerializer


MSG91_BASE_URL = "https://api.msg91.com/api/v5/widget"
CACHE_PREFIX = "auth:otp:"


class OTPServiceError(Exception):
    def __init__(self, message, status_code=502, data=None):
        super().__init__(message)
        self.status_code = status_code
        self.data = data


def _cache_key(req_id):
    return f"{CACHE_PREFIX}{req_id}"


def _generate_otp():
    lower = 10 ** (settings.OTP_LENGTH - 1)
    return str(secrets.randbelow(9 * lower) + lower)


def _msg91_request(endpoint, payload):
    if not settings.MSG_AUTH_KEY or not settings.MSG_WIDGET_ID:
        raise OTPServiceError("MSG91 credentials are not configured.", 503)
    payload = {"widgetId": settings.MSG_WIDGET_ID, **payload}
    request = Request(
        f"{MSG91_BASE_URL}/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"authkey": settings.MSG_AUTH_KEY, "content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.MSG91_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            try:
                data = json.loads(body) if body else {}
            except ValueError as exc:
                raise OTPServiceError(
                    body or "OTP provider returned an invalid response.",
                    502,
                    {
                        "type": "error",
                        "message": body or "OTP provider returned an invalid response.",
                    },
                ) from exc
            if isinstance(data, dict) and str(data.get("type", "")).lower() in {
                "error",
                "failure",
                "failed",
            }:
                raise OTPServiceError(
                    data.get("message", "OTP provider rejected the request."),
                    400,
                    data,
                )
            return data
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw_body)
        except ValueError:
            data = {
                "type": "error",
                "message": raw_body or "OTP provider rejected the request.",
            }
        message = (
            data.get("message", "OTP provider rejected the request.")
            if isinstance(data, dict)
            else "OTP provider rejected the request."
        )
        raise OTPServiceError(message, exc.code, data) from exc
    except (URLError, TimeoutError) as exc:
        raise OTPServiceError("OTP provider is unavailable.") from exc


def send_otp(identifier):
    if settings.ENVIRONMENT == "prod":
        response = _msg91_request("sendOtp", {"identifier": identifier})
        req_id = (
            response.get("reqId")
            or response.get("requestId")
            or response.get("message")
        )
        if req_id:
            cache.set(
                _cache_key(req_id),
                {"identifier": identifier},
                settings.OTP_EXPIRY_SECONDS,
            )
        normalized_response = {
            key: value
            for key, value in response.items()
            if key not in {"message", "reqId", "requestId"}
        }
        normalized_response["req_id"] = req_id
        return normalized_response
    req_id = str(uuid.uuid4())
    otp = _generate_otp()
    cache.set(
        _cache_key(req_id),
        {"identifier": identifier, "otp": otp, "attempts": 0},
        settings.OTP_EXPIRY_SECONDS,
    )
    return {
        "type": "success",
        "req_id": req_id,
        "otp": otp,
        "expiresIn": settings.OTP_EXPIRY_SECONDS,
    }


def resend_otp(req_id, retry_channel=None):
    if settings.ENVIRONMENT == "prod":
        record = cache.get(_cache_key(req_id))
        payload = {"reqId": req_id}
        if retry_channel:
            payload["retryChannel"] = retry_channel
        response = _msg91_request("retryOtp", payload)
        new_req_id = (
            response.get("reqId")
            or response.get("requestId")
            or response.get("message")
        )
        if record and new_req_id:
            cache.set(
                _cache_key(new_req_id),
                record,
                settings.OTP_EXPIRY_SECONDS,
            )
            if new_req_id != req_id:
                cache.delete(_cache_key(req_id))
        return response
    record = cache.get(_cache_key(req_id))
    if not record:
        raise OTPServiceError("OTP request was not found or has expired.", 404)
    otp = _generate_otp()
    record.update(otp=otp, attempts=0)
    cache.set(_cache_key(req_id), record, settings.OTP_EXPIRY_SECONDS)
    return {
        "type": "success",
        "message": "OTP regenerated successfully.",
        "reqId": req_id,
        "otp": otp,
        "expiresIn": settings.OTP_EXPIRY_SECONDS,
    }


def verify_otp(req_id, otp):
    if settings.ENVIRONMENT == "prod":
        response = _msg91_request("verifyOtp", {"reqId": req_id, "otp": otp})
        if str(response.get("type", "")).lower() != "success":
            return response
        record = cache.get(_cache_key(req_id))
        if not record:
            raise OTPServiceError("OTP request was not found or has expired.", 404)
        cache.delete(_cache_key(req_id))
        return _authentication_response(response, record["identifier"])
    key = _cache_key(req_id)
    record = cache.get(key)
    if not record:
        raise OTPServiceError("OTP request was not found or has expired.", 404)
    if secrets.compare_digest(record["otp"], otp):
        cache.delete(key)
        return _authentication_response({
            "type": "success",
            "message": "OTP verified successfully.",
            "reqId": req_id,
        }, record["identifier"])
    record["attempts"] += 1
    if record["attempts"] >= settings.OTP_MAX_VERIFY_ATTEMPTS:
        cache.delete(key)
        raise OTPServiceError("Maximum verification attempts exceeded.", 429)
    cache.set(key, record, settings.OTP_EXPIRY_SECONDS)
    raise OTPServiceError("Invalid OTP.", 400)


def _authentication_response(response, identifier):
    User = get_user_model()
    if "@" in identifier:
        user, _ = User.objects.get_or_create(email=identifier, defaults={"phone": None})
    else:
        user, _ = User.objects.get_or_create(phone=identifier)
    refresh = RefreshToken.for_user(user)
    return {
        "type": response.get("type", "success"),
        "message": "OTP verified successfully.",
        "user": AuthUserSerializer(user).data,
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
    }
