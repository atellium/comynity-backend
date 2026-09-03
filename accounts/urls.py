from django.urls import path

from . import views


app_name = "accounts"

urlpatterns = [
    path("otp/send/", views.send, name="otp-send"),
    path("otp/resend/", views.resend, name="otp-resend"),
    path("otp/verify/", views.verify, name="otp-verify"),
    path("token/refresh/", views.refresh_token, name="token-refresh"),
    path("token/logout/", views.logout, name="token-logout"),
    path("users/me/", views.CurrentUserView.as_view(), name="user-me"),
]
