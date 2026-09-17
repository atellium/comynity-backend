from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from catalogs.models import Catalog
from uploads.models import Upload
from uploads.serializers import UploadSerializer


class CatalogListQuerySerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=Catalog.CatalogType.choices,
        required=False,
    )


class CatalogSerializer(serializers.ModelSerializer):
    business = serializers.SerializerMethodField()
    images = UploadSerializer(many=True, read_only=True)

    class Meta:
        model = Catalog
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "business",
            "description",
            "type",
            "images",
            "custom_fields",
            "is_active",
            "is_available",
            "created_at",
            "updated_at",
        )

    def get_business(self, obj):
        return {
            "id": obj.business_id,
            "name": obj.business.name,
            "slug": obj.business.slug,
        }


class CatalogWriteSerializer(serializers.ModelSerializer):
    image_ids = serializers.PrimaryKeyRelatedField(
        queryset=Upload.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Catalog
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "description",
            "type",
            "image_ids",
            "custom_fields",
            "is_active",
            "is_available",
        )
        read_only_fields = (
            "id",
            "public_id",
            "slug",
        )
        extra_kwargs = {
            "name": {"required": True},
            "description": {"required": False},
            "type": {"required": False},
            "custom_fields": {"required": False, "allow_null": True},
            "is_active": {"required": False},
            "is_available": {"required": False},
        }

    def validate(self, attrs):
        catalog = self.instance or Catalog(business=self.context["business"])

        for field, value in attrs.items():
            if field != "image_ids":
                setattr(catalog, field, value)

        try:
            catalog.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

        return attrs

    def create(self, validated_data):
        images = validated_data.pop("image_ids", [])
        catalog = Catalog.objects.create(
            business=self.context["business"],
            **validated_data,
        )

        if images:
            catalog.images.set(images)

        return catalog

    def update(self, instance, validated_data):
        images = validated_data.pop("image_ids", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        if images is not None:
            instance.images.set(images)

        return instance
