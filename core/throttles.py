from rest_framework.throttling import AnonRateThrottle


class OTPIdentifierThrottle(AnonRateThrottle):
    """Rate-limit OTP operations by both client IP and request identifier."""

    scope = None

    def get_cache_key(self, request, view):
        identifier = str(
            request.data.get("identifier") or request.data.get("req_id") or ""
        ).strip().lower()
        ident = self.get_ident(request)
        if identifier:
            ident = f"{ident}:{identifier}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class OTPSendThrottle(OTPIdentifierThrottle):
    scope = "otp_send"


class OTPResendThrottle(OTPIdentifierThrottle):
    scope = "otp_resend"


class OTPVerifyThrottle(OTPIdentifierThrottle):
    scope = "otp_verify"


class TokenRefreshThrottle(AnonRateThrottle):
    scope = "token_refresh"
