import uuid

from django.db import models


class SavedItem(models.Model):
    class ItemType(models.TextChoices):
        BUSINESS = "business", "Business"
        PRODUCT = "product", "Product"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
            
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="saved_items",
    )

    item_type = models.CharField(
        max_length=50,
        choices=ItemType.choices,
    )

    object_id = models.UUIDField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item_type", "object_id"],
                name="unique_user_saved_item",
            )
        ]

        indexes = [
            models.Index(
                fields=["user", "item_type", "object_id"],
                name="bookmarks_s_user_id_ceb735_idx",
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="bookmarks_s_user_id_582caf_idx",
            ),
        ]
