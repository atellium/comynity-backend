from decimal import Decimal
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from businesses.models import Business
from catalogs.models import Catalog


PRODUCT_STYLES = (
    "Classic",
    "Premium",
    "Modern",
    "Essential",
    "Deluxe",
    "Smart",
    "Eco",
    "Compact",
    "Signature",
    "Everyday",
)

PRODUCT_NAMES = (
    "Cotton Shirt",
    "Running Shoes",
    "Wireless Earbuds",
    "Travel Backpack",
    "Wrist Watch",
    "Water Bottle",
    "Desk Lamp",
    "Phone Case",
    "Coffee Mug",
    "Notebook Set",
)


class Command(BaseCommand):
    help = "Create or update 100 dummy product catalogs for one business."

    def add_arguments(self, parser):
        parser.add_argument(
            "--business-id",
            required=True,
            help="UUID of the business that will own the catalog products.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        business = self._get_business(options["business_id"])
        created_count = 0
        updated_count = 0

        for position, (style, product_name) in enumerate(
            (
                (style, product_name)
                for style in PRODUCT_STYLES
                for product_name in PRODUCT_NAMES
            ),
            start=1,
        ):
            name = f"{style} {product_name}"
            price = Decimal(199 + ((position * 137) % 4800))
            _, created = Catalog.objects.update_or_create(
                business=business,
                type=Catalog.TypeChoices.PRODUCT,
                name=name,
                defaults={
                    "description": (
                        f"Explore the {name}, a sample product created for "
                        f"{business.name}'s catalog."
                    ),
                    "price_type": Catalog.PriceTypeChoices.FIXED,
                    "price": price,
                    "original_price": (price * Decimal("1.20")).quantize(
                        Decimal("0.01")
                    ),
                    "is_active": True,
                    "is_featured": position <= 10,
                    "sort_order": position,
                },
            )
            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded 100 product catalogs for {business.name} "
                f"({business.pk}): {created_count} created, "
                f"{updated_count} updated."
            )
        )

    def _get_business(self, raw_business_id):
        try:
            business_id = UUID(str(raw_business_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise CommandError("--business-id must be a valid UUID.") from exc

        try:
            return Business.objects.get(pk=business_id)
        except Business.DoesNotExist as exc:
            raise CommandError(
                f"Business with ID {business_id} does not exist."
            ) from exc
