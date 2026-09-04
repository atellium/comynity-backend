from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("businesses", "0006_businessgalleryupload")]
    operations = [
        migrations.AddField(model_name="businessgalleryupload", name="kind", field=models.CharField(choices=[("gallery", "Business gallery"), ("thumbnail", "Business thumbnail"), ("offer", "Offer image")], default="gallery", max_length=12)),
        migrations.AddField(model_name="businessgalleryupload", name="target_id", field=models.UUIDField(blank=True, null=True)),
    ]
