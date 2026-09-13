from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from rest_framework import serializers

from products.models import Product, ProductCategory, ProductImage
from uploads.models import Upload
from uploads.serializers import UploadSerializer


class OptionalBooleanField(serializers.BooleanField):
    default_empty_html = serializers.empty


class ProductCategoryListQuerySerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    name = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    label = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    display_name = serializers.CharField(
        required=False,
        max_length=100,
        trim_whitespace=True,
    )
    slug = serializers.SlugField(required=False, max_length=255)
    aliases = serializers.CharField(required=False, max_length=500, trim_whitespace=True)
    parent = serializers.IntegerField(required=False, min_value=1)
    parent_slug = serializers.SlugField(required=False, max_length=255)
    is_root = OptionalBooleanField(required=False)
    is_active = OptionalBooleanField(required=False)
    is_featured = OptionalBooleanField(required=False)
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
            "display_name",
            "slug",
            "parent",
            "sort_order",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
        ),
    )
    sort_order = serializers.ChoiceField(
        required=False,
        default="asc",
        choices=("asc", "desc"),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
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


class PublicProductListQuerySerializer(serializers.Serializer):
    category = serializers.SlugField(required=False, max_length=255)
    search = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    min_price = serializers.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )
    max_price = serializers.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )
    price_type = serializers.ChoiceField(required=False, choices=Product.PriceType.choices)
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
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
    )

    def validate(self, attrs):
        min_price = attrs.get("min_price")
        max_price = attrs.get("max_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError(
                {"max_price": "Must be greater than or equal to min_price."}
            )
        return attrs


class ProductCategorySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    parent_slug = serializers.SlugField(source="parent.slug", read_only=True)

    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "name",
            "label",
            "display_name",
            "slug",
            "aliases",
            "parent",
            "parent_slug",
            "image",
            "sort_order",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
        )

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class ProductImageSerializer(serializers.ModelSerializer):
    upload = UploadSerializer(read_only=True)

    class Meta:
        model = ProductImage
        fields = ("id", "upload", "sort_order")


class ProductSerializer(serializers.ModelSerializer):
    categories = ProductCategorySerializer(many=True, read_only=True)
    images = ProductImageSerializer(
        many=True,
        read_only=True,
        source="product_images",
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "description",
            "categories",
            "price_type",
            "price",
            "mrp_price",
            "max_price",
            "images",
            "variants",
            "specifications",
            "status",
            "is_featured",
            "is_available",
            "sort_order",
            "created_at",
            "updated_at",
        )


class PublicProductListSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "description",
            "price_type",
            "price",
            "mrp_price",
            "max_price",
            "images",
            "variants",
            "specifications",
            "is_featured",
            "is_available",
            "sort_order",
        )

    def get_images(self, obj):
        request = self.context.get("request")
        urls = []
        for product_image in obj.product_images.all():
            upload = product_image.upload
            if upload.status != Upload.Status.READY:
                continue
            url = default_storage.url(upload.object_key)
            urls.append(
                request.build_absolute_uri(url)
                if request and url.startswith("/")
                else url
            )
        return urls


class ProductWriteSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.all(),
        many=True,
        required=False,
    )
    image_ids = serializers.PrimaryKeyRelatedField(
        queryset=Upload.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "public_id",
            "name",
            "slug",
            "description",
            "categories",
            "price_type",
            "price",
            "mrp_price",
            "max_price",
            "image_ids",
            "variants",
            "specifications",
            "status",
            "is_featured",
            "is_available",
            "sort_order",
        )
        read_only_fields = ("id", "public_id", "slug")
        extra_kwargs = {
            "name": {"required": True},
            "description": {"required": False},
            "price_type": {"required": False},
            "price": {"required": False},
            "mrp_price": {"required": False, "allow_null": True},
            "max_price": {"required": False, "allow_null": True},
            "variants": {"required": False},
            "specifications": {"required": False},
            "status": {"required": False},
            "is_featured": {"required": False},
            "is_available": {"required": False},
            "sort_order": {"required": False},
        }

    def validate(self, attrs):
        product = self.instance or Product(business=self.context["business"])
        for field, value in attrs.items():
            if field not in {"categories", "image_ids"}:
                setattr(product, field, value)

        try:
            product.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

        return attrs

    def _sync_images(self, product, images):
        ProductImage.objects.filter(product=product).exclude(upload__in=images).delete()
        existing_upload_ids = set(
            ProductImage.objects.filter(product=product, upload__in=images)
            .values_list("upload_id", flat=True)
        )
        for sort_order, upload in enumerate(images):
            if upload.pk in existing_upload_ids:
                ProductImage.objects.filter(product=product, upload=upload).update(
                    sort_order=sort_order
                )
            else:
                ProductImage.objects.create(
                    product=product,
                    upload=upload,
                    sort_order=sort_order,
                )

    def create(self, validated_data):
        categories = validated_data.pop("categories", [])
        images = validated_data.pop("image_ids", [])
        product = Product.objects.create(
            business=self.context["business"],
            **validated_data,
        )
        if categories:
            product.categories.set(categories)
        if images:
            self._sync_images(product, images)
        return product

    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        images = validated_data.pop("image_ids", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if categories is not None:
            instance.categories.set(categories)
        if images is not None:
            self._sync_images(instance, images)
        return instance
