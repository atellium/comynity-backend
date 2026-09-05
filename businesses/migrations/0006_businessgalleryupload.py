import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("businesses", "0005_remove_business_display_as_store")]

    operations = [
        migrations.CreateModel(
            name="BusinessGalleryUpload",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_key", models.CharField(max_length=500, unique=True)),
                ("content_type", models.CharField(max_length=32)),
                ("status", models.CharField(choices=[("pending", "Pending upload"), ("processing", "Processing"), ("ready", "Ready"), ("failed", "Failed")], default="pending", max_length=12)),
                ("error", models.CharField(blank=True, default="", max_length=500)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gallery_uploads", to="businesses.business")),
                ("gallery_image", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="upload", to="businesses.businessgalleryimage")),
            ],
            options={"db_table": "business_gallery_uploads"},
        ),
    ]
