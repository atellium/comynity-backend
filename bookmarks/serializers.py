from rest_framework import serializers

from bookmarks.models import SavedItem
from businesses.models import Business
from businesses.serializers import BusinessListSerializer
from catalogs.models import Catalog
from catalogs.serializers import ProductListSerializer


ITEM_TYPE_MODELS = {
    SavedItem.ItemType.BUSINESS: Business,
    SavedItem.ItemType.PRODUCT: Catalog,
}


class SavedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedItem
        fields = ("id", "item_type", "object_id", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        instance = self.instance
        item_type = attrs.get(
            "item_type", getattr(instance, "item_type", None)
        )
        object_id = attrs.get("object_id", getattr(instance, "object_id", None))

        if item_type is not None and object_id is not None:
            model = ITEM_TYPE_MODELS.get(item_type)
            if model is None or not model.objects.filter(pk=object_id).exists():
                raise serializers.ValidationError(
                    {"object_id": "The referenced object does not exist."}
                )

        request = self.context.get("request")
        if request and item_type is not None and object_id is not None:
            duplicate = SavedItem.objects.filter(
                user=request.user,
                item_type=item_type,
                object_id=object_id,
            )
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"non_field_errors": ["This item is already saved."]}
                )

        return attrs


class SavedItemListSerializer(SavedItemSerializer):
    item = serializers.SerializerMethodField()

    class Meta(SavedItemSerializer.Meta):
        fields = SavedItemSerializer.Meta.fields + ("item",)

    def get_item(self, obj):
        item = self.context.get("resolved_items", {}).get(
            obj.item_type, {}
        ).get(obj.object_id)
        if item is None:
            return None

        serializer_class = {
            SavedItem.ItemType.BUSINESS: BusinessListSerializer,
            SavedItem.ItemType.PRODUCT: ProductListSerializer,
        }.get(obj.item_type)
        if serializer_class is None:
            return None
        return serializer_class(item, context=self.context).data
