from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("businesses", "0009_widen_direct_upload_paths")]

    operations = [
        migrations.AddField(
            model_name="business",
            name="offerings",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
