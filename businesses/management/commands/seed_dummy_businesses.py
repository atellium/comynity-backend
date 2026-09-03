import math
import random
from datetime import time

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from businesses.models import Business, BusinessCategoryAssignment, BusinessHour, BusinessProfile
from categories.models import BusinessCategory
from locations.models import City


CENTER_LATITUDE = 22.467324
CENTER_LONGITUDE = 88.403916
RADIUS_KM = 10.0

LOCALITIES = (
    ("Narendrapur", "NSC Bose Road", "700103"), ("Rajpur", "Rajpur Main Road", "700149"),
    ("Sonarpur", "Sonarpur Station Road", "700150"), ("Garia", "Raja SC Mullick Road", "700084"),
    ("Kamalgazi", "Kamalgazi Bypass Road", "700103"), ("Harinavi", "Harinavi Main Road", "700148"),
    ("Subhasgram", "Subhasgram Station Road", "700147"), ("Kodalia", "Kodalia Road", "700146"),
    ("Boral", "Boral Main Road", "700154"), ("Mahamayatala", "Mahamayatala Road", "700084"),
    ("Baruipur", "Kulpi Road", "700144"), ("Champahati", "Champahati Main Road", "743330"),
    ("Mallikpur", "Mallikpur Station Road", "700145"), ("Naktala", "NSC Bose Road", "700047"),
    ("Patuli", "Baishnabghata Patuli Road", "700094"), ("Bansdroni", "Netaji Subhash Chandra Bose Road", "700070"),
    ("Kamdahari", "Kamdahari Road", "700084"), ("Tentultala", "Tentultala Road", "700152"),
    ("Gobindapur", "Gobindapur Road", "700145"), ("Langalberia", "Langalberia Road", "700145"),
)

BUSINESS_NAMES = (
    "Saha Medical Hall", "Maa Tara Pharmacy", "New Life Diagnostic Centre", "Annapurna Grocery",
    "Bengal Sweet House", "Friends Electronics", "Sen Hardware Stores", "Das Auto Centre",
    "Mitali Beauty Parlour", "Green Leaf Nursery", "Roy Dental Clinic", "Care Physiotherapy Centre",
    "Asha Opticals", "City Mobile Care", "Bharat Furniture House", "Apanjan Restaurant",
    "Royal Biryani House", "Fresh Basket", "Ghosh Variety Stores", "Modern Tailors",
    "Lakshmi Book House", "Star Computer Centre", "Paul Electricals", "Maa Kali Bastralaya",
    "New Bengal Bakery", "Health Point Clinic", "Life Care Pathology", "Sree Guru Jewellers",
    "Eastern Travel Agency", "Dream Home Decor", "Classic Hair Studio", "Sunrise Coaching Centre",
    "Little Flower Preschool", "Bose Refrigeration", "Mondal Sanitary House", "Galaxy Gift Corner",
    "Rupasi Boutique", "South City Fitness", "Wellness Yoga Studio", "Kitchen Queen Caterers",
    "Petals Flower Shop", "Aarogya Homeo Clinic", "Netaji Cycle Stores", "Popular Shoe House",
    "New India Stationery", "Mitra Paints and Hardware", "Blue Sky Xerox Centre", "Calcutta Tea Corner",
    "Spice Garden Restaurant", "Family Salon", "Secure Vision CCTV", "Quick Fix Appliance Care",
    "Mother's Kitchen", "Golden Spoon Caterers", "Sundarban Fish Centre", "Daily Needs Store",
    "Ideal Motor Training School", "Bright Future Academy", "Creative Art School", "Melody Music Academy",
    "Shanti Nursing Home", "Relief Medical Centre", "Smile Dental Care", "Vision Eye Care",
    "Maa Sarada Surgical", "Eastern Pest Control", "Clean Home Services", "Reliable Packers and Movers",
    "Fast Track Courier", "Digital Seva Kendra", "Smart Choice Mobile", "Computer World",
    "Elegant Furniture", "Home Comfort Furnishings", "Marble Palace", "Ganapati Electrical House",
    "New Town Plumbing Services", "Aqua Pure Water", "Fresh Chicken Centre", "Organic Food Corner",
    "Bengal Dairy", "Krishna Mistanna Bhandar", "Tea Junction", "Cafe Adda",
    "Tandoor House", "Chinese Wok", "South Indian Corner", "Royal Decorators",
    "Subham Event Management", "Moments Photography", "Wedding Bells Boutique", "Kids Corner",
    "Sports World", "Fitness Zone", "Care Vet Clinic", "Happy Paws Pet Shop",
    "Nature Cure Wellness", "Ayush Ayurveda", "Puja Stores", "Biswas Enterprise",
)

HOUR_PATTERNS = (
    ((0, 1, 2, 3, 4, 5), time(9), time(20)),
    ((0, 1, 2, 3, 4, 5, 6), time(10), time(21)),
    ((0, 1, 2, 3, 4), time(9), time(18)),
    ((1, 2, 3, 4, 5, 6), time(11), time(22)),
)


def point_within_radius(generator):
    # Keep a small buffer for ellipsoid/projection differences in distance checks.
    distance = (RADIUS_KM * 0.99) * math.sqrt(generator.random())
    bearing = generator.uniform(0, 2 * math.pi)
    latitude = CENTER_LATITUDE + distance * math.cos(bearing) / 111.32
    longitude = CENTER_LONGITUDE + distance * math.sin(bearing) / (
        111.32 * math.cos(math.radians(CENTER_LATITUDE))
    )
    return Point(longitude, latitude, srid=4326)


class Command(BaseCommand):
    help = "Seed 100 realistic businesses with profiles, category 1, hours, and nearby coordinates."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=20260829)
        parser.add_argument("--city-id", type=int, help="Defaults to the city with slug 'kolkata'.")

    @transaction.atomic
    def handle(self, *args, **options):
        category = BusinessCategory.objects.filter(pk=1).first()
        if category is None:
            raise CommandError("Business category ID 1 does not exist.")

        city_query = City.objects.filter(pk=options["city_id"]) if options["city_id"] else City.objects.filter(slug="kolkata")
        city = city_query.first()
        if city is None:
            error = f"City ID {options['city_id']} does not exist." if options["city_id"] else "A city with slug 'kolkata' does not exist; pass --city-id."
            raise CommandError(error)

        generator = random.Random(options["seed"])
        created_count = 0
        published_at = timezone.now()

        for index, name in enumerate(BUSINESS_NAMES):
            locality, road, postal_code = LOCALITIES[index % len(LOCALITIES)]
            base_slug = slugify(name)
            locality_slug = slugify(locality)
            slug = f"{base_slug}-{locality_slug}"
            phone = f"+91{7000000000 + index}"

            business, created = Business.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "handle": f"{base_slug[:38]}-{locality_slug[:10]}"[:50],
                    "established_year": 1985 + index % 40,
                    "address": f"{12 + (index * 17) % 219}, {road}",
                    "landmark": f"Near {locality} Market",
                    "locality": locality,
                    "city": city,
                    "postal_code": postal_code,
                    "location": point_within_radius(generator),
                    "phone": phone,
                    "whatsapp": phone,
                    "email": f"{base_slug.replace('-', '.')}@example.com",
                    "status": Business.Status.PUBLISHED,
                    "is_active": True,
                    "is_verified": index % 4 == 0,
                    "published_at": published_at,
                },
            )
            created_count += int(created)

            business.category_assignments.exclude(category=category).delete()
            BusinessCategoryAssignment.objects.update_or_create(
                business=business, category=category, defaults={"sort_order": 0}
            )
            BusinessProfile.objects.update_or_create(
                business=business,
                defaults={
                    "description": f"{name} serves customers in {locality} and nearby areas with dependable local service.",
                    "alternate_numbers": [],
                    "social_urls": {},
                    "seo_title": f"{name} in {locality}",
                    "seo_description": f"Contact details, address, and opening hours for {name}, {locality}.",
                    "seo_keywords": f"{name}, {locality}, local business",
                },
            )
            days, opens_at, closes_at = HOUR_PATTERNS[index % len(HOUR_PATTERNS)]
            business.business_hours.all().delete()
            BusinessHour.objects.create(
                business=business, days=list(days), opens_at=opens_at, closes_at=closes_at
            )

        updated_count = len(BUSINESS_NAMES) - created_count
        self.stdout.write(self.style.SUCCESS(
            f"Seeded 100 businesses: {created_count} created, {updated_count} updated; "
            "profiles, category 1, hours, and coordinates applied."
        ))
