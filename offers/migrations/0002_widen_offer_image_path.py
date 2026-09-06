from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("offers", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="offer",
            name="image",
            field=models.ImageField(
                blank=True,
                max_length=500,
                null=True,
                upload_to="offers/",
            ),
        ),
        migrations.RunSQL(
            sql="ALTER TABLE offers ALTER COLUMN image TYPE varchar(500);",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
