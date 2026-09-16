import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from doctors.models import Doctor, DoctorSpecialty
from businesses.models import Business


DEFAULT_SEED = 20260909
DEFAULT_COUNT = 60

DOCTOR_NAMES = [
    "Dr. Ananya Sen",
    "Dr. Arjun Roy",
    "Dr. Priya Mukherjee",
    "Dr. Rohan Das",
    "Dr. Ishita Ghosh",
    "Dr. Vikram Chatterjee",
    "Dr. Neha Agarwal",
    "Dr. Sayan Dutta",
    "Dr. Mitali Banerjee",
    "Dr. Kunal Bose",
    "Dr. Riya Saha",
    "Dr. Abhishek Paul",
    "Dr. Sneha Kapoor",
    "Dr. Rajiv Nandi",
    "Dr. Poulomi Chakraborty",
    "Dr. Aritra Basu",
    "Dr. Tanaya Dey",
    "Dr. Sourav Mitra",
    "Dr. Nandini Lahiri",
    "Dr. Debjit Sarkar",
]

QUALIFICATIONS = [
    "MBBS",
    "MBBS, MD",
    "MBBS, MS",
    "MBBS, DNB",
    "BDS, MDS",
    "MBBS, Diploma in Child Health",
    "MBBS, MD Dermatology",
]

LANGUAGE_SETS = [
    ["English", "Hindi", "Bengali"],
    ["English", "Bengali"],
    ["Hindi", "Bengali"],
    ["English", "Hindi"],
]

TREATMENT_SETS = [
    ["general consultation", "preventive care", "follow-up care"],
    ["fever treatment", "infection care", "health checkup"],
    ["diabetes care", "hypertension care", "lifestyle counselling"],
    ["skin consultation", "allergy care", "minor procedures"],
    ["child consultation", "vaccination", "growth monitoring"],
    ["dental consultation", "scaling", "root canal"],
]


class Command(BaseCommand):
    help = "Create repeatable dummy doctors across existing businesses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help="Number of dummy doctors to create or update.",
        )
        parser.add_argument(
            "--business-limit",
            "--provider-limit",
            type=int,
            default=None,
            dest="business_limit",
            help="Maximum number of active businesses to use.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help="Random seed for repeatable doctor data.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        business_limit = options["business_limit"]
        if count < 1:
            raise CommandError("count must be at least 1.")
        if business_limit is not None and business_limit < 1:
            raise CommandError("business-limit must be at least 1.")

        businesses = list(
            Business.objects.filter(is_active=True).order_by("name", "id")[
                :business_limit
            ]
        )
        if not businesses:
            raise CommandError("No active businesses found. Seed businesses first.")

        specialties = list(
            DoctorSpecialty.objects.filter(is_active=True).order_by(
                "sort_order",
                "name",
            )
        )

        rng = random.Random(options["seed"])
        created_count = 0
        updated_count = 0

        for index in range(count):
            business = businesses[index % len(businesses)]
            name = _doctor_name(index)
            defaults = _doctor_defaults(index, rng)
            doctor, created = Doctor.objects.update_or_create(
                business=business,
                name=name,
                defaults=defaults,
            )
            if specialties:
                doctor.specialties.set(_specialties_for_index(specialties, index, rng))

            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {count} dummy doctors across {len(businesses)} businesses: "
                f"{created_count} created, {updated_count} updated."
            )
        )


def _doctor_name(index):
    if index < len(DOCTOR_NAMES):
        return DOCTOR_NAMES[index]
    return f"Dr. MedNearby Demo {index + 1}"


def _doctor_defaults(index, rng):
    gender_values = [
        Doctor.GenderChoices.MALE,
        Doctor.GenderChoices.FEMALE,
        Doctor.GenderChoices.OTHER,
    ]
    fee = Decimal(rng.choice([300, 400, 500, 600, 700, 800, 1000]))

    return {
        "qualification": rng.choice(QUALIFICATIONS),
        "registration_number": f"WBMC-DUMMY-{index + 1:05d}",
        "registration_council": "West Bengal Medical Council",
        "registration_year": 2000 + (index % 25),
        "consultation_fee": fee,
        "gender": gender_values[index % len(gender_values)],
        "bio": (
            f"Dummy doctor profile for local testing with "
            f"{5 + (index % 20)} years of practice experience."
        ),
        "languages": rng.choice(LANGUAGE_SETS),
        "treatments": rng.choice(TREATMENT_SETS),
        "is_active": True,
        "is_featured": index < 10,
    }


def _specialties_for_index(specialties, index, rng):
    primary = specialties[index % len(specialties)]
    if len(specialties) == 1 or rng.random() >= 0.35:
        return [primary]

    secondary = specialties[(index + rng.randint(1, len(specialties) - 1)) % len(specialties)]
    return [primary, secondary]
