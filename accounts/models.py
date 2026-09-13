import uuid
import secrets
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from .managers import UserManager

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter the phone number in international format, such as +919876543210.",
)

PROFILE_COLORS = (
    "#1A73E8",  # blue
    "#188038",  # green
    "#D93025",  # red
    "#A142F4",  # purple
    "#F29900",  # orange
    "#007B83",  # teal
    "#C5221F",  # dark red
    "#3F51B5",  # indigo
)


def generate_profile_color():
    """Return an accessible avatar background color for a new user."""
    return secrets.choice(PROFILE_COLORS)

class User(AbstractUser):
    class GenderChoice(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"
        NOT_MENTIONED = "N", "Not Mentioned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True, validators=[phone_validator])

    full_name = models.CharField(max_length=150, null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GenderChoice.choices, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    profile_color = models.CharField(
        max_length=7,
        default=generate_profile_color,
        editable=False,
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-F]{6}$",
                message="Profile color must be an uppercase hexadecimal color.",
            )
        ],
    )

    username = None
    first_name = None
    last_name = None

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower() if self.email and self.email.strip() else None

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower() if self.email and self.email.strip() else None
        if self._state.adding and not self.password:
            self.set_unusable_password()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
