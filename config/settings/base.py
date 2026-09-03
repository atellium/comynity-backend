from pathlib import Path

import environ


BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

ENVIRONMENT = env.str("ENVIRONMENT")
SECRET_KEY = env.str("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
MSG_AUTH_KEY = env.str("MSG_AUTH_KEY", default="")
MSG_WIDGET_ID = env.str("MSG_WIDGET_ID", default="")
OTP_LENGTH = env.int("OTP_LENGTH", default=4)
OTP_EXPIRY_SECONDS = env.int("OTP_EXPIRY_SECONDS", default=300)
OTP_MAX_VERIFY_ATTEMPTS = env.int("OTP_MAX_VERIFY_ATTEMPTS", default=5)
MSG91_TIMEOUT_SECONDS = env.int("MSG91_TIMEOUT_SECONDS", default=10)

# GeoDjango native library overrides. These are usually auto-detected on Linux,
# while Windows installations commonly need explicit OSGeo4W/QGIS DLL paths.
GDAL_LIBRARY_PATH = env.str("GDAL_LIBRARY_PATH", default="").strip() or None
GEOS_LIBRARY_PATH = env.str("GEOS_LIBRARY_PATH", default="").strip() or None

INSTALLED_APPS = [
    # "unfold",
    
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.contrib.gis",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "storages",

    "core",
    "accounts",
    "locations",
    "categories",
    "businesses",
    "bookmarks",
    "catalogs",
    "offers",
]

AUTH_USER_MODEL = "accounts.User"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=False)
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "otp_send": env.str("OTP_SEND_RATE", default="5/hour"),
        "otp_resend": env.str("OTP_RESEND_RATE", default="5/hour"),
        "otp_verify": env.str("OTP_VERIFY_RATE", default="20/hour"),
        "token_refresh": env.str("TOKEN_REFRESH_RATE", default="30/hour"),
    },
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=30)
    ),
    "ROTATE_REFRESH_TOKENS": env.bool("JWT_ROTATE_REFRESH_TOKENS", default=True),
    "BLACKLIST_AFTER_ROTATION": env.bool(
        "JWT_BLACKLIST_AFTER_ROTATION", default=True
    ),
    "UPDATE_LAST_LOGIN": env.bool("JWT_UPDATE_LAST_LOGIN", default=False),
    "ALGORITHM": env.str("JWT_ALGORITHM", default="HS256"),
    "SIGNING_KEY": env.str("JWT_SIGNING_KEY", default="") or SECRET_KEY,
    "AUTH_HEADER_TYPES": tuple(env.list("JWT_AUTH_HEADER_TYPES", default=["Bearer"])),
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env.str("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
MAX_IMAGE_UPLOAD_BYTES = env.int("MAX_IMAGE_UPLOAD_BYTES", default=10 * 1024 * 1024)
MAX_IMAGE_PIXELS = env.int("MAX_IMAGE_PIXELS", default=40_000_000)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
    "loggers": {"django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

R2_ENABLED = env.bool("R2_ENABLED", default=False)
if R2_ENABLED:
    r2_public_development_url = env.str(
        "R2_PUBLIC_DEVELOPMENT_URL", default=""
    ).strip()
    r2_custom_domain = env.str("R2_CUSTOM_DOMAIN", default="").strip()
    r2_storage_options = {
        "access_key": env.str("R2_ACCESS_KEY_ID"),
        "secret_key": env.str("R2_SECRET_ACCESS_KEY"),
        "bucket_name": env.str("R2_BUCKET_NAME"),
        "endpoint_url": env.str("R2_ENDPOINT_URL"),
        "region_name": "auto",
        "signature_version": "s3v4",
        "default_acl": None,
        "file_overwrite": False,
        "location": env.str("R2_LOCATION", default="media").strip("/"),
        "querystring_auth": env.bool("R2_QUERYSTRING_AUTH", default=True),
        "querystring_expire": env.int("R2_QUERYSTRING_EXPIRE", default=3600),
    }
    r2_public_domain = r2_custom_domain or r2_public_development_url
    if r2_public_domain:
        r2_storage_options["custom_domain"] = r2_public_domain.removeprefix(
            "https://"
        ).removeprefix("http://").rstrip("/")

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": r2_storage_options,
    }
