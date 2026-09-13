from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def readiness(request):
    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        pass
    try:
        cache_key = "health:readiness"
        cache.set(cache_key, "ok", timeout=10)
        checks["cache"] = cache.get(cache_key) == "ok"
    except Exception:
        pass
    ready = all(checks.values())
    return Response(
        {"status": "ok" if ready else "unavailable", "checks": checks},
        status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
