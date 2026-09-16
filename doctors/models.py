import uuid
from django.core.validators import FileExtensionValidator
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models

from core.image_service import compress_image
from core.models import AutoSlugModel, TimestampedModel
from core.utils import generate_unique_slug
from uploads.models import Upload


class DoctorSpecialty(AutoSlugModel, TimestampedModel):
    class BodyPartChoices(models.TextChoices):
        HEART = "heart", "Heart"
        SKIN = "skin", "Skin"
        EYE = "eye", "Eye"
        EAR_NOSE_THROAT = "ent", "Ear, Nose & Throat"
        BRAIN_NERVOUS_SYSTEM = "brain_nervous_system", "Brain & Nervous System"
        BONES_JOINTS = "bones_joints", "Bones & Joints"
        LUNGS = "lungs", "Lungs"
        KIDNEY = "kidney", "Kidney"
        STOMACH_DIGESTIVE = "digestive_system", "Stomach & Digestive System"
        LIVER = "liver", "Liver"
        TEETH_MOUTH = "teeth_mouth", "Teeth & Mouth"
        WOMENS_HEALTH = "womens_health", "Women's Health"
        CHILD_HEALTH = "child_health", "Child Health"
        MENTAL_HEALTH = "mental_health", "Mental Health"
        HORMONES_METABOLISM = "hormones_metabolism", "Hormones & Metabolism"
        URINARY_SYSTEM = "urinary_system", "Urinary System"
        REPRODUCTIVE_SYSTEM = "reproductive_system", "Reproductive System"
        BLOOD = "blood", "Blood"
        CANCER = "cancer", "Cancer"
        GENERAL = "general", "General Health"
        OTHER = "other", "Other"
        
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Singular name, e.g. Cardiologist"
    )
    label = models.CharField(
        max_length=120,
        help_text="Plural/display label, e.g. Cardiologists"
    )
    slug = models.SlugField(
        max_length=120,
        unique=True
    )

    aliases = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated search aliases, e.g. heart doctor, heart specialist"
    )
    body_part = models.CharField(
        max_length=50,
        choices=BodyPartChoices.choices,
        blank=True,
        help_text="Primary body part or health system associated with this specialty"
    )

    image = models.ImageField(
        upload_to="categories/doctor_specialties/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg","jpeg","png","webp","avif",])
        ],
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )
    is_featured = models.BooleanField(
        default=False
    )

    class Meta:
        db_table = "doctorspecialties"
        ordering = ["sort_order", "name"]
        verbose_name = "Doctor Specialty"
        verbose_name_plural = "Doctor Specialties"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.image and not self.image._committed:
            self.image = compress_image(
                self.image,
                quality=100,
                max_width=300,
                convert_to_webp=False,
            )
        super().save(*args, **kwargs)


class Doctor(TimestampedModel):
    class GenderChoices(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="doctors",
    )

    name = models.CharField(max_length=150)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        db_index=True,
    )
    gender = models.CharField(
        max_length=20,
        choices=GenderChoices.choices,
        default=GenderChoices.PREFER_NOT_TO_SAY,
    )
    specialties = models.ManyToManyField(
        "DoctorSpecialty",
        related_name="doctors",
        blank=True
    )
    qualification = models.CharField(
        max_length=300,
        blank=True
    )
    profile_image = models.ForeignKey(
        "uploads.Upload",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )
    registration_council = models.CharField(
        max_length=150,
        blank=True,
    )
    registration_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    bio = models.TextField(
        blank=True,
    )
    languages = models.JSONField(
        default=list,
        blank=True,
        help_text="Example: ['English', 'Hindi', 'Bengali']",
    )
    treatments = models.JSONField(
        default=list,
        blank=True,
        help_text="Treatments/services commonly provided by the doctor.",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )

    class Meta:
        db_table = "doctors"
        ordering = ["-is_featured", "name"]
        indexes = [
            models.Index(fields=["is_active", "business"]),
            models.Index(fields=["is_featured", "is_active"]),
        ]
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        slug_source = f"{self.name} at {self._business_slug()}".strip()
        self.slug = generate_unique_slug(
            self,
            slug_source,
            fallback="doctor",
            using=kwargs.get("using"),
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"slug"}

        super().save(*args, **kwargs)

    def _business_slug(self):
        if self.business_id is None:
            return ""

        if hasattr(self, "business") and self.business.slug:
            return self.business.slug

        return (
            type(self)
            ._meta
            .get_field("business")
            .remote_field
            .model
            .objects
            .filter(pk=self.business_id)
            .values_list("slug", flat=True)
            .first()
            or ""
        )


class DoctorSchedule(TimestampedModel):

    class ScheduleType(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY_WEEKDAY = "monthly_weekday", "Monthly Weekday"
        MONTHLY_DATE = "monthly_date", "Monthly Date"

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    class WeekOfMonth(models.IntegerChoices):
        FIRST = 1, "1st"
        SECOND = 2, "2nd"
        THIRD = 3, "3rd"
        FOURTH = 4, "4th"
        FIFTH = 5, "5th"

    class ConsultationType(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        BY_APPOINTMENT = "by_appointment", "By Appointment"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    doctor = models.ForeignKey(
        "Doctor",
        on_delete=models.CASCADE,
        related_name="schedules",
    )

    schedule_type = models.CharField(
        max_length=30,
        choices=ScheduleType.choices,
        db_index=True,
    )

    # Type 1:
    # Every Monday / Every Saturday
    #
    # Type 2:
    # 2nd Saturday / 4th Saturday
    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        null=True,
        blank=True,
    )

    # Only for MONTHLY_WEEKDAY
    # Example: 2nd Saturday
    week_of_month = models.PositiveSmallIntegerField(
        choices=WeekOfMonth.choices,
        null=True,
        blank=True,
    )

    # Only for MONTHLY_DATE
    # Example: 10th / 20th / 30th
    day_of_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(31),
        ],
    )

    # Time
    start_time = models.TimeField()
    end_time = models.TimeField()

    consultation_type = models.CharField(
        max_length=30,
        choices=ConsultationType.choices,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    class Meta:
        db_table = "doctor_schedules"
        verbose_name = "Doctor Schedule"
        verbose_name_plural = "Doctor Schedules"
        ordering = [
            "doctor",
            "schedule_type",
            "weekday",
            "week_of_month",
            "day_of_month",
            "start_time",
        ]

        indexes = [
            models.Index(
                fields=[
                    "doctor",
                    "schedule_type",
                    "is_active",
                ]
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="doctor_schedule_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()

        if self.schedule_type == self.ScheduleType.WEEKLY:
            if self.weekday is None:
                raise ValidationError({
                    "weekday": "Weekday is required for weekly schedules."
                })

            if self.week_of_month is not None:
                raise ValidationError({
                    "week_of_month": "Week of month is not allowed."
                })

            if self.day_of_month is not None:
                raise ValidationError({
                    "day_of_month": "Day of month is not allowed."
                })

        elif self.schedule_type == self.ScheduleType.MONTHLY_WEEKDAY:
            if self.weekday is None:
                raise ValidationError({
                    "weekday": "Weekday is required."
                })

            if self.week_of_month is None:
                raise ValidationError({
                    "week_of_month": "Week of month is required."
                })

            if self.day_of_month is not None:
                raise ValidationError({
                    "day_of_month": "Day of month is not allowed."
                })

        elif self.schedule_type == self.ScheduleType.MONTHLY_DATE:
            if self.day_of_month is None:
                raise ValidationError({
                    "day_of_month": "Day of month is required."
                })

            if self.weekday is not None:
                raise ValidationError({
                    "weekday": "Weekday is not allowed."
                })

            if self.week_of_month is not None:
                raise ValidationError({
                    "week_of_month": "Week of month is not allowed."
                })

        if self.start_time >= self.end_time:
            raise ValidationError({
                "end_time": "End time must be after start time."
            })
    
    def __str__(self):
        return (
            f"{self.doctor} - {self.schedule_label} "
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        )

    @property
    def schedule_label(self):
        if self.schedule_type == self.ScheduleType.WEEKLY:
            return f"Every {self.get_weekday_display()}"

        if self.schedule_type == self.ScheduleType.MONTHLY_WEEKDAY:
            return (
                f"{self.get_week_of_month_display()} "
                f"{self.get_weekday_display()}"
            )

        if self.schedule_type == self.ScheduleType.MONTHLY_DATE:
            return f"{_ordinal(self.day_of_month)} Date of every month"

        return self.get_schedule_type_display()


def _ordinal(value):
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"
