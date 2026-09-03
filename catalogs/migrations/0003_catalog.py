import uuid

import catalogs.models
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0005_remove_business_display_as_store"),
        ("catalogs", "0002_alter_catalogcategory_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="Catalog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "public_id",
                    models.CharField(
                        default=catalogs.models.generate_catalog_public_id,
                        editable=False,
                        max_length=8,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message=(
                                    "Public ID must contain exactly 8 "
                                    "alphanumeric characters."
                                ),
                                regex="^[a-z0-9]{8}$",
                            )
                        ],
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("product", "Product"),
                            ("service", "Service"),
                            ("doctor", "Doctor"),
                            ("property", "Property"),
                            ("menu", "Menu"),
                            ("package", "Package"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="product",
                        max_length=20,
                    ),
                ),
                ("name", models.CharField(db_index=True, max_length=200)),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        db_index=True,
                        max_length=200,
                        null=True,
                        unique=True,
                    ),
                ),
                ("short_description", models.CharField(blank=True, max_length=300)),
                ("description", models.TextField(blank=True)),
                (
                    "price_type",
                    models.CharField(
                        choices=[
                            ("fixed", "Fixed"),
                            ("starts_from", "Starts From"),
                            ("range", "Range"),
                            ("ask", "Ask for Price"),
                            ("free", "Free"),
                        ],
                        default="fixed",
                        max_length=20,
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "max_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Used only when price_type is range.",
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "original_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Optional MRP/original price for display.",
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "variants",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            "Display-only variant options such as size, color, "
                            "weight or volume."
                        ),
                    ),
                ),
                (
                    "specifications",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            "Structured type-specific data controlled by the application."
                        ),
                    ),
                ),
                (
                    "custom_fields",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="User-defined title/value information for display.",
                    ),
                ),
                ("is_featured", models.BooleanField(db_index=True, default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=0)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="catalog_items",
                        to="businesses.business",
                    ),
                ),
                (
                    "categories",
                    models.ManyToManyField(
                        blank=True,
                        related_name="catalog_items",
                        to="catalogs.catalogcategory",
                    ),
                ),
            ],
            options={
                "ordering": ("sort_order", "-created_at"),
                "indexes": [
                    models.Index(
                        fields=["business", "type", "is_active"],
                        name="catalog_business_type_idx",
                    ),
                    models.Index(
                        fields=["business", "is_featured", "is_active"],
                        name="catalog_featured_idx",
                    ),
                    models.Index(
                        fields=["type", "is_active"],
                        name="catalog_type_active_idx",
                    ),
                ],
            },
        ),
    ]
