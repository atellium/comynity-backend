from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
from django.utils import timezone

from doctors.models import Doctor, DoctorSchedule, DoctorSpecialty
from doctors.serializers import (
    BusinessDoctorListQuerySerializer,
    DoctorDetailSerializer,
    DoctorListItemSerializer,
    DoctorListQuerySerializer,
    DoctorSpecialtyListItemSerializer,
    DoctorSpecialtyListQuerySerializer,
    DoctorWriteSerializer,
    doctor_specialty_data,
)
from businesses.models import Business


class UnsupportedDoctorQueryParams(ValueError):
    def __init__(self, params):
        self.params = sorted(params)
        super().__init__(
            "Unsupported query parameter(s): "
            f"{', '.join(self.params)}."
        )


class DoctorSpecialtyNotFound(LookupError):
    pass


class DoctorNotFound(LookupError):
    pass


class BusinessNotFound(LookupError):
    pass


def build_pagination(*, count, page, page_size):
    total_pages = (count + page_size - 1) // page_size
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def list_doctors(*, query_params, request):
    unsupported_params = set(query_params) - set(DoctorListQuerySerializer().fields)
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = DoctorListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    specialty = find_doctor_specialty(params["specialty"])
    if specialty is None:
        raise DoctorSpecialtyNotFound("Doctor specialty was not found.")

    user_location = Point(float(params["lng"]), float(params["lat"]), srid=4326)
    doctors = (
        Doctor.objects.filter(
            is_active=True,
            business__is_active=True,
            business__location__isnull=False,
            specialties=specialty,
        )
        .filter(
            business__location__distance_lte=(
                user_location,
                D(km=params["radius_km"]),
            )
        )
        .annotate(distance=Distance("business__location", user_location))
        .select_related(
            "business",
            "business__city",
            "business__profile",
            "business__cover_image",
        )
        .prefetch_related(
            "specialties",
            "schedules",
            "business__categories",
            "business__business_hours",
        )
        .order_by("distance", "-is_featured", "name")
        .distinct()
    )

    if params.get("available_today"):
        doctors = doctors.filter(_available_today_schedule_filter())

    count = doctors.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = doctors[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "specialty": doctor_specialty_data(specialty),
        "results": DoctorListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def list_doctor_specialties(*, query_params, request):
    unsupported_params = set(query_params) - set(
        DoctorSpecialtyListQuerySerializer().fields
    )
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = DoctorSpecialtyListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    specialties = DoctorSpecialty.objects.filter(is_active=True)

    search = params.get("search")
    if search:
        specialties = specialties.filter(
            Q(name__icontains=search)
            | Q(label__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )

    body_part = params.get("body_part")
    if body_part:
        specialties = specialties.filter(body_part=body_part)

    if "is_featured" in params:
        specialties = specialties.filter(is_featured=params["is_featured"])

    specialties = specialties.order_by("sort_order", "name", "pk")
    count = specialties.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = specialties[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "results": DoctorSpecialtyListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def list_business_doctors(*, business_slug, query_params, request):
    unsupported_params = set(query_params) - set(
        BusinessDoctorListQuerySerializer().fields
    )
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = BusinessDoctorListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    business = Business.objects.filter(slug=business_slug, is_active=True).first()
    if business is None:
        raise BusinessNotFound("Business was not found.")

    doctors = (
        _doctor_detail_queryset()
        .filter(business=business, is_active=True)
        .order_by("-is_featured", "name")
        .distinct()
    )

    if params.get("available_today"):
        doctors = doctors.filter(_available_today_schedule_filter())

    count = doctors.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = doctors[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "business": {
            "id": business.id,
            "name": business.name,
            "slug": business.slug,
        },
        "results": DoctorListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def add_doctor_for_my_business(*, business_id, data, request):
    business = Business.objects.filter(pk=business_id, owner=request.user).first()
    if business is None:
        raise BusinessNotFound("Business was not found.")

    serializer = DoctorWriteSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    doctor = serializer.save(business=business)
    doctor = _doctor_detail_queryset().get(pk=doctor.pk)

    return DoctorDetailSerializer(doctor, context={"request": request}).data


def update_doctor_for_my_business(*, business_id, doctor_id, data, request, partial=True):
    doctor = (
        _doctor_detail_queryset()
        .filter(
            pk=doctor_id,
            business_id=business_id,
            business__owner=request.user,
        )
        .first()
    )
    if doctor is None:
        raise DoctorNotFound("Doctor was not found.")

    serializer = DoctorWriteSerializer(
        doctor,
        data=data,
        partial=partial,
    )
    serializer.is_valid(raise_exception=True)
    doctor = serializer.save()
    doctor = _doctor_detail_queryset().get(pk=doctor.pk)

    return DoctorDetailSerializer(doctor, context={"request": request}).data


def delete_doctor_for_my_business(*, business_id, doctor_id, request):
    doctor = Doctor.objects.filter(
        pk=doctor_id,
        business_id=business_id,
        business__owner=request.user,
    ).first()
    if doctor is None:
        raise DoctorNotFound("Doctor was not found.")

    doctor.delete()


def get_doctor_detail(*, slug, request):
    doctor = (
        _doctor_detail_queryset()
        .filter(
            slug=slug,
            is_active=True,
            business__is_active=True,
        )
        .first()
    )
    if doctor is None:
        raise DoctorNotFound("Doctor was not found.")

    return DoctorDetailSerializer(doctor, context={"request": request}).data


def _doctor_detail_queryset():
    return (
        Doctor.objects.select_related(
            "business",
            "business__city",
            "business__profile",
            "business__cover_image",
        )
        .prefetch_related(
            "specialties",
            "schedules",
            "business__categories",
            "business__business_hours",
        )
    )


def find_doctor_specialty(specialty_key):
    return DoctorSpecialty.objects.filter(
        slug=specialty_key,
        is_active=True,
    ).first()


def _available_today_schedule_filter():
    now = timezone.localtime()
    today = now.date()
    current_time = now.time()
    week_of_month = ((today.day - 1) // 7) + 1

    return (
        Q(schedules__is_active=True)
        & Q(schedules__end_time__gt=current_time)
        & (
            Q(
                schedules__schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
                schedules__weekday=today.weekday(),
            )
            | Q(
                schedules__schedule_type=DoctorSchedule.ScheduleType.MONTHLY_WEEKDAY,
                schedules__weekday=today.weekday(),
                schedules__week_of_month=week_of_month,
            )
            | Q(
                schedules__schedule_type=DoctorSchedule.ScheduleType.MONTHLY_DATE,
                schedules__day_of_month=today.day,
            )
        )
    )
