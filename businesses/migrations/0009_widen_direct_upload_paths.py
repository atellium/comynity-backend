import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("businesses", "0008_businessprofile_services")]

    operations = [
        migrations.AlterField(
            model_name="businessgalleryimage",
            name="image",
            field=models.ImageField(
                max_length=500,
                upload_to="businesses/gallery/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["jpg", "jpeg", "png", "webp"]
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="businessgalleryupload",
            name="object_key",
            field=models.CharField(max_length=500, unique=True),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE business_gallery_images "
                "ALTER COLUMN image TYPE varchar(500); "
                "ALTER TABLE business_gallery_uploads "
                "ALTER COLUMN object_key TYPE varchar(500);"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
