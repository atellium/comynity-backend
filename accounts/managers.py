from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom manager for the Comynity user model.
    """

    use_in_migrations = True

    def normalize_phone(self, phone: str) -> str:
        """
        Remove spaces and common formatting characters.
        The phone should ultimately be stored in E.164 format.
        """
        if not phone:
            raise ValueError("A phone number is required.")

        return (
            str(phone)
            .strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

    def create_user(
        self,
        phone,
        password=None,
        **extra_fields,
    ):
        if not phone:
            raise ValueError("The phone number must be provided.")

        phone = self.normalize_phone(phone)

        email = extra_fields.get("email")
        if email:
            extra_fields["email"] = self.normalize_email(email.strip()).lower()
        else:
            extra_fields["email"] = None

        user = self.model(
            phone=phone,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            # Useful when authentication is OTP-only.
            user.set_unusable_password()

        user.full_clean()
        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        phone,
        password,
        **extra_fields,
    ):
        if not password:
            raise ValueError("A superuser must have a password.")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(
            phone=phone,
            password=password,
            **extra_fields,
        )
