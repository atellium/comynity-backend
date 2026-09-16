from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from doctors.models import Doctor, DoctorSchedule, DoctorSpecialty


def _format_indian_phone(value):
    if not value:
        return ""
    value = str(value).strip()
    if value.startswith("+"):
        return value
    if len(value) == 10:
        return f"+91{value}"
    return value


class DoctorListQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    specialty = serializers.CharField(
        max_length=120,
        trim_whitespace=True,
        allow_blank=False,
    )
    radius_km = serializers.FloatField(
        required=False,
        min_value=0.1,
        max_value=100,
        default=5,
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )
    available_today = serializers.BooleanField(required=False)


class DoctorSpecialtyListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        max_length=120,
        trim_whitespace=True,
        allow_blank=False,
    )
    body_part = serializers.ChoiceField(
        required=False,
        choices=DoctorSpecialty.BodyPartChoices.choices,
    )
    is_featured = serializers.BooleanField(required=False)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class BusinessDoctorListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )
    available_today = serializers.BooleanField(required=False)


class DoctorScheduleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorSchedule
        fields = (
            "schedule_type",
            "weekday",
            "week_of_month",
            "day_of_month",
            "start_time",
            "end_time",
            "consultation_type",
            "is_active",
        )
        extra_kwargs = {
            "weekday": {"required": False, "allow_null": True},
            "week_of_month": {"required": False, "allow_null": True},
            "day_of_month": {"required": False, "allow_null": True},
            "is_active": {"required": False},
        }


class DoctorWriteSerializer(serializers.ModelSerializer):
    specialty_ids = serializers.PrimaryKeyRelatedField(
        source="specialties",
        many=True,
        queryset=DoctorSpecialty.objects.filter(is_active=True),
        required=True,
        allow_empty=False,
    )
    schedules = DoctorScheduleWriteSerializer(many=True, required=False)

    class Meta:
        model = Doctor
        fields = (
            "name",
            "specialty_ids",
            "qualification",
            "profile_image",
            "registration_number",
            "registration_council",
            "registration_year",
            "consultation_fee",
            "gender",
            "bio",
            "languages",
            "treatments",
            "is_active",
            "schedules",
        )
        extra_kwargs = {
            "name": {"allow_blank": False},
            "qualification": {"required": True, "allow_blank": False},
            "is_active": {"required": False},
        }

    def create(self, validated_data):
        specialties = validated_data.pop("specialties", None)
        schedules = validated_data.pop("schedules", None)

        with transaction.atomic():
            doctor = Doctor.objects.create(**validated_data)
            if specialties is not None:
                doctor.specialties.set(specialties)
            if schedules is not None:
                self._replace_schedules(doctor, schedules)

        return doctor

    def update(self, instance, validated_data):
        specialties = validated_data.pop("specialties", None)
        schedules = validated_data.pop("schedules", None)

        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(instance, field, value)

            instance.save()

            if specialties is not None:
                instance.specialties.set(specialties)
            if schedules is not None:
                self._replace_schedules(instance, schedules)

        return instance

    def _replace_schedules(self, doctor, schedules):
        doctor.schedules.all().delete()
        for schedule_data in schedules:
            schedule = DoctorSchedule(doctor=doctor, **schedule_data)
            try:
                schedule.full_clean()
            except DjangoValidationError as error:
                raise serializers.ValidationError(
                    {"schedules": error.message_dict}
                ) from error
            schedule.save()


class DoctorSpecialtyListItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = DoctorSpecialty
        fields = (
            "id",
            "name",
            "label",
            "slug",
            "aliases",
            "body_part",
            "image",
            "sort_order",
            "is_active",
            "is_featured",
        )

    def get_image(self, obj):
        if not obj.image:
            return ""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class DoctorListItemSerializer(serializers.ModelSerializer):
    specialties = serializers.SerializerMethodField()
    business = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = (
            "id",
            "name",
            "slug",
            "qualification",
            "registration_number",
            "registration_council",
            "registration_year",
            "consultation_fee",
            "gender",
            "bio",
            "languages",
            "treatments",
            "is_active",
            "is_featured",
            "specialties",
            "business",
            "schedule",
        )

    def get_specialties(self, obj):
        return [
            doctor_specialty_data(specialty)
            for specialty in obj.specialties.all()
        ]

    def get_business(self, obj):
        business = obj.business
        distance = getattr(obj, "distance", None)
        return {
            "id": business.id,
            "name": business.name,
            "slug": business.slug,
            "distance_km": round(distance.km, 2) if distance is not None else None,
            "is_verified": business.is_verified,
            "cover_image": self._business_cover_image_url(business),
            "contact": {
                "phone": _format_indian_phone(business.phone),
                "alternate_numbers": _business_alternate_numbers(business),
                "whatsapp": _format_indian_phone(business.whatsapp),
                "email": business.email,
                "website": business.website,
            },
            "address": {
                "address": business.address,
                "landmark": business.landmark,
                "locality": business.locality,
                "postal_code": business.postal_code,
                "latitude": business.location.y if business.location else None,
                "longitude": business.location.x if business.location else None,
            },
            "city": _business_city_data(business),
        }

    def _business_cover_image_url(self, business):
        if not business.cover_image_id:
            return None

        url = default_storage.url(business.cover_image.object_key)
        request = self.context.get("request")
        if request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

    def get_schedule(self, obj):
        return build_doctor_schedule_data(
            obj.schedules.all(),
            now=self.context.get("now"),
        )


class DoctorDetailSerializer(DoctorListItemSerializer):
    class Meta(DoctorListItemSerializer.Meta):
        fields = DoctorListItemSerializer.Meta.fields


def build_doctor_schedule_data(schedules, *, now=None):
    schedules = sorted(
        (schedule for schedule in schedules if schedule.is_active),
        key=lambda schedule: (
            schedule.schedule_type,
            schedule.weekday if schedule.weekday is not None else 99,
            schedule.week_of_month if schedule.week_of_month is not None else 99,
            schedule.day_of_month if schedule.day_of_month is not None else 99,
            schedule.start_time,
            str(schedule.id or ""),
        ),
    )
    now = now or timezone.localtime()
    current_slot = _current_schedule_slot(schedules, now)
    display_slot = current_slot or _next_schedule_slot(schedules, now)

    return {
        "is_available": current_slot is not None,
        "next_available": _next_available_text(display_slot, now),
        "is_today": _slot_is_today(display_slot, now),
        "full_schedule": [_schedule_data(schedule) for schedule in schedules],
    }


def _current_schedule_slot(schedules, now):
    for schedule in schedules:
        if (
            _schedule_matches_date(schedule, now.date())
            and schedule.start_time <= now.time() < schedule.end_time
        ):
            return (schedule, now.date())
    return None


def _next_schedule_slot(schedules, now):
    for day_offset in range(366):
        candidate_date = now.date() + timedelta(days=day_offset)
        matching_schedules = sorted(
            (
                schedule
                for schedule in schedules
                if _schedule_matches_date(schedule, candidate_date)
            ),
            key=lambda schedule: schedule.start_time,
        )
        for schedule in matching_schedules:
            if day_offset > 0 or schedule.start_time > now.time():
                return (schedule, candidate_date)
    return None


def _schedule_matches_date(schedule, date_value):
    if schedule.schedule_type == DoctorSchedule.ScheduleType.WEEKLY:
        return schedule.weekday == date_value.weekday()

    if schedule.schedule_type == DoctorSchedule.ScheduleType.MONTHLY_WEEKDAY:
        return (
            schedule.weekday == date_value.weekday()
            and schedule.week_of_month == ((date_value.day - 1) // 7) + 1
        )

    if schedule.schedule_type == DoctorSchedule.ScheduleType.MONTHLY_DATE:
        return schedule.day_of_month == date_value.day

    return False


def _next_available_text(slot, now):
    if slot is None:
        return ""

    schedule, date_value = slot
    time_range = (
        f"{_format_display_time(schedule.start_time)} - "
        f"{_format_display_time(schedule.end_time)}"
    )
    consultation_suffix = ""
    if schedule.consultation_type == DoctorSchedule.ConsultationType.BY_APPOINTMENT:
        consultation_suffix = f" ({schedule.get_consultation_type_display()})"

    if date_value == now.date():
        return f"Available today, {time_range}{consultation_suffix}"

    if date_value == now.date() + timedelta(days=1):
        return f"Available tomorrow, {time_range}{consultation_suffix}"

    return f"Available {date_value.strftime('%A')}, {time_range}{consultation_suffix}"


def _slot_is_today(slot, now):
    return slot is not None and slot[1] == now.date()


def _schedule_data(schedule):
    return {
        "schedule_type": schedule.schedule_type,
        "schedule_label": schedule.schedule_label,
        "weekday": schedule.weekday,
        "week_of_month": schedule.week_of_month,
        "day_of_month": schedule.day_of_month,
        "start_time": _format_time(schedule.start_time),
        "end_time": _format_time(schedule.end_time),
        "consultation_type": schedule.consultation_type,
    }


def _format_time(value):
    return value.strftime("%H:%M:%S")


def _format_display_time(value):
    return value.strftime("%I:%M %p").lstrip("0").replace(":00", "")


def doctor_specialty_data(specialty):
    return {
        "id": specialty.id,
        "name": specialty.name,
        "label": specialty.label,
        "slug": specialty.slug,
        "aliases": specialty.aliases,
        "body_part": specialty.body_part,
    }


def _business_city_data(business):
    if business.city is None:
        return None

    return {
        "id": business.city_id,
        "name": business.city.name,
        "slug": business.city.slug,
    }


def _business_alternate_numbers(business):
    try:
        return business.profile.alternate_numbers
    except AttributeError:
        return []
