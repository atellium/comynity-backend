from rest_framework import serializers

from categories.models import BusinessCategory, ProductCategory


class OptionalBooleanField(serializers.BooleanField):
    default_empty_html = serializers.empty


class BusinessCategoryListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    name = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    label = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    display_name = serializers.CharField(required=False, max_length=100, trim_whitespace=True)
    slug = serializers.SlugField(required=False, max_length=255)
    is_active = OptionalBooleanField(required=False)
    is_featured = OptionalBooleanField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    updated_after = serializers.DateTimeField(required=False)
    updated_before = serializers.DateTimeField(required=False)
    sort_by = serializers.ChoiceField(
        required=False,
        default="sort_order",
        choices=("id", "name", "label", "display_name", "slug", "sort_order", "is_active", "is_featured", "created_at", "updated_at"),
    )
    sort_order = serializers.ChoiceField(
        required=False,
        default="asc",
        choices=("asc", "desc"),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)

    def validate(self, attrs):
        for prefix in ("created", "updated"):
            after = attrs.get(f"{prefix}_after")
            before = attrs.get(f"{prefix}_before")
            if after and before and after > before:
                raise serializers.ValidationError(
                    {f"{prefix}_before": f"Must be on or after {prefix}_after."}
                )
        return attrs


class BusinessCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = (
            "id",
            "name",
            "display_name",
            "label",
            "slug",
            "aliases",
            "image",
            "sort_order",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
        )


class ProductCategoryListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    name = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    label = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    display_name = serializers.CharField(required=False, max_length=100, trim_whitespace=True)
    slug = serializers.SlugField(required=False, max_length=255)
    parent = serializers.IntegerField(required=False, min_value=1)
    is_root = OptionalBooleanField(required=False)
    is_active = OptionalBooleanField(required=False)
    is_featured = OptionalBooleanField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    updated_after = serializers.DateTimeField(required=False)
    updated_before = serializers.DateTimeField(required=False)
    sort_by = serializers.ChoiceField(
        required=False,
        default="name",
        choices=("id", "name", "label", "display_name", "slug", "is_active", "is_featured", "created_at", "updated_at"),
    )
    sort_order = serializers.ChoiceField(
        required=False,
        default="asc",
        choices=("asc", "desc"),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)

    def validate(self, attrs):
        if "parent" in attrs and attrs.get("is_root") is True:
            raise serializers.ValidationError(
                {"parent": "Cannot be combined with is_root=true."}
            )
        for prefix in ("created", "updated"):
            after = attrs.get(f"{prefix}_after")
            before = attrs.get(f"{prefix}_before")
            if after and before and after > before:
                raise serializers.ValidationError(
                    {f"{prefix}_before": f"Must be on or after {prefix}_after."}
                )
        return attrs


class ProductCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "name",
            "display_name",
            "label",
            "slug",
            "aliases",
            "image",
            "parent",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
        )


class CategorySearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = ("id", "name", "display_name", "label", "slug", "aliases", "image")
