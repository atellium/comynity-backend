from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from businesses.serializers import BusinessListQuerySerializer
from offers.models import Offer
from uploads.models import Upload
from uploads.serializers import UploadSerializer


class NearbyOfferListQuerySerializer(BusinessListQuerySerializer):
    lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=True, min_value=-180, max_value=180)


class OfferSerializer(serializers.ModelSerializer):
    image = UploadSerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Offer
        fields = (
            "id",
            "title",
            "description",
            "image",
            "is_all_time",
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


class NearbyOfferSerializer(OfferSerializer):
    business = serializers.SerializerMethodField()
    distance_km = serializers.FloatField(read_only=True)

    class Meta(OfferSerializer.Meta):
        fields = OfferSerializer.Meta.fields + ("business", "distance_km")

    def get_business(self, obj):
        city = obj.business.city
        return {
            "id": obj.business_id,
            "name": obj.business.name,
            "slug": obj.business.slug,
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
    image_id = serializers.PrimaryKeyRelatedField(
        queryset=Upload.objects.all(),
        required=False,
        allow_null=True,
        source="image",
        write_only=True,
    )

    class Meta:
        model = Offer
        fields = (
            "title",
            "description",
            "image_id",
            "is_all_time",
            "starts_at",
            "expires_at",
            "is_active",
            "sort_order",
            "terms",
        )
        extra_kwargs = {
            "description": {"required": False},
            "is_all_time": {"required": False},
            "starts_at": {"required": False, "allow_null": True},
            "expires_at": {"required": False, "allow_null": True},
            "is_active": {"required": False},
            "sort_order": {"required": False},
            "terms": {"required": False},
        }

    def validate(self, attrs):
        is_all_time = attrs.get(
            "is_all_time", getattr(self.instance, "is_all_time", False)
        )

        if is_all_time:
            attrs["starts_at"] = None
            attrs["expires_at"] = None
            return attrs

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

        offer = self.instance or Offer(business=self.context["business"])
        for field, value in attrs.items():
            setattr(offer, field, value)

        try:
            offer.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

        return attrs

    def create(self, validated_data):
        return Offer.objects.create(
            business=self.context["business"],
            **validated_data,
        )
