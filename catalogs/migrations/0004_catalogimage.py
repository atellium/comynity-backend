import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0003_catalog"),
    ]

    operations = [
        migrations.CreateModel(
            name="CatalogImage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "image",
                    models.ImageField(
                        upload_to="catalog/items/",
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                ["jpg", "jpeg", "png", "webp"]
                            )
                        ],
                    ),
                ),
                ("alt_text", models.CharField(blank=True, max_length=200)),
                (
                    "is_primary",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text=(
                            "Primary/default image shown for the catalog item."
                        ),
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=0)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "catalog",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="catalogs.catalog",
                    ),
                ),
            ],
            options={
                "db_table": "catalogimages",
                "ordering": ("sort_order", "created_at"),
                "indexes": [
                    models.Index(
                        fields=["catalog", "is_active", "sort_order"],
                        name="catalog_img_active_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_primary", True)),
                        fields=("catalog",),
                        name="unique_primary_catalog_image",
                    )
                ],
            },
        ),
    ]
