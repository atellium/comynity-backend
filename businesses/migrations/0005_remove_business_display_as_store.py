from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0004_business_display_as_store"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="business",
            name="display_as_store",
        ),
    ]
