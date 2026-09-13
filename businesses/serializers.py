from django.db import transaction
from django.core.files.storage import default_storage
from rest_framework import serializers

from businesses.models import Business, BusinessCategoryAssignment, BusinessHour, BusinessProfile
from businesses.services import get_business_hours_status
from categories.models import BusinessCategory
from locations.models import City
from uploads.models import Upload


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
            "slug",
            "established_year",
            "offerings",
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
        cover_image = None
        if obj.cover_image_id:
            cover_image = default_storage.url(obj.cover_image.object_key)
            if request and cover_image.startswith("/"):
                cover_image = request.build_absolute_uri(cover_image)
        return {"cover_image": cover_image}

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
    services = serializers.JSONField(source="profile.services", read_only=True)
    seo = BusinessSEOSerializer(source="profile", read_only=True)
    metadata = serializers.SerializerMethodField()

    class Meta(BusinessListSerializer.Meta):
        fields = (
            "id",
            "name",
            "slug",
            "established_year",
            "offerings",
            "sections",
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
            "services",
            "seo",
            "metadata",
        )

    def get_metadata(self, obj):
        return {"created_at": obj.created_at, "updated_at": obj.updated_at}

    def get_media(self, obj):
        media = super().get_media(obj)
        request = self.context.get("request")
        media["gallery"] = []
        for upload in obj.gallery.all():
            if upload.status != Upload.Status.READY:
                continue
            url = default_storage.url(upload.object_key)
            media["gallery"].append(
                request.build_absolute_uri(url)
                if request and url.startswith("/")
                else url
            )
        return media

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
    cover_image = serializers.PrimaryKeyRelatedField(
        queryset=Upload.objects.filter(status=Upload.Status.READY),
        required=False,
        allow_null=True,
    )
    gallery = serializers.PrimaryKeyRelatedField(
        queryset=Upload.objects.filter(status=Upload.Status.READY),
        many=True,
        required=False,
    )
    description = serializers.CharField(source="profile.description", required=False, allow_blank=True, allow_null=True)
    services = serializers.JSONField(source="profile.services", required=False, allow_null=True)
    established_year = serializers.IntegerField(required=False, allow_null=True, min_value=1800)
    alternate_numbers = serializers.JSONField(source="profile.alternate_numbers", required=False, allow_null=True)
    social_urls = serializers.JSONField(source="profile.social_urls", required=False, allow_null=True)
    seo_title = serializers.CharField(source="profile.seo_title", required=False, allow_blank=True)
    seo_description = serializers.CharField(source="profile.seo_description", required=False, allow_blank=True)
    seo_keywords = serializers.CharField(source="profile.seo_keywords", required=False, allow_blank=True)

    class Meta:
        model = Business
        fields = (
            "name", "categories", "address", "landmark", "locality", "city", "postal_code",
            "latitude", "longitude", "phone", "whatsapp", "email", "website", "cover_image", "gallery",
            "description", "services", "established_year", "offerings", "alternate_numbers", "social_urls",
            "is_active", "display_full_address", "display_business_hours",
            "seo_title", "seo_description", "seo_keywords",
        )

    def validate_cover_image(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and value.uploaded_by_id != request.user.pk:
            raise serializers.ValidationError("Select an upload owned by the current user.")
        return value

    def validate_gallery(self, value):
        upload_ids = [upload.pk for upload in value]
        if len(upload_ids) != len(set(upload_ids)):
            raise serializers.ValidationError("Gallery uploads must be unique.")
        request = self.context.get("request")
        if request:
            invalid_upload = next(
                (upload for upload in value if upload.uploaded_by_id != request.user.pk),
                None,
            )
            if invalid_upload:
                raise serializers.ValidationError("Select uploads owned by the current user.")
        return value

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
