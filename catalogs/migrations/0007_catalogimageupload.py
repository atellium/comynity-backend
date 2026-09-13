import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0006_catalogcategory_is_display")]
    operations = [
        migrations.CreateModel(
            name="CatalogImageUpload",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_key", models.CharField(max_length=500, unique=True)),
                ("content_type", models.CharField(max_length=32)),
                ("status", models.CharField(choices=[("pending", "Pending upload"), ("processing", "Processing"), ("ready", "Ready"), ("failed", "Failed")], default="pending", max_length=12)),
                ("error", models.CharField(blank=True, default="", max_length=500)),
                ("catalog", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="image_uploads", to="catalogs.catalog")),
                ("catalog_image", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="upload", to="catalogs.catalogimage")),
            ],
            options={"db_table": "catalog_image_uploads"},
        )
    ]
