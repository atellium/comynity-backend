import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from businesses.models import Business
from offers.models import Offer


OFFER_NAMES = (
    "Weekend Special",
    "Customer Appreciation Deal",
    "Limited Time Discount",
    "Festival Savings",
    "New Customer Offer",
    "Buy More Save More",
    "Seasonal Special",
    "Local Shopper Deal",
    "Happy Hours Offer",
    "Exclusive Store Discount",
    "Family Savings",
    "Value Combo Offer",
)

DESCRIPTIONS = (
    "Enjoy special savings on selected products and services for a limited time.",
    "Visit the business to discover this exclusive local customer offer.",
    "Save more on your next purchase while this promotion is available.",
    "A limited-period deal created for customers in the nearby community.",
)

TERMS = (
    ["Subject to availability", "Cannot be combined with another offer"],
    ["Valid once per customer", "Please mention this offer before billing"],
    ["Available on selected items only", "Business terms apply"],
    ["Limited-period offer", "Contact the business for details"],
)

DUMMY_OFFER_NAMESPACE = uuid.UUID("cfa82235-e8e5-49ab-aa10-936a1252d886")


def validate_offer_count(count):
    if not 50 <= count <= 60:
        raise CommandError("--count must be between 50 and 60.")
    return count


class Command(BaseCommand):
    help = "Create or update 50-60 deterministic dummy offers across published businesses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=60,
            help="Number of offers to seed, from 50 to 60 (default: 60).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260902,
            help="Seed used for deterministic offer content.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = validate_offer_count(options["count"])

        businesses = list(
            Business.objects.filter(
                status=Business.Status.PUBLISHED,
                is_active=True,
            ).order_by("pk")
        )
        if not businesses:
            raise CommandError(
                "No active, published businesses exist. Seed businesses first."
            )

        generator = random.Random(options["seed"])
        now = timezone.now()
        created_count = 0

        for index in range(count):
            business = businesses[index % len(businesses)]
            cycle = index // len(OFFER_NAMES) + 1
            base_title = OFFER_NAMES[index % len(OFFER_NAMES)]
            title = f"{base_title} {cycle}"
            schedule = index % 4

            if schedule == 0:  # Currently active.
                starts_at = now - timedelta(days=generator.randint(1, 5))
                expires_at = now + timedelta(days=generator.randint(3, 14))
                is_active = True
            elif schedule == 1:  # Scheduled.
                starts_at = now + timedelta(days=generator.randint(1, 7))
                expires_at = starts_at + timedelta(days=generator.randint(5, 14))
                is_active = True
            elif schedule == 2:  # Expired.
                expires_at = now - timedelta(days=generator.randint(1, 5))
                starts_at = expires_at - timedelta(days=generator.randint(5, 14))
                is_active = True
            else:  # Administratively disabled.
                starts_at = now - timedelta(days=2)
                expires_at = now + timedelta(days=10)
                is_active = False

            offer_id = uuid.uuid5(
                DUMMY_OFFER_NAMESPACE,
                f"{business.pk}:dummy-offer:{index}",
            )
            _, created = Offer.objects.update_or_create(
                pk=offer_id,
                defaults={
                    "business": business,
                    "title": title,
                    "description": DESCRIPTIONS[index % len(DESCRIPTIONS)],
                    "starts_at": starts_at,
                    "expires_at": expires_at,
                    "is_active": is_active,
                    "sort_order": index // len(businesses),
                    "terms": TERMS[index % len(TERMS)],
                },
            )
            created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {count} dummy offers across {len(businesses)} businesses: "
                f"{created_count} created, {count - created_count} updated."
            )
        )
