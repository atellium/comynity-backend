import uuid
import secrets
import string
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from core.models import TimestampedModel


PUBLIC_ID_ALPHABET = string.ascii_lowercase + string.digits


def generate_product_public_id():
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(8))


class Product(TimestampedModel):
    class PriceType(models.TextChoices):
        FIXED = "fixed", "Fixed Price"
        ASK = "ask", "Ask for Price"
        RANGE = "range", "Price Range"
        STARTS_FROM = "starts_from", "Starts From"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(
        max_length=8,
        unique=True,
        editable=False,
        default=generate_product_public_id,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9]{8}$",
                message="Public ID must contain exactly 8 alphanumeric characters.",
            )
        ],
    )

    # Ownership
    business = models.ForeignKey("businesses.Business", on_delete=models.CASCADE, related_name="products")

    # Identity
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)

    # Classification
    categories = models.ManyToManyField(
        "products.ProductCategory",
        related_name="products",
        blank=True,
    )

    # Pricing
    price_type = models.CharField(
        max_length=20,
        choices=PriceType.choices,
        default=PriceType.FIXED,
        db_index=True,
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    mrp_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    #Media
    images = models.ManyToManyField(
        "uploads.Upload",
        through="ProductImage",
        through_fields=("product", "upload"),
        related_name="products",
        blank=True,
    )

    # Product information
    variants = models.JSONField(
        default=dict,
        blank=True,
        help_text="Product variants."
    )
    specifications = models.JSONField(
        default=list,
        blank=True,
        help_text="Product specifications."
    )

    # Visibility
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )
    is_available = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        db_table = "products"

        ordering = (
            "sort_order",
            "-created_at",
        )

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "status",
                    "is_available",
                ],
                name="prod_business_status_idx",
            ),
            models.Index(
                fields=[
                    "business",
                    "is_featured",
                    "sort_order",
                ],
                name="prod_business_featured_idx",
            ),
            models.Index(
                fields=[
                    "status",
                    "is_available",
                    "-created_at",
                ],
                name="prod_active_recent_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="product_price_non_negative",
            ),

            models.CheckConstraint(
                condition=(
                    Q(mrp_price__isnull=True)
                    | Q(mrp_price__gte=0)
                ),
                name="product_mrp_price_non_negative",
            ),

            models.CheckConstraint(
                condition=(
                    Q(max_price__isnull=True)
                    | Q(max_price__gte=0)
                ),
                name="product_max_price_non_negative",
            ),
        ]

    def clean(self):
        super().clean()

        self.name = (self.name or "").strip()

        errors = {}

        if not self.name:
            errors["name"] = "Product name cannot be empty."

        if self.price_type == self.PriceType.FIXED:
            if self.price <= 0:
                errors["price"] = (
                    "Fixed-price products must have a price greater than 0."
                )

            if self.max_price is not None:
                errors["max_price"] = (
                    "Fixed-price products cannot have max_price."
                )

        elif self.price_type == self.PriceType.ASK:
            if self.price != 0:
                errors["price"] = (
                    "Ask-for-price products must have price set to 0."
                )

            if self.mrp_price is not None:
                errors["mrp_price"] = (
                    "Ask-for-price products cannot have MRP."
                )

            if self.max_price is not None:
                errors["max_price"] = (
                    "Ask-for-price products cannot have max_price."
                )

        elif self.price_type == self.PriceType.RANGE:
            if self.price <= 0:
                errors["price"] = (
                    "Range pricing requires a starting price."
                )

            if self.max_price is None:
                errors["max_price"] = (
                    "Range pricing requires max_price."
                )

            elif self.max_price <= self.price:
                errors["max_price"] = (
                    "max_price must be greater than price."
                )

            if self.mrp_price is not None:
                errors["mrp_price"] = (
                    "Range-priced products cannot have MRP."
                )

        elif self.price_type == self.PriceType.STARTS_FROM:
            if self.price <= 0:
                errors["price"] = (
                    "Starts-from pricing requires a price greater than 0."
                )

            if self.max_price is not None:
                errors["max_price"] = (
                    "Starts-from products cannot have max_price."
                )

        if (
            self.mrp_price is not None
            and self.price_type
            in {
                self.PriceType.FIXED,
                self.PriceType.STARTS_FROM,
            }
            and self.mrp_price <= self.price
        ):
            errors["mrp_price"] = (
                "MRP must be greater than the selling price."
            )

        if errors:
            raise ValidationError(errors)

    def build_slug(self):
        suffix = f"-{self.public_id}"
        max_base_length = self._meta.get_field("slug").max_length - len(suffix)
        base = (slugify(self.name) or "item")[:max_base_length].rstrip("-")
        return f"{base}{suffix}"

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        slug = self.build_slug()
        if self.slug != slug:
            self.slug = slug
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"slug"}
        return super().save(*args, **kwargs)

        if not self.is_available:
            return False

        if not self.track_inventory:
            return True

        return self.stock_quantity > 0

    @property
    def has_discount(self):
        return (
            self.mrp_price is not None
            and self.mrp_price > self.price
            and self.price_type
            in {
                self.PriceType.FIXED,
                self.PriceType.STARTS_FROM,
            }
        )

    @property
    def discount_percentage(self):
        if not self.has_discount:
            return None

        return round(
            (
                (self.mrp_price - self.price)
                / self.mrp_price
            )
            * 100
        )

    def __str__(self):
        return self.name


class ProductImage(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_images",
    )
    upload = models.ForeignKey(
        "uploads.Upload",
        on_delete=models.CASCADE,
        related_name="product_images",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        db_table = "product_images"
        ordering = (
            "sort_order",
            "created_at",
        )
        constraints = [
            models.UniqueConstraint(
                fields=["product", "upload"],
                name="unique_product_upload_image",
            ),
        ]
        indexes = [
            models.Index(
                fields=["product", "sort_order"],
                name="prod_image_sort_idx",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.upload}"