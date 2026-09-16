import json

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.text import slugify
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


class NearbyProductListQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    category = serializers.SlugField(max_length=255)
    radius = serializers.FloatField(
        required=False,
        min_value=0.1,
        max_value=100,
    )
    radius_km = serializers.FloatField(
        required=False,
        min_value=0.1,
        max_value=100,
        default=5,
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
    )

    def validate(self, attrs):
        radius = attrs.pop("radius", None)
        radius_km = attrs.get("radius_km")
        if radius is not None and radius_km is not None and radius != radius_km:
            raise serializers.ValidationError(
                {"radius": "Use either radius or radius_km, not conflicting values."}
            )
        if radius is not None:
            attrs["radius_km"] = radius
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


class ProductCategoryBulkImportSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True)
    parent_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        write_only=True,
    )

    def validate_file(self, value):
        if not value.name.lower().endswith(".json"):
            raise serializers.ValidationError("Upload a .json file.")
        return value

    def validate(self, attrs):
        parent_id = attrs.get("parent_id")
        parent = None
        if parent_id is not None:
            parent = ProductCategory.objects.filter(pk=parent_id).first()
            if parent is None:
                raise serializers.ValidationError(
                    {"parent_id": f"Product category with ID {parent_id} does not exist."}
                )

        categories = self._read_categories(attrs["file"])
        seen_slugs = set()
        validated_categories = []
        for index, category in enumerate(categories, start=1):
            values = self._validated_category(category, index)
            if values["slug"] in seen_slugs:
                raise serializers.ValidationError(
                    {"file": f"Category #{index} repeats slug {values['slug']!r}."}
                )
            seen_slugs.add(values["slug"])
            validated_categories.append(values)

        attrs["parent"] = parent
        attrs["categories"] = validated_categories
        return attrs

    def _read_categories(self, uploaded_file):
        try:
            uploaded_file.seek(0)
            content = b"".join(uploaded_file.chunks()).decode("utf-8")
            categories = json.loads(content)
        except UnicodeDecodeError as exc:
            raise serializers.ValidationError(
                {"file": "The JSON file must be UTF-8 encoded."}
            ) from exc
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError(
                {"file": f"Invalid JSON file: {exc.msg}."}
            ) from exc

        if isinstance(categories, dict):
            categories = categories.get("categories")

        if not isinstance(categories, list):
            raise serializers.ValidationError(
                {"file": "The JSON file must contain a list, or an object with a categories list."}
            )
        return categories

    def _validated_category(self, category, index):
        if not isinstance(category, dict):
            raise serializers.ValidationError(
                {"file": f"Category #{index} must be a JSON object."}
            )

        name = str(category.get("name", "")).strip()
        if not name:
            raise serializers.ValidationError(
                {"file": f"Category #{index} is missing a non-empty name."}
            )

        sort_order = category.get("sort_order", 100)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int) or sort_order < 0:
            raise serializers.ValidationError(
                {"file": f"Category #{index} sort_order must be a non-negative integer."}
            )

        boolean_values = {}
        for field, default in (
            ("is_active", True),
            ("is_featured", False),
        ):
            value = category.get(field, default)
            if not isinstance(value, bool):
                raise serializers.ValidationError(
                    {"file": f"Category #{index} {field} must be a boolean."}
                )
            boolean_values[field] = value

        slug = str(
            category.get("slug") or slugify(category.get("label") or name)
        ).strip()
        if not slug:
            raise serializers.ValidationError(
                {"file": f"Category #{index} slug could not be generated."}
            )

        return {
            "name": name,
            "slug": slug,
            "label": str(category.get("label", "")).strip(),
            "display_name": str(category.get("display_name", "")).strip(),
            "aliases": str(category.get("aliases", "")).strip(),
            "sort_order": sort_order,
            **boolean_values,
        }

    @transaction.atomic
    def save(self, **kwargs):
        parent = self.validated_data["parent"]
        created_count = 0
        updated_count = 0
        imported_categories = []

        for values in self.validated_data["categories"]:
            category = ProductCategory.objects.filter(slug=values["slug"]).first()
            created = category is None
            if created:
                category = ProductCategory(slug=values["slug"])

            for field, value in values.items():
                setattr(category, field, value)
            category.parent = parent
            try:
                category.full_clean()
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
            category.save()

            created_count += int(created)
            updated_count += int(not created)
            imported_categories.append(category)

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(imported_categories),
            "categories": imported_categories,
        }


class ProductImageSerializer(serializers.ModelSerializer):
    upload = UploadSerializer(read_only=True)

    class Meta:
        model = ProductImage
        fields = ("id", "upload", "sort_order")


class ProductBusinessSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    locality = serializers.CharField(read_only=True)
    city = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()

    def get_city(self, obj):
        if not obj.city:
            return None
        return {
            "id": obj.city_id,
            "name": obj.city.name,
            "state_id": obj.city.state_id,
            "state": obj.city.state.name,
        }

    def get_media(self, obj):
        cover_image = None
        if obj.cover_image_id:
            request = self.context.get("request")
            cover_image = default_storage.url(obj.cover_image.object_key)
            if request and cover_image.startswith("/"):
                cover_image = request.build_absolute_uri(cover_image)
        return {"cover_image": cover_image}


class ProductSerializer(serializers.ModelSerializer):
    business = ProductBusinessSerializer(read_only=True)
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
            "business",
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
