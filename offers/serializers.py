from django.db import transaction
from rest_framework import serializers

from core.image_service import validate_image_upload
from businesses.serializers import BusinessListQuerySerializer
from offers.models import Offer


class NearbyOfferListQuerySerializer(BusinessListQuerySerializer):
    lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=True, min_value=-180, max_value=180)


class OfferSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Offer
        fields = (
            "id",
            "title",
            "description",
            "image",
            "starts_at",
            "expires_at",
            "is_active",
            "is_currently_active",
            "status",
            "sort_order",
            "terms",
            "created_at",
            "updated_at",
        )

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class NearbyOfferSerializer(OfferSerializer):
    business = serializers.SerializerMethodField()
    distance_km = serializers.FloatField(read_only=True)

    class Meta(OfferSerializer.Meta):
        fields = OfferSerializer.Meta.fields + ("business", "distance_km")

    def get_business(self, obj):
        request = self.context.get("request")
        thumbnail = None
        if obj.business.thumbnail:
            thumbnail = obj.business.thumbnail.url
            if request:
                thumbnail = request.build_absolute_uri(thumbnail)
        city = obj.business.city
        return {
            "id": obj.business_id,
            "name": obj.business.name,
            "handle": obj.business.handle,
            "slug": obj.business.slug,
            "thumbnail": thumbnail,
            "locality": obj.business.locality,
            "city": (
                {
                    "id": city.pk,
                    "name": city.name,
                    "state": city.state.name,
                }
                if city
                else None
            ),
        }


class OfferWriteSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Offer
        fields = (
            "title",
            "description",
            "image",
            "starts_at",
            "expires_at",
            "is_active",
            "sort_order",
            "terms",
        )
        extra_kwargs = {
            "description": {"required": False},
            "starts_at": {"required": False, "allow_null": True},
            "expires_at": {"required": False, "allow_null": True},
            "is_active": {"required": False},
            "sort_order": {"required": False},
            "terms": {"required": False},
        }

    def validate_image(self, value):
        return validate_image_upload(value) if value is not None else None

    def validate(self, attrs):
        starts_at = attrs.get(
            "starts_at", getattr(self.instance, "starts_at", None)
        )
        expires_at = attrs.get(
            "expires_at", getattr(self.instance, "expires_at", None)
        )
        if starts_at and expires_at and expires_at <= starts_at:
            raise serializers.ValidationError(
                {"expires_at": "Expiry time must be after the start time."}
            )
        return attrs

    def create(self, validated_data):
        return Offer.objects.create(
            business=self.context["business"],
            **validated_data,
        )

    def update(self, instance, validated_data):
        previous_name = instance.image.name if "image" in validated_data else None
        previous_storage = instance.image.storage if previous_name else None
        instance = super().update(instance, validated_data)
        if previous_name and previous_name != instance.image.name:
            transaction.on_commit(
                lambda: previous_storage.delete(previous_name)
            )
        return instance
