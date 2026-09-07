import json
import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, router, transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models import Prefetch
from django.db.models import FloatField, ExpressionWrapper
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.paginator import Paginator
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from categories.models import BusinessCategory
from locations.models import City
from core.image_service import compress_image
from core.utils import generate_unique_slug

BUSINESS_CLOSING_SOON_MINUTES = 60

def normalize_business(business):
    business.name = (business.name or "").strip()
    business.address = (business.address or "").strip()
    business.email = (business.email or "").strip().lower()
    business.website = (business.website or "").strip()
    business.postal_code = (business.postal_code or "").strip()
    business.phone = (business.phone or "").strip()
    business.whatsapp = (business.whatsapp or "").strip()
    errors = {field: "This field cannot be blank." for field in ("name", "address") if not getattr(business, field)}
    if errors:
        raise ValidationError(errors)


def normalize_business_profile(profile):
    profile.description = (profile.description or "").strip()
    profile.seo_title = (profile.seo_title or "").strip()
    profile.seo_description = (profile.seo_description or "").strip()
    profile.seo_keywords = (profile.seo_keywords or "").strip()


def prepare_business_for_save(business):
    normalize_business(business)
    business.location = (
        Point(float(business.longitude), float(business.latitude), srid=4326)
        if business.latitude is not None and business.longitude is not None
        else None
    )
    if not business.thumbnail or getattr(business.thumbnail, "_committed", True):
        return
    business.thumbnail = compress_image(business.thumbnail, quality=80)


def save_business(business, save_callback, args, kwargs, max_slug_attempts=5):
    prepare_business_for_save(business)
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and {"latitude", "longitude"} & set(update_fields):
        kwargs["update_fields"] = set(update_fields) | {"location"}
    generated_slug = not business.slug
    using = kwargs.get("using") or router.db_for_write(type(business), instance=business)
    if generated_slug:
        business.slug = generate_unique_slug(business, business.name, using=using)
        if update_fields is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"slug"}
    for attempt in range(max_slug_attempts):
        attempted_slug = business.slug
        try:
            with transaction.atomic(using=using):
                return save_callback(*args, **kwargs)
        except IntegrityError:
            collision = type(business).objects.using(using).filter(slug=attempted_slug).exclude(pk=business.pk).exists()
            if not generated_slug or not collision or attempt == max_slug_attempts - 1:
                raise
            business.slug = generate_unique_slug(business, business.name, using=using)


class BusinessSeedError(ValueError):
    pass


def load_business_seed(path):
    try:
        records = json.loads(
            Path(path).read_text(encoding="utf-8-sig"),
            parse_float=Decimal,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise BusinessSeedError(f"Could not read business seed file: {exc}") from exc
    if not isinstance(records, list):
        raise BusinessSeedError("Business seed file must contain a JSON list.")
    return records


@transaction.atomic
def seed_businesses(records):
    from businesses.models import Business, BusinessCategoryAssignment, BusinessProfile
    if not records:
        return 0, 0
    try:
        category_ids = {category_id for record in records for category_id in record.get("categories", [])}
        city_ids = {record.get("city") for record in records if record.get("city") is not None}
        owner_ids = {UUID(str(record["owner"])) for record in records if record.get("owner")}
    except (AttributeError, TypeError, ValueError) as exc:
        raise BusinessSeedError(f"Invalid seed references: {exc}") from exc
    categories = BusinessCategory.objects.in_bulk(category_ids)
    cities = City.objects.in_bulk(city_ids)
    owners = get_user_model().objects.in_bulk(owner_ids)
    missing_categories, missing_cities, missing_owners = category_ids - categories.keys(), city_ids - cities.keys(), owner_ids - owners.keys()
    if missing_categories or missing_cities or missing_owners:
        raise BusinessSeedError(f"Missing references: categories={sorted(missing_categories)}, cities={sorted(missing_cities)}, owners={sorted(map(str, missing_owners))}")
    writable = {"name", "slug", "handle", "established_year", "offerings", "address", "landmark", "locality", "postal_code", "latitude", "longitude", "phone", "whatsapp", "email", "website", "status", "is_active", "is_verified", "display_full_address", "display_business_hours"}
    profile_fields = {"description", "alternate_numbers", "social_urls", "seo_title", "seo_description", "seo_keywords"}
    profile_aliases = {"alt_numbers": "alternate_numbers"}
    accepted = writable | profile_fields | set(profile_aliases) | {"id", "owner", "categories", "city", "thumbnail", "published_at"}
    created_count = updated_count = 0
    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise BusinessSeedError(f"Record {position} must be a JSON object.")
        try:
            unknown_fields = set(record) - accepted
            if unknown_fields:
                raise BusinessSeedError(f"Unknown fields: {sorted(unknown_fields)}")
            business_id = UUID(str(record["id"]))
            business = Business.objects.filter(pk=business_id).first()
            created = business is None
            business = business or Business(id=business_id)
            for field in writable:
                if field in record:
                    setattr(business, field, record[field])
            business.city = cities[record["city"]]
            business.owner = owners.get(UUID(str(record["owner"]))) if record.get("owner") else None
            business.published_at = parse_datetime(record["published_at"]) if record.get("published_at") else None
            if record.get("published_at") and business.published_at is None:
                raise BusinessSeedError("published_at must be an ISO-8601 datetime.")
            business.full_clean()
            business.save()
            business.category_assignments.all().delete()
            BusinessCategoryAssignment.objects.bulk_create(
                BusinessCategoryAssignment(
                    business=business,
                    category=categories[category_id],
                    sort_order=sort_order,
                )
                for sort_order, category_id in enumerate(record.get("categories", []))
            )
            profile_defaults = {
                target: record[source]
                for source, target in ({field: field for field in profile_fields} | profile_aliases).items()
                if source in record
            }
            profile, _ = BusinessProfile.objects.get_or_create(business=business)
            for field, value in profile_defaults.items():
                setattr(profile, field, value)
            profile.full_clean()
            profile.save()
        except (IntegrityError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise BusinessSeedError(f"Invalid business at record {position}: {exc}") from exc
        created_count += created
        updated_count += not created
    return created_count, updated_count


BUSINESS_HOUR_PATTERNS = (
    (((0, 1, 2, 3, 4), time(9), time(18)), ((5,), time(9), time(14))),
    (((0, 1, 2, 3, 4, 5), time(10), time(20)),),
    (((0, 1, 2, 3, 4, 5, 6), time(9), time(21)),),
    (((0, 1, 2, 3, 4, 5, 6), time(11), time(23)),),
    (((0, 1, 2, 3, 4, 5), time(8), time(13)), ((0, 1, 2, 3, 4, 5), time(16), time(21))),
    (((0, 1, 2, 3, 4), time(8, 30), time(17, 30)),),
)


@transaction.atomic
def seed_random_business_hours(*, seed=20260815, replace=False, business_ids=None, batch_size=500):
    """Create realistic, deterministic schedules for businesses without hours."""
    from businesses.models import Business, BusinessHour

    businesses = Business.objects.order_by("id")
    if business_ids:
        businesses = businesses.filter(pk__in=business_ids)
    if not replace:
        businesses = businesses.filter(business_hours__isnull=True)

    business_ids_to_seed = list(businesses.values_list("id", flat=True))
    if replace and business_ids_to_seed:
        BusinessHour.objects.filter(business_id__in=business_ids_to_seed).delete()

    generator = random.Random(seed)
    hours = [
        BusinessHour(business_id=business_id, days=list(days), opens_at=opens_at, closes_at=closes_at)
        for business_id in business_ids_to_seed
        for days, opens_at, closes_at in generator.choice(BUSINESS_HOUR_PATTERNS)
    ]
    BusinessHour.objects.bulk_create(hours, batch_size=batch_size)
    return len(business_ids_to_seed), len(hours)


def _format_business_time(value):
    formatted = value.strftime("%I:%M %p") if value.minute else value.strftime("%I %p")
    return formatted.lstrip("0")


def get_business_hours_status(hours, *, holidays=(), now=None, closing_soon_minutes=BUSINESS_CLOSING_SOON_MINUTES):
    """Return the current weekly operating state for a prefetched schedule."""
    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    now = timezone.localtime(now)
    hours = list(hours)
    holidays_by_date = {
        holiday_date: holiday
        for holiday in holidays
        for day_offset in range((holiday.end_date - holiday.start_date).days + 1)
        for holiday_date in (holiday.start_date + timedelta(days=day_offset),)
    }
    current_holiday = holidays_by_date.get(now.date())
    if current_holiday is not None:
        remark = "Closed for holiday"
        if current_holiday.reason:
            remark = f"{remark}: {current_holiday.reason}"
        return {"status": "closed", "next_closing_time": None, "remark": remark}
    if not hours:
        return {"status": "closed", "next_closing_time": None, "remark": "Hours unavailable"}

    current_time = now.time().replace(tzinfo=None)
    effective_current_hours = [hour for hour in hours if now.weekday() in hour.days]
    current_slots = sorted(
        (hour for hour in effective_current_hours if hour.opens_at <= current_time < hour.closes_at),
        key=lambda hour: hour.closes_at,
    )
    if current_slots:
        current = current_slots[0]
        closing_at = timezone.make_aware(datetime.combine(now.date(), current.closes_at), now.tzinfo)
        remaining = closing_at - now
        status = "closing_soon" if remaining < timedelta(minutes=closing_soon_minutes) else "open"
        return {
            "status": status,
            "next_closing_time": closing_at.isoformat() if status == "closing_soon" else None,
            "remark": f"Open until {_format_business_time(current.closes_at)}",
        }

    next_opening = None
    for day_offset in range(8):
        candidate_date = now.date() + timedelta(days=day_offset)
        if candidate_date in holidays_by_date:
            continue
        candidate_hours = [
            hour for hour in hours if candidate_date.weekday() in hour.days
        ]
        for hour in candidate_hours:
            candidate = timezone.make_aware(datetime.combine(candidate_date, hour.opens_at), now.tzinfo)
            if candidate <= now:
                continue
            if next_opening is None or candidate < next_opening:
                next_opening = candidate

    if next_opening is None:
        return {"status": "closed", "next_closing_time": None, "remark": "Closed"}
    day_offset = (next_opening.date() - now.date()).days
    if day_offset == 0:
        day_label = "today"
    elif day_offset == 1:
        day_label = "tomorrow"
    else:
        day_label = next_opening.strftime("%A")
    return {
        "status": "closed",
        "next_closing_time": None,
        "remark": f"Opens {day_label} at {_format_business_time(next_opening.time())}",
    }


def business_response_queryset(
    *, include_detail_data=False, include_all_offers=False, now=None
):
    from businesses.models import Business, BusinessGalleryImage
    category_queryset = BusinessCategory.objects.only(
        "id", "slug", "display_name", "name"
    ).order_by("business_assignments__sort_order", "business_assignments__id")
    response_fields = ("id", "owner_id", "name", "handle", "slug", "established_year", "offerings", "thumbnail", "address", "landmark", "locality", "city_id", "postal_code", "location", "phone", "whatsapp", "email", "website", "status", "is_active", "is_verified", "display_full_address", "display_business_hours", "published_at", "created_at", "updated_at")
    from businesses.models import BusinessHour
    hours_queryset = BusinessHour.objects.only("business_id", "days", "opens_at", "closes_at").order_by("opens_at")
    prefetches = [
        Prefetch("categories", queryset=category_queryset),
        Prefetch("business_hours", queryset=hours_queryset, to_attr="_prefetched_business_hours"),
    ]
    if include_detail_data:
        from catalogs.models import Catalog, CatalogImage
        from offers.models import Offer

        gallery_queryset = BusinessGalleryImage.objects.only(
            "business_id", "image", "created_at", "updated_at"
        ).order_by("created_at", "id")
        prefetches.append(
            Prefetch("gallery_images", queryset=gallery_queryset, to_attr="_prefetched_gallery_images")
        )
        offer_queryset = Offer.objects.all()
        if not include_all_offers:
            offer_now = now or timezone.now()
            offer_queryset = offer_queryset.filter(is_active=True).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=offer_now),
                Q(expires_at__isnull=True) | Q(expires_at__gte=offer_now),
            )
        offer_queryset = offer_queryset.only(
            "id",
            "business_id",
            "title",
            "description",
            "image",
            "starts_at",
            "expires_at",
            "is_active",
            "sort_order",
            "terms",
            "created_at",
            "updated_at",
        ).order_by("sort_order", "-created_at", "id")
        prefetches.append(
            Prefetch(
                "offers",
                queryset=offer_queryset,
                to_attr="_prefetched_offers",
            )
        )
        primary_image_queryset = CatalogImage.objects.filter(
            is_active=True,
            is_primary=True,
        ).only("catalog_id", "image")
        product_queryset = (
            Catalog.objects.filter(
                type=Catalog.TypeChoices.PRODUCT,
                is_active=True,
            )
            .only(
                "id",
                "business_id",
                "public_id",
                "name",
                "slug",
                "price_type",
                "price",
                "max_price",
                "original_price",
                "variants",
                "specifications",
                "is_featured",
                "sort_order",
                "created_at",
            )
            .order_by("-is_featured", "sort_order", "created_at")
            .prefetch_related(
                Prefetch(
                    "images",
                    queryset=primary_image_queryset,
                    to_attr="_prefetched_primary_images",
                )
            )[:10]
        )
        prefetches.append(
            Prefetch(
                "catalog_items",
                queryset=product_queryset,
                to_attr="_prefetched_catalog_products",
            )
        )
    profile_fields = (
        "profile__description",
        "profile__alternate_numbers",
        "profile__social_urls",
        "profile__seo_title",
        "profile__seo_description",
        "profile__seo_keywords",
    )
    queryset = Business.objects.only(
        *response_fields,
        *profile_fields,
        "city__name",
        "city__state__name",
    ).select_related("city", "city__state", "profile")
    return queryset.prefetch_related(*prefetches)


def get_business_by_slug(slug, *, now=None):
    return business_response_queryset(
        include_detail_data=True,
        include_all_offers=True,
        now=now,
    ).filter(slug=slug).first()


def get_public_business_by_slug(slug, *, now=None):
    return business_response_queryset(include_detail_data=True, now=now).filter(
        slug=slug,
        status="published",
        is_active=True,
    ).first()


def get_business_for_update(slug):
    from businesses.models import Business
    return Business.objects.select_related("owner", "city", "city__state", "profile").prefetch_related("categories", "business_hours").filter(slug=slug).first()


def replace_business_hours(business, hours):
    """Replace a business schedule with already validated time slots."""
    from businesses.models import BusinessHour

    business.business_hours.all().delete()
    BusinessHour.objects.bulk_create(
        BusinessHour(business=business, **slot) for slot in hours
    )
    return business.business_hours.order_by("opens_at", "id")


def list_businesses(filters, *, now=None):
    queryset = business_response_queryset(now=now)
    if filters.get("owner_id"):
        queryset = queryset.filter(owner_id=filters["owner_id"])
    if filters.get("search"):
        search = filters["search"]
        queryset = queryset.filter(Q(name__icontains=search) | Q(profile__description__icontains=search) | Q(address__icontains=search) | Q(locality__icontains=search))
    field_filters = {field: filters[field] for field in ("is_active", "is_verified") if field in filters}
    if filters.get("locality"):
        field_filters["locality__iexact"] = filters["locality"]
    if filters.get("publication_status"):
        field_filters["status"] = filters["publication_status"]
    if filters.get("category"):
        field_filters["categories__slug"] = filters["category"]
    if filters.get("city"):
        field_filters["city__slug"] = filters["city"]
    if filters.get("established_year_min"):
        field_filters["established_year__gte"] = filters["established_year_min"]
    if filters.get("established_year_max"):
        field_filters["established_year__lte"] = filters["established_year_max"]
    queryset = queryset.filter(**field_filters).distinct()
    if "open_now" in filters:
        from businesses.models import BusinessHour
        current = timezone.localtime(now or timezone.now())
        open_slot = BusinessHour.objects.filter(
            business_id=OuterRef("pk"),
            days__contains=[current.weekday()],
            opens_at__lte=current.time().replace(tzinfo=None),
            closes_at__gt=current.time().replace(tzinfo=None),
        )
        queryset = queryset.alias(
            _regular_is_open=Exists(open_slot),
        )
        expected = filters["open_now"]
        queryset = queryset.filter(
            Q(display_business_hours=False) | Q(_regular_is_open=expected)
        )
    if "lat" in filters and "lng" in filters:
        origin = Point(filters["lng"], filters["lat"], srid=4326)
        direction = "-" if filters["sort_order"] == "desc" else ""
        return (
            queryset.filter(
                location__isnull=False,
                location__distance_lte=(origin, D(km=filters["radius_km"])),
            )
            .annotate(
                distance_km=ExpressionWrapper(
                    Distance("location", origin) / 1000.0,
                    output_field=FloatField(),
                )
            )
            .order_by(f"{direction}distance_km", "id")
        )
    direction = "-" if filters["sort_order"] == "desc" else ""
    return queryset.order_by(f"{direction}{filters['sort_by']}", "id")


def get_business_category(slug):
    if not slug:
        return None
    return BusinessCategory.objects.only("name", "display_name", "label").filter(slug=slug).first()


def paginate_businesses(queryset, page, page_size):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    pagination = {"page": page_obj.number, "page_size": page_size, "total_pages": paginator.num_pages, "total_items": paginator.count, "has_next": page_obj.has_next(), "has_previous": page_obj.has_previous()}
    return page_obj.object_list, pagination
