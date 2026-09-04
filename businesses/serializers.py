from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from businesses.models import Business, BusinessCategoryAssignment, BusinessGalleryImage, BusinessGalleryUpload, BusinessHoliday, BusinessHour, BusinessProfile
from businesses.services import get_business_hours_status
from categories.models import BusinessCategory
from catalogs.models import Catalog, CatalogCategory
from locations.models import City
from core.image_service import validate_image_upload


class OptionalBooleanField(serializers.BooleanField):
    default_empty_html = serializers.empty


class BusinessHourSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHour
        fields = ("id", "days", "opens_at", "closes_at")


class BusinessHourInputSerializer(serializers.Serializer):
    days = serializers.ListField(
        child=serializers.ChoiceField(choices=BusinessHour.Weekday.choices),
        allow_empty=False,
        max_length=7,
    )
    opens_at = serializers.TimeField()
    closes_at = serializers.TimeField()

    def validate_days(self, days):
        if len(days) != len(set(days)):
            raise serializers.ValidationError("Weekdays must be unique within a slot.")
        return sorted(days)

    def validate(self, attrs):
        if attrs["closes_at"] <= attrs["opens_at"]:
            raise serializers.ValidationError(
                {"closes_at": "Closing time must be later than opening time."}
            )
        return attrs


class BusinessHoursUpdateSerializer(serializers.Serializer):
    business_hours = BusinessHourInputSerializer(many=True, allow_empty=True)

    def validate_business_hours(self, hours):
        for index, slot in enumerate(hours):
            for other_index, other in enumerate(hours[index + 1 :], start=index + 1):
                same_day = set(slot["days"]) & set(other["days"])
                overlaps = (
                    slot["opens_at"] < other["closes_at"]
                    and slot["closes_at"] > other["opens_at"]
                )
                if same_day and overlaps:
                    days = ", ".join(
                        BusinessHour.Weekday(day).label for day in sorted(same_day)
                    )
                    raise serializers.ValidationError(
                        f"Slots {index + 1} and {other_index + 1} overlap on {days}."
                    )
        return hours


class BusinessHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHoliday
        fields = ("id", "start_date", "end_date", "reason")
        read_only_fields = ("id",)

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be on or after start date."})
        duplicate = BusinessHoliday.objects.filter(
            business=self.context["business"], start_date__lte=end_date, end_date__gte=start_date
        )
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"start_date": "This holiday range overlaps an existing holiday."})
        return attrs


class BusinessGalleryImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = BusinessGalleryImage
        fields = ("id", "image", "created_at", "updated_at")

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class BusinessGalleryUploadCreateSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(
        choices=("image/jpeg", "image/png", "image/webp")
    )


class BusinessGalleryUploadSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = BusinessGalleryUpload
        fields = ("id", "status", "error", "image")

    def get_image(self, obj):
        if not obj.gallery_image_id:
            return None
        return BusinessGalleryImageSerializer(
            obj.gallery_image,
            context=self.context,
        ).data


class BusinessGalleryImageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessGalleryImage
        fields = ("image",)

    def validate_image(self, value):
        return validate_image_upload(value)

    def create(self, validated_data):
        business = self.context["business"]
        if business.gallery_images.count() >= 20:
            raise serializers.ValidationError(
                {"image": "A business can have a maximum of 20 gallery images."}
            )
        return BusinessGalleryImage.objects.create(business=business, **validated_data)

    def update(self, instance, validated_data):
        previous_image = instance.image if "image" in validated_data else None
        instance = super().update(instance, validated_data)
        if previous_image and previous_image.name != instance.image.name:
            previous_image.delete(save=False)
        return instance


class BusinessGalleryBulkUploadSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False,
    )

    def validate_images(self, values):
        return [validate_image_upload(value) for value in values]

    def validate(self, attrs):
        business = self.context["business"]
        if business.gallery_images.count() + len(attrs["images"]) > 20:
            raise serializers.ValidationError(
                {"images": "A business can have a maximum of 20 gallery images."}
            )
        return attrs


class BusinessGallerySyncSerializer(serializers.Serializer):
    """Validate the complete retained gallery plus any newly uploaded images."""

    existing_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        allow_empty=True,
    )
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        default=list,
        allow_empty=True,
    )

    def validate_images(self, values):
        return [validate_image_upload(value) for value in values]

    def validate(self, attrs):
        existing_ids = attrs["existing_ids"]
        if len(existing_ids) != len(set(existing_ids)):
            raise serializers.ValidationError(
                {"existing_ids": "An existing image cannot appear more than once."}
            )
        if len(existing_ids) + len(attrs["images"]) > 20:
            raise serializers.ValidationError(
                {"images": "A business can have a maximum of 20 gallery images."}
            )
        return attrs


class BusinessListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, max_length=180, trim_whitespace=True)
    category = serializers.SlugField(required=False, max_length=255)
    city = serializers.SlugField(required=False, max_length=100)
    locality = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, min_value=-180, max_value=180)
    radius_km = serializers.FloatField(
        required=False, default=25.0, min_value=0.1, max_value=200.0
    )
    is_active = OptionalBooleanField(required=False)
    is_verified = OptionalBooleanField(required=False)
    open_now = OptionalBooleanField(required=False)
    publication_status = serializers.ChoiceField(required=False, choices=Business.Status.choices)
    status = serializers.ChoiceField(required=False, choices=Business.Status.choices, write_only=True)
    established_year_min = serializers.IntegerField(required=False, min_value=1800)
    established_year_max = serializers.IntegerField(required=False, min_value=1800)
    sort_by = serializers.ChoiceField(required=False, default="name", choices=("name", "established_year", "published_at", "created_at", "updated_at"))
    sort_order = serializers.ChoiceField(required=False, default="asc", choices=("asc", "desc"))
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)

    def validate(self, attrs):
        if ("lat" in attrs) != ("lng" in attrs):
            raise serializers.ValidationError({"location": "lat and lng must be provided together."})
        if attrs.get("status") and attrs.get("publication_status") and attrs["status"] != attrs["publication_status"]:
            raise serializers.ValidationError({"status": "Use either status or publication_status, not conflicting values."})
        if attrs.get("established_year_min", 1800) > attrs.get("established_year_max", 9999):
            raise serializers.ValidationError({"established_year_max": "Must be greater than or equal to established_year_min."})
        attrs["publication_status"] = attrs.get("publication_status", attrs.pop("status", None))
        return attrs


class CategorySummarySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="public_name", read_only=True)

    class Meta:
        model = BusinessCategory
        fields = ("id", "name", "slug", "display_name")


class CategoryFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = ("name", "display_name", "label")


class BusinessLocationSerializer(serializers.Serializer):
    address = serializers.SerializerMethodField()
    landmark = serializers.SerializerMethodField()
    locality = serializers.CharField()
    city = serializers.SerializerMethodField()
    postal_code = serializers.SerializerMethodField()
    coordinates = serializers.SerializerMethodField()
    display_full_address = serializers.BooleanField()

    def get_address(self, obj):
        return obj.address

    def get_landmark(self, obj):
        return obj.landmark

    def get_postal_code(self, obj):
        return obj.postal_code

    def get_city(self, obj):
        if not obj.city:
            return None
        return {
            "id": obj.city_id,
            "name": obj.city.name,
            "state_id": obj.city.state_id,
            "state": obj.city.state.name,
        }

    def get_coordinates(self, obj):
        return {"latitude": obj.latitude, "longitude": obj.longitude, "distance_km": getattr(obj, "distance_km", None)}


class OwnerBusinessLocationSerializer(serializers.Serializer):
    address = serializers.CharField()
    landmark = serializers.CharField(allow_null=True)
    locality = serializers.CharField(allow_null=True)
    city = serializers.SerializerMethodField()
    postal_code = serializers.CharField()
    coordinates = serializers.SerializerMethodField()
    display_full_address = serializers.BooleanField()

    def get_city(self, obj):
        if not obj.city:
            return None
        return {
            "id": obj.city_id,
            "name": obj.city.name,
            "state_id": obj.city.state_id,
            "state": obj.city.state.name,
        }

    def get_coordinates(self, obj):
        return {
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "distance_km": getattr(obj, "distance_km", None),
        }


class BusinessContactSerializer(serializers.Serializer):
    phone = serializers.CharField()
    whatsapp = serializers.CharField()
    alternate_numbers = serializers.JSONField(source="profile.alternate_numbers", allow_null=True)
    email = serializers.EmailField()
    website = serializers.URLField()
    social_urls = serializers.JSONField(source="profile.social_urls", allow_null=True)


class BusinessPublicationSerializer(serializers.Serializer):
    status = serializers.CharField()
    is_active = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    published_at = serializers.DateTimeField()


class BusinessSEOSerializer(serializers.Serializer):
    title = serializers.CharField(source="seo_title")
    description = serializers.CharField(source="seo_description")
    keywords = serializers.CharField(source="seo_keywords")


class CatalogProductSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Catalog
        fields = (
            "id",
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
            "primary_image",
        )

    def get_primary_image(self, obj):
        images = getattr(obj, "_prefetched_primary_images", ())
        image = images[0] if images else None
        if image is None or not image.image:
            return None
        request = self.context.get("request")
        return (
            request.build_absolute_uri(image.image.url)
            if request
            else image.image.url
        )


class CatalogCategorySummarySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = CatalogCategory
        fields = ("id", "name", "label", "slug", "type", "display_name", "image")

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class BusinessListSerializer(serializers.ModelSerializer):
    established_year = serializers.IntegerField(allow_null=True, read_only=True)
    publication_status = serializers.CharField(source="status", read_only=True)
    last_updated = serializers.DateTimeField(source="updated_at", read_only=True)
    categories = CategorySummarySerializer(many=True, read_only=True)
    media = serializers.SerializerMethodField()
    location = BusinessLocationSerializer(source="*", read_only=True)
    contact = BusinessContactSerializer(source="*", read_only=True)
    hours = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = (
            "id",
            "name",
            "handle",
            "slug",
            "established_year",
            "is_active",
            "is_verified",
            "publication_status",
            "last_updated",
            "categories",
            "media",
            "location",
            "contact",
            "hours",
        )

    def get_media(self, obj):
        request = self.context.get("request")
        thumbnail = None
        if obj.thumbnail:
            url = obj.thumbnail.url
            thumbnail = request.build_absolute_uri(url) if request else url
        media = {"thumbnail": thumbnail}
        if hasattr(obj, "_prefetched_gallery_images"):
            media["gallery"] = [
                request.build_absolute_uri(image.image.url)
                if request
                else image.image.url
                for image in obj._prefetched_gallery_images
                if image.image
            ]
        return media

    def get_hours(self, obj):
        if not obj.display_business_hours:
            return None
        hours = getattr(obj, "_prefetched_business_hours", ())
        return get_business_hours_status(
            hours,
            now=self.context.get("now"),
        )


class BusinessDetailSerializer(BusinessListSerializer):
    """Detailed representation using the same grouped contract as the list API."""

    description = serializers.CharField(source="profile.description", allow_null=True, read_only=True)
    seo = BusinessSEOSerializer(source="profile", read_only=True)
    metadata = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()

    class Meta(BusinessListSerializer.Meta):
        fields = (
            "id",
            "name",
            "handle",
            "slug",
            "established_year",
            "is_active",
            "is_verified",
            "publication_status",
            "last_updated",
            "description",
            "categories",
            "media",
            "location",
            "contact",
            "hours",
            "product",
            "offers",
            "seo",
            "metadata",
        )

    def get_metadata(self, obj):
        return {"created_at": obj.created_at, "updated_at": obj.updated_at}

    def get_offers(self, obj):
        request = self.context.get("request")
        return [
            {
                "id": offer.pk,
                "title": offer.title,
                "description": offer.description,
                "image": (
                    request.build_absolute_uri(offer.image.url)
                    if request and offer.image
                    else offer.image.url if offer.image else None
                ),
                "starts_at": offer.starts_at,
                "expires_at": offer.expires_at,
                "is_active": offer.is_active,
                "is_currently_active": offer.is_currently_active,
                "status": offer.status,
                "sort_order": offer.sort_order,
                "terms": offer.terms,
                "created_at": offer.created_at,
                "updated_at": offer.updated_at,
            }
            for offer in getattr(obj, "_prefetched_offers", ())
        ]

    def get_product(self, obj):
        products = list(getattr(obj, "_prefetched_catalog_products", ()))[:10]
        categories = getattr(obj, "_prefetched_product_categories", None)
        if categories is None and obj.pk:
            categories = (
                CatalogCategory.objects.filter(
                    catalog_items__business_id=obj.pk,
                    catalog_items__type=Catalog.TypeChoices.PRODUCT,
                    catalog_items__is_active=True,
                    is_active=True,
                    is_display=True,
                )
                .distinct()
                .order_by("sort_order", "name")
            )
        elif categories is not None:
            categories = [category for category in categories if category.is_display]
        return {
            "categories": CatalogCategorySummarySerializer(
                categories or (),
                many=True,
                context=self.context,
            ).data,
            "items": CatalogProductSerializer(
                products,
                many=True,
                context=self.context,
            ).data,
        }

    def get_hours(self, obj):
        hours_status = super().get_hours(obj)
        if hours_status is None:
            return None

        hours = getattr(obj, "_prefetched_business_hours", ())
        weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        schedule = {weekday: [] for weekday in weekdays}
        for hour in hours:
            slot = {"opens_at": hour.opens_at, "closes_at": hour.closes_at}
            for day in hour.days:
                schedule[weekdays[day]].append(slot.copy())

        return {**hours_status, "schedule": schedule}


class OwnerBusinessDetailSerializer(BusinessDetailSerializer):
    owner_id = serializers.UUIDField(read_only=True)
    location = OwnerBusinessLocationSerializer(source="*", read_only=True)
    visibility = serializers.SerializerMethodField()

    class Meta(BusinessDetailSerializer.Meta):
        fields = BusinessDetailSerializer.Meta.fields + ("owner_id", "visibility")

    def get_visibility(self, obj):
        return {
            "display_full_address": obj.display_full_address,
            "display_business_hours": obj.display_business_hours,
        }


class BusinessUpdateSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(queryset=BusinessCategory.objects.all(), many=True, required=False)
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.select_related("state"), required=False)
    description = serializers.CharField(source="profile.description", required=False, allow_blank=True, allow_null=True)
    established_year = serializers.IntegerField(required=False, allow_null=True, min_value=1800)
    alternate_numbers = serializers.JSONField(source="profile.alternate_numbers", required=False, allow_null=True)
    social_urls = serializers.JSONField(source="profile.social_urls", required=False, allow_null=True)
    seo_title = serializers.CharField(source="profile.seo_title", required=False, allow_blank=True)
    seo_description = serializers.CharField(source="profile.seo_description", required=False, allow_blank=True)
    seo_keywords = serializers.CharField(source="profile.seo_keywords", required=False, allow_blank=True)

    class Meta:
        model = Business
        fields = (
            "name", "handle", "categories", "address", "landmark", "locality", "city", "postal_code",
            "latitude", "longitude", "phone", "whatsapp", "email", "website", "thumbnail",
            "description", "established_year", "alternate_numbers", "social_urls",
            "is_active", "display_full_address", "display_business_hours",
            "seo_title", "seo_description", "seo_keywords",
        )

    def validate_thumbnail(self, value):
        return validate_image_upload(value)

    def validate_description(self, value):
        return value or ""

    def validate_categories(self, value):
        category_ids = [category.pk for category in value]
        if len(category_ids) != len(set(category_ids)):
            raise serializers.ValidationError("Categories must be unique.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", serializers.empty)
        profile_data = validated_data.pop("profile", {})
        instance = super().update(instance, validated_data)
        if categories is not serializers.empty:
            instance.category_assignments.all().delete()
            BusinessCategoryAssignment.objects.bulk_create(
                BusinessCategoryAssignment(business=instance, category=category, sort_order=position)
                for position, category in enumerate(categories)
            )
        if profile_data:
            # Supply the PATCH values during creation. Creating an empty profile
            # first can violate a legacy database NOT NULL constraint before the
            # submitted description gets assigned below.
            profile, _ = BusinessProfile.objects.get_or_create(
                business=instance,
                defaults=profile_data,
            )
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.full_clean()
            profile.save()
        return instance
