from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0003_alter_business_handle"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="display_as_store",
            field=models.BooleanField(
                default=False,
                help_text="Show profile as a store on the website.",
            ),
        ),
    ]
