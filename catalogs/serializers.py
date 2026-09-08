from rest_framework import serializers

from catalogs.models import Catalog, CatalogCategory, CatalogImage, CatalogImageUpload
from core.image_service import validate_image_upload


class OptionalBooleanField(serializers.BooleanField):
    default_empty_html = serializers.empty


class CatalogCategoryListQuerySerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    name = serializers.CharField(required=False, max_length=150, trim_whitespace=True)
    label = serializers.CharField(required=False, max_length=150, trim_whitespace=True)
    display_name = serializers.CharField(
        required=False, max_length=150, trim_whitespace=True
    )
    slug = serializers.SlugField(required=False, max_length=255)
    aliases = serializers.CharField(required=False, max_length=500, trim_whitespace=True)
    type = serializers.ChoiceField(required=False, choices=CatalogCategory.TypeChoices.choices)
    parent = serializers.IntegerField(required=False, min_value=1)
    parent_slug = serializers.SlugField(required=False, max_length=255)
    is_root = OptionalBooleanField(required=False)
    is_active = OptionalBooleanField(required=False)
    is_featured = OptionalBooleanField(required=False)
    is_display = OptionalBooleanField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    updated_after = serializers.DateTimeField(required=False)
    updated_before = serializers.DateTimeField(required=False)
    sort_by = serializers.ChoiceField(
        required=False,
        default="sort_order",
        choices=(
            "id",
            "name",
            "label",
            "slug",
            "type",
            "parent",
            "sort_order",
            "is_active",
            "is_featured",
            "is_display",
            "created_at",
            "updated_at",
        ),
    )
    sort_order = serializers.ChoiceField(
        required=False, default="asc", choices=("asc", "desc")
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )

    def validate(self, attrs):
        hierarchy_filters = sum(
            key in attrs for key in ("parent", "parent_slug", "is_root")
        )
        if hierarchy_filters > 1:
            raise serializers.ValidationError(
                {"parent": "Use only one of parent, parent_slug, or is_root."}
            )
        for prefix in ("created", "updated"):
            after = attrs.get(f"{prefix}_after")
            before = attrs.get(f"{prefix}_before")
            if after and before and after > before:
                raise serializers.ValidationError(
                    {f"{prefix}_before": f"Must be on or after {prefix}_after."}
                )
        return attrs


class CatalogCategoryListSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = CatalogCategory
        fields = (
            "id",
            "name",
            "label",
            "display_name",
            "slug",
            "type",
            "parent",
            "aliases",
            "image",
            "sort_order",
            "is_active",
            "is_featured",
            "is_display",
            "created_at",
            "updated_at",
        )


class ProductListQuerySerializer(serializers.Serializer):
    type = serializers.ChoiceField(required=False, choices=Catalog.TypeChoices.choices)
    category = serializers.SlugField(required=False, max_length=255)
    search = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    min_price = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0)
    max_price = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0)
    price_type = serializers.ChoiceField(required=False, choices=Catalog.PriceTypeChoices.choices)
    is_featured = OptionalBooleanField(required=False)
    sort_by = serializers.ChoiceField(
        required=False,
        default="sort_order",
        choices=("sort_order", "name", "price", "created_at"),
    )
    sort_order = serializers.ChoiceField(
        required=False,
        default="asc",
        choices=("asc", "desc"),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)

    def validate(self, attrs):
        min_price = attrs.get("min_price")
        max_price = attrs.get("max_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError(
                {"max_price": "Must be greater than or equal to min_price."}
            )
        return attrs


class PublicCatalogListQuerySerializer(ProductListQuerySerializer):
    type = serializers.ChoiceField(required=True, choices=Catalog.TypeChoices.choices)


class OwnerCatalogListQuerySerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=(
            Catalog.TypeChoices.PRODUCT,
            Catalog.TypeChoices.DOCTOR,
        ),
        required=True,
    )


class ProductCategorySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = CatalogCategory
        fields = ("id", "name", "label", "slug", "display_name", "image")

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class ProductListSerializer(serializers.ModelSerializer):
    categories = ProductCategorySerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Catalog
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "type",
            "price_type",
            "price",
            "max_price",
            "original_price",
            "variants",
            "specifications",
            "categories",
            "is_featured",
            "sort_order",
            "primary_image",
        )

    def get_primary_image(self, obj):
        images = getattr(obj, "_prefetched_primary_images", ())
        image = images[0] if images else None
        if image is None or not image.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = CatalogImage
        fields = (
            "id",
            "image",
            "alt_text",
            "is_primary",
            "is_active",
            "sort_order",
        )

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class CatalogImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = CatalogImage
        fields = (
            "id",
            "image",
            "alt_text",
            "is_primary",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        )

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class CatalogImageUploadCreateSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=("image/jpeg", "image/png", "image/webp"))


class CatalogImageUploadSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = CatalogImageUpload
        fields = ("id", "status", "error", "image")

    def get_image(self, obj):
        if not obj.catalog_image_id:
            return None
        return CatalogImageSerializer(obj.catalog_image, context=self.context).data


class CatalogImageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogImage
        fields = ("image", "alt_text", "is_primary", "is_active", "sort_order")
        extra_kwargs = {
            "alt_text": {"required": False},
            "is_primary": {"required": False},
            "is_active": {"required": False},
            "sort_order": {"required": False},
        }

    def validate_image(self, value):
        return validate_image_upload(value)

    def _clear_other_primary(self, catalog, instance=None):
        queryset = CatalogImage.objects.filter(catalog=catalog, is_primary=True)
        if instance is not None:
            queryset = queryset.exclude(pk=instance.pk)
        queryset.update(is_primary=False)

    def create(self, validated_data):
        catalog = self.context["catalog"]
        if validated_data.get("is_primary"):
            self._clear_other_primary(catalog)
        return CatalogImage.objects.create(catalog=catalog, **validated_data)

    def update(self, instance, validated_data):
        previous_image = instance.image if "image" in validated_data else None
        if validated_data.get("is_primary"):
            self._clear_other_primary(instance.catalog, instance)
        instance = super().update(instance, validated_data)
        if previous_image and previous_image.name != instance.image.name:
            previous_image.delete(save=False)
        return instance


class CatalogImageBulkUploadSerializer(serializers.Serializer):
    """Create multiple catalog images from one multipart request."""

    images = serializers.ListField(
        child=serializers.ImageField(),
        max_length=5,
        allow_empty=False,
    )
    alt_text = serializers.CharField(required=False, allow_blank=True, max_length=200)
    is_primary = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.IntegerField(required=False, default=0, min_value=0)
    sort_orders = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        required=False,
        allow_empty=False,
    )

    def validate_images(self, values):
        return [validate_image_upload(value) for value in values]

    def validate(self, attrs):
        sort_orders = attrs.get("sort_orders")
        if sort_orders is not None and len(sort_orders) != len(attrs["images"]):
            raise serializers.ValidationError(
                {"sort_orders": "Provide one sort order for every uploaded image."}
            )
        return attrs

    def create(self, validated_data):
        catalog = self.context["catalog"]
        images = validated_data.pop("images")
        make_primary = validated_data.pop("is_primary")
        starting_sort_order = validated_data.pop("sort_order")
        sort_orders = validated_data.pop("sort_orders", None)

        if make_primary:
            CatalogImage.objects.filter(
                catalog=catalog,
                is_primary=True,
            ).update(is_primary=False)

        return [
            CatalogImage.objects.create(
                catalog=catalog,
                image=image,
                is_primary=make_primary and index == 0,
                sort_order=(
                    sort_orders[index]
                    if sort_orders is not None
                    else starting_sort_order + index
                ),
                **validated_data,
            )
            for index, image in enumerate(images)
        ]


class CatalogGallerySyncSerializer(serializers.Serializer):
    """Validate the final ordered state of a catalog gallery."""

    images = serializers.ListField(
        child=serializers.ImageField(),
        max_length=5,
        required=False,
        allow_empty=True,
    )
    order = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )

    def validate_images(self, values):
        return [validate_image_upload(value) for value in values]

    def validate(self, attrs):
        parsed_order = []
        existing_ids = []
        new_indexes = []
        for token in attrs["order"]:
            kind, separator, raw_id = token.partition(":")
            if not separator or kind not in ("existing", "new") or not raw_id.isdigit():
                raise serializers.ValidationError(
                    {"order": f"Invalid gallery order token: {token}."}
                )
            value = int(raw_id)
            if kind == "existing" and value < 1:
                raise serializers.ValidationError(
                    {"order": f"Invalid gallery order token: {token}."}
                )
            parsed_order.append((kind, value))
            (existing_ids if kind == "existing" else new_indexes).append(value)

        if len(existing_ids) != len(set(existing_ids)):
            raise serializers.ValidationError(
                {"order": "An existing image cannot appear more than once."}
            )

        expected_new_indexes = list(range(len(attrs.get("images", []))))
        if sorted(new_indexes) != expected_new_indexes:
            raise serializers.ValidationError(
                {
                    "order": (
                        "Every uploaded image must appear exactly once as new:0, "
                        "new:1, and so on."
                    )
                }
            )
        attrs["parsed_order"] = parsed_order
        return attrs


class ProductBusinessSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    handle = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    thumbnail = serializers.SerializerMethodField()
    locality = serializers.CharField(read_only=True)
    city = serializers.SerializerMethodField()

    def get_thumbnail(self, obj):
        if not obj.thumbnail:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.thumbnail.url) if request else obj.thumbnail.url

    def get_city(self, obj):
        if not obj.city:
            return None
        return {
            "id": obj.city_id,
            "name": obj.city.name,
            "state": obj.city.state.name,
        }


class ProductDetailSerializer(serializers.ModelSerializer):
    business = ProductBusinessSerializer(read_only=True)
    categories = ProductCategorySerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Catalog
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "type",
            "description",
            "price_type",
            "price",
            "max_price",
            "original_price",
            "variants",
            "specifications",
            "custom_fields",
            "categories",
            "images",
            "is_featured",
            "sort_order",
            "business",
        )


class CatalogWriteSerializer(serializers.ModelSerializer):
    """Create and update catalogs owned by the authenticated business owner."""

    sort_order = serializers.IntegerField(required=False, min_value=0)

    class Meta:
        model = Catalog
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "type",
            "description",
            "price_type",
            "price",
            "max_price",
            "original_price",
            "variants",
            "specifications",
            "custom_fields",
            "categories",
            "is_featured",
            "is_active",
            "sort_order",
        )
        read_only_fields = ("id", "public_id", "slug")
        extra_kwargs = {
            "name": {"required": True},
            "type": {"required": True},
            "description": {"required": False},
            "price_type": {"required": False},
            "price": {"required": False, "allow_null": True},
            "max_price": {"required": False, "allow_null": True},
            "original_price": {"required": False, "allow_null": True},
            "variants": {"required": False},
            "specifications": {"required": False},
            "custom_fields": {"required": False},
            "categories": {"required": False},
            "is_featured": {"required": False},
            "is_active": {"required": False},
        }


class CatalogDetailSerializer(CatalogWriteSerializer):
    """Return an owned catalog with expanded category objects."""

    categories = CatalogCategoryListSerializer(many=True, read_only=True)


class OwnerCatalogListSerializer(CatalogWriteSerializer):
    """List catalogs owned by the authenticated business owner."""

    categories = ProductCategorySerializer(many=True, read_only=True)
