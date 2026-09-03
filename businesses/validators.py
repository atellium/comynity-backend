from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator

phone_validator = RegexValidator(r"^\+[1-9]\d{7,14}$", "Use international format, such as +919876543210.")


def validate_alternate_numbers(value):
    if not isinstance(value, list):
        raise ValidationError("Alternate numbers must be a list.")
    if len(value) > 10:
        raise ValidationError("A maximum of 10 alternate numbers is allowed.")
    if any(not isinstance(number, str) for number in value):
        raise ValidationError("Every alternate number must be a string.")
    for number in value:
        phone_validator(number)
    if len(value) != len(set(value)):
        raise ValidationError("Alternate numbers must be unique.")


def validate_social_urls(value):
    if not isinstance(value, dict):
        raise ValidationError("Social URLs must be an object of platform and URL pairs.")
    if len(value) > 20:
        raise ValidationError("A maximum of 20 social URLs is allowed.")
    url_validator = URLValidator(schemes=["http", "https"])
    for platform, url in value.items():
        if not isinstance(platform, str) or not platform.strip() or len(platform) > 50:
            raise ValidationError("Each social platform must be a non-empty string of at most 50 characters.")
        if not isinstance(url, str):
            raise ValidationError(f"The URL for {platform} must be a string.")
        url_validator(url)


def validate_established_year(value):
    if value < 1800 or value > date.today().year:
        raise ValidationError(f"Established year must be between 1800 and {date.today().year}.")


def validate_business_days(value):
    """Validate a non-empty set of weekday numbers (Monday=0, Sunday=6)."""
    if not isinstance(value, list) or isinstance(value, (str, bytes)):
        raise ValidationError("Days must be a list of ISO weekday numbers.")
    if not value:
        raise ValidationError("Select at least one day.")
    if any(type(day) is not int or day < 0 or day > 6 for day in value):
        raise ValidationError("Each day must be an integer from 0 (Monday) to 6 (Sunday).")
    if len(value) != len(set(value)):
        raise ValidationError("Days cannot contain duplicates.")
