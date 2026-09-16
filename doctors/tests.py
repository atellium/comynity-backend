from datetime import datetime, time
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from doctors.management.commands.import_doctor_specialties import Command
from doctors.models import Doctor, DoctorSchedule, DoctorSpecialty
from doctors.serializers import build_doctor_schedule_data
from locations.models import City, State
from businesses.models import Business
from uploads.models import Upload


class DoctorSpecialtyImageTests(TestCase):
    @staticmethod
    def image_upload(width, height, image_format="PNG"):
        content = BytesIO()
        Image.new("RGB", (width, height), "teal").save(content, format=image_format)
        return SimpleUploadedFile(
            f"specialty.{image_format.lower()}",
            content.getvalue(),
            content_type=f"image/{image_format.lower()}",
        )

    def test_specialty_image_is_compressed_without_webp_conversion(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                specialty = DoctorSpecialty.objects.create(
                    name="Cardiologist",
                    label="Cardiologists",
                    slug="cardiologist",
                    image=self.image_upload(600, 300, image_format="PNG"),
                )

                self.assertTrue(specialty.image.name.startswith("categories/"))
                self.assertTrue(specialty.image.name.endswith(".png"))

                with Image.open(specialty.image.path) as compressed:
                    self.assertEqual(compressed.format, "PNG")
                    self.assertEqual(compressed.size, (300, 150))

                self.assertTrue(Path(specialty.image.path).exists())


class DoctorModelTests(TestCase):
    def test_generates_slug_with_provider_slug_suffix(self):
        state = State.objects.create(
            name="West Bengal",
            slug="west-bengal",
            code="WB",
        )
        city = City.objects.create(
            name="Kolkata",
            slug="kolkata",
            state=state,
        )
        provider = Business.objects.create(
            name="CarePlus Clinic",
            locality="Garia",
            city=city,
            address="1 Demo Road",
        )

        doctor = Doctor.objects.create(
            business=provider,
            name="Dr. Ananya Sen",
        )

        self.assertEqual(doctor.slug, f"dr-ananya-sen-at-{provider.slug}")


class ImportDoctorSpecialtiesCommandTests(TestCase):
    def test_validates_doctor_specialty_item(self):
        seen_slugs = set()

        specialty = Command._validate_item(
            {
                "name": "Cardiologist",
                "label": "Cardiologists",
                "slug": "cardiologists",
                "aliases": "heart doctor, heart specialist",
                "body_part": "heart",
                "sort_order": 10,
                "is_active": True,
                "is_featured": False,
            },
            1,
            seen_slugs,
        )

        self.assertEqual(specialty["slug"], "cardiologists")
        self.assertEqual(specialty["body_part"], "heart")
        self.assertEqual(specialty["sort_order"], 10)

    def test_rejects_unknown_body_part(self):
        with self.assertRaises(CommandError):
            Command._validate_item(
                {
                    "name": "Cardiologist",
                    "label": "Cardiologists",
                    "slug": "cardiologists",
                    "body_part": "unknown",
                },
                1,
                set(),
            )


class DoctorListEndpointTests(APITestCase):
    def setUp(self):
        self.state = State.objects.create(
            name="West Bengal",
            slug="west-bengal",
            code="WB",
        )
        self.city = City.objects.create(
            name="Kolkata",
            slug="kolkata",
            state=self.state,
        )
        self.provider = Business.objects.create(
            name="CarePlus Clinic",
            locality="Garia",
            city=self.city,
            address="1 Demo Road",
            phone="9800000001",
            location=Point(88.40233304308231, 22.467778888332326, srid=4326),
            is_verified=True,
        )
        self.specialty = DoctorSpecialty.objects.create(
            name="Cardiologist",
            label="Cardiologists",
            slug="cardiologists",
        )

    def test_lists_doctor_specialties(self):
        DoctorSpecialty.objects.create(
            name="Dermatologist",
            label="Dermatologists",
            slug="dermatologists",
            aliases="skin doctor",
            body_part=DoctorSpecialty.BodyPartChoices.SKIN,
            sort_order=1,
            is_featured=True,
        )
        DoctorSpecialty.objects.create(
            name="Inactive Specialty",
            label="Inactive Specialties",
            slug="inactive-specialties",
            is_active=False,
        )

        response = self.client.get(reverse("doctors:doctor-specialty-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 2)
        self.assertEqual(
            [specialty["slug"] for specialty in data["results"]],
            ["cardiologists", "dermatologists"],
        )
        self.assertEqual(
            set(data["results"][0]),
            {
                "id",
                "name",
                "label",
                "slug",
                "aliases",
                "body_part",
                "image",
                "sort_order",
                "is_active",
                "is_featured",
            },
        )

    def test_filters_doctor_specialties_with_query_parameters(self):
        DoctorSpecialty.objects.create(
            name="Dermatologist",
            label="Dermatologists",
            slug="dermatologists",
            aliases="skin doctor",
            body_part=DoctorSpecialty.BodyPartChoices.SKIN,
            is_featured=True,
        )
        DoctorSpecialty.objects.create(
            name="Neurologist",
            label="Neurologists",
            slug="neurologists",
            aliases="brain doctor",
            body_part=DoctorSpecialty.BodyPartChoices.BRAIN_NERVOUS_SYSTEM,
            is_featured=True,
        )

        response = self.client.get(
            reverse("doctors:doctor-specialty-list"),
            {
                "search": "skin",
                "body_part": DoctorSpecialty.BodyPartChoices.SKIN,
                "is_featured": "true",
                "page_size": "1",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertEqual(data["results"][0]["slug"], "dermatologists")

    def test_doctor_specialty_list_rejects_unknown_query_parameter(self):
        response = self.client.get(
            reverse("doctors:doctor-specialty-list"),
            {"unknown": "true"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lists_nearby_doctors_with_provider_general_information(self):
        self.provider.cover_image = Upload.objects.create(
            object_key="uploads/businesses/cover.webp",
            mime_type="image/webp",
            status=Upload.Status.READY,
        )
        self.provider.save()
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Ananya Sen",
            qualification="MBBS, MD",
            consultation_fee="500.00",
        )
        doctor.specialties.set([self.specialty])
        DoctorSchedule.objects.create(
            doctor=doctor,
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )

        response = self.client.get(
            reverse("doctors:doctor-list"),
            {
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "specialty": self.specialty.slug,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertEqual(data["specialty"]["slug"], "cardiologists")
        self.assertEqual(data["results"][0]["name"], "Dr. Ananya Sen")
        self.assertEqual(data["results"][0]["specialties"][0]["slug"], "cardiologists")
        self.assertEqual(data["results"][0]["business"]["name"], "CarePlus Clinic")
        self.assertEqual(data["results"][0]["business"]["distance_km"], 0)
        self.assertEqual(
            set(data["results"][0]["business"]),
            {
                "id",
                "name",
                "slug",
                "distance_km",
                "is_verified",
                "cover_image",
                "contact",
                "address",
                "city",
            },
        )
        self.assertEqual(
            data["results"][0]["business"]["contact"]["phone"],
            "+919800000001",
        )
        self.assertTrue(
            data["results"][0]["business"]["cover_image"].endswith(
                "/media/uploads/businesses/cover.webp"
            )
        )
        self.assertIn("is_available", data["results"][0]["schedule"])
        self.assertIn("next_available", data["results"][0]["schedule"])
        self.assertIn("full_schedule", data["results"][0]["schedule"])

    def test_rejects_unknown_query_parameter(self):
        response = self.client.get(
            reverse("doctors:doctor-list"),
            {
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "specialty": self.specialty.slug,
                "unknown": "true",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filters_doctors_available_today_with_future_time(self):
        available_doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Available Today",
        )
        available_doctor.specialties.set([self.specialty])
        DoctorSchedule.objects.create(
            doctor=available_doctor,
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(11, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )

        tomorrow_doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Available Tomorrow",
        )
        tomorrow_doctor.specialties.set([self.specialty])
        DoctorSchedule.objects.create(
            doctor=tomorrow_doctor,
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.THURSDAY,
            start_time=time(11, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )

        with patch(
            "doctors.services.timezone.localtime",
            return_value=_kolkata_datetime(2026, 9, 9, 10, 0),
        ):
            response = self.client.get(
                reverse("doctors:doctor-list"),
                {
                    "lat": "22.467778888332326",
                    "lng": "88.40233304308231",
                    "specialty": self.specialty.slug,
                    "available_today": "true",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Dr. Available Today")

    def test_returns_404_for_unknown_specialty(self):
        response = self.client.get(
            reverse("doctors:doctor-list"),
            {
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "specialty": "unknown",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_doctor_detail_by_slug(self):
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Ananya Sen",
            qualification="MBBS, MD",
            consultation_fee="500.00",
        )
        doctor.specialties.set([self.specialty])
        DoctorSchedule.objects.create(
            doctor=doctor,
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )

        response = self.client.get(
            reverse("doctors:doctor-detail", kwargs={"slug": doctor.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["slug"], doctor.slug)
        self.assertEqual(data["name"], "Dr. Ananya Sen")
        self.assertEqual(data["business"]["name"], "CarePlus Clinic")
        self.assertEqual(data["specialties"][0]["slug"], "cardiologists")
        self.assertIn("schedule", data)
        self.assertIn("full_schedule", data["schedule"])

    def test_doctor_detail_ignores_inactive_doctor(self):
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Inactive Sen",
            is_active=False,
        )

        response = self.client.get(
            reverse("doctors:doctor-detail", kwargs={"slug": doctor.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_lists_public_doctors_for_provider(self):
        active_doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Active Sen",
            qualification="MBBS, MD",
        )
        active_doctor.specialties.set([self.specialty])
        DoctorSchedule.objects.create(
            doctor=active_doctor,
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )
        Doctor.objects.create(
            business=self.provider,
            name="Dr. Inactive Sen",
            is_active=False,
        )

        response = self.client.get(
            reverse(
                "doctors:business-doctor-list",
                kwargs={"business_slug": self.provider.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertEqual(data["business"]["id"], str(self.provider.id))
        self.assertEqual(data["business"]["slug"], self.provider.slug)
        self.assertEqual(data["results"][0]["name"], "Dr. Active Sen")
        self.assertEqual(data["results"][0]["business"]["slug"], self.provider.slug)
        self.assertEqual(
            data["results"][0]["schedule"]["full_schedule"][0]["schedule_label"],
            "Every Wednesday",
        )

    def test_provider_doctor_list_rejects_unknown_query_parameter(self):
        response = self.client.get(
            reverse(
                "doctors:business-doctor-list",
                kwargs={"business_slug": self.provider.slug},
            ),
            {"lat": "22.467778888332326"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_provider_doctor_list_ignores_inactive_provider(self):
        self.provider.is_active = False
        self.provider.save()

        response = self.client.get(
            reverse(
                "doctors:business-doctor-list",
                kwargs={"business_slug": self.provider.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_adds_doctor_for_owned_provider(self):
        user = User.objects.create_user(phone="+919876543210")
        self.provider.owner = user
        self.provider.save()

        self.client.force_authenticate(user)
        response = self.client.post(
            reverse(
                "doctors:my-business-doctor-list",
                kwargs={"business_id": self.provider.id},
            ),
            {
                "name": "Dr. New Doctor",
                "specialty_ids": [self.specialty.id],
                "qualification": "MBBS",
                "registration_number": "WB-123",
                "consultation_fee": "700.00",
                "gender": Doctor.GenderChoices.FEMALE,
                "bio": "General physician.",
                "languages": ["English", "Bengali"],
                "treatments": ["Consultation"],
                "schedules": [
                    {
                        "schedule_type": DoctorSchedule.ScheduleType.WEEKLY,
                        "weekday": DoctorSchedule.Weekday.WEDNESDAY,
                        "start_time": "09:00:00",
                        "end_time": "12:00:00",
                        "consultation_type": (
                            DoctorSchedule.ConsultationType.BY_APPOINTMENT
                        ),
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["name"], "Dr. New Doctor")
        self.assertEqual(data["business"]["id"], str(self.provider.id))
        self.assertEqual(data["specialties"][0]["slug"], "cardiologists")
        self.assertEqual(data["consultation_fee"], "700.00")
        self.assertEqual(
            data["schedule"]["full_schedule"][0]["schedule_label"],
            "Every Wednesday",
        )
        self.assertEqual(
            data["schedule"]["full_schedule"][0]["consultation_type"],
            DoctorSchedule.ConsultationType.BY_APPOINTMENT,
        )

        doctor = Doctor.objects.get(name="Dr. New Doctor")
        self.assertEqual(doctor.business, self.provider)
        self.assertEqual(doctor.specialties.get(), self.specialty)
        self.assertEqual(doctor.schedules.count(), 1)

    def test_cannot_add_doctor_for_provider_owned_by_another_user(self):
        user = User.objects.create_user(phone="+919876543210")
        other_user = User.objects.create_user(phone="+919876543211")
        self.provider.owner = other_user
        self.provider.save()

        self.client.force_authenticate(user)
        response = self.client.post(
            reverse(
                "doctors:my-business-doctor-list",
                kwargs={"business_id": self.provider.id},
            ),
            {"name": "Dr. Blocked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Doctor.objects.filter(name="Dr. Blocked").exists())

    def test_add_doctor_requires_name_qualification_and_specialties(self):
        user = User.objects.create_user(phone="+919876543210")
        self.provider.owner = user
        self.provider.save()

        self.client.force_authenticate(user)
        response = self.client.post(
            reverse(
                "doctors:my-business-doctor-list",
                kwargs={"business_id": self.provider.id},
            ),
            {"name": "Dr. Missing Fields"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("qualification", response.json())
        self.assertIn("specialty_ids", response.json())

    def test_updates_doctor_for_owned_provider(self):
        user = User.objects.create_user(phone="+919876543210")
        self.provider.owner = user
        self.provider.save()
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Old Name",
            qualification="MBBS",
        )
        DoctorSchedule.objects.create(
            doctor=doctor,
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.MONDAY,
            start_time=time(10, 0),
            end_time=time(11, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )

        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse(
                "doctors:my-business-doctor-detail",
                kwargs={
                    "business_id": self.provider.id,
                    "doctor_id": doctor.id,
                },
            ),
            {
                "name": "Dr. Updated Name",
                "specialty_ids": [self.specialty.id],
                "qualification": "MBBS, MD",
                "languages": ["Hindi"],
                "is_active": False,
                "schedules": [
                    {
                        "schedule_type": DoctorSchedule.ScheduleType.MONTHLY_DATE,
                        "day_of_month": 15,
                        "start_time": "13:00:00",
                        "end_time": "15:00:00",
                        "consultation_type": DoctorSchedule.ConsultationType.WALK_IN,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["name"], "Dr. Updated Name")
        self.assertEqual(data["qualification"], "MBBS, MD")
        self.assertEqual(data["languages"], ["Hindi"])
        self.assertFalse(data["is_active"])
        self.assertEqual(data["specialties"][0]["id"], self.specialty.id)
        self.assertEqual(
            data["schedule"]["full_schedule"][0]["schedule_label"],
            "15th Date of every month",
        )

        doctor.refresh_from_db()
        self.assertEqual(doctor.name, "Dr. Updated Name")
        self.assertEqual(doctor.specialties.get(), self.specialty)
        schedule = doctor.schedules.get()
        self.assertEqual(schedule.schedule_type, DoctorSchedule.ScheduleType.MONTHLY_DATE)
        self.assertEqual(schedule.day_of_month, 15)

    def test_cannot_update_doctor_for_provider_owned_by_another_user(self):
        user = User.objects.create_user(phone="+919876543210")
        other_user = User.objects.create_user(phone="+919876543211")
        self.provider.owner = other_user
        self.provider.save()
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Other Provider",
        )

        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse(
                "doctors:my-business-doctor-detail",
                kwargs={
                    "business_id": self.provider.id,
                    "doctor_id": doctor.id,
                },
            ),
            {"name": "Dr. Should Not Update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        doctor.refresh_from_db()
        self.assertEqual(doctor.name, "Dr. Other Provider")

    def test_deletes_doctor_for_owned_provider(self):
        user = User.objects.create_user(phone="+919876543210")
        self.provider.owner = user
        self.provider.save()
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Delete Me",
        )

        self.client.force_authenticate(user)
        response = self.client.delete(
            reverse(
                "doctors:my-business-doctor-detail",
                kwargs={
                    "business_id": self.provider.id,
                    "doctor_id": doctor.id,
                },
            )
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Doctor.objects.filter(pk=doctor.pk).exists())

    def test_cannot_delete_doctor_for_provider_owned_by_another_user(self):
        user = User.objects.create_user(phone="+919876543210")
        other_user = User.objects.create_user(phone="+919876543211")
        self.provider.owner = other_user
        self.provider.save()
        doctor = Doctor.objects.create(
            business=self.provider,
            name="Dr. Keep Me",
        )

        self.client.force_authenticate(user)
        response = self.client.delete(
            reverse(
                "doctors:my-business-doctor-detail",
                kwargs={
                    "business_id": self.provider.id,
                    "doctor_id": doctor.id,
                },
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Doctor.objects.filter(pk=doctor.pk).exists())


class DoctorScheduleSerializerTests(TestCase):
    def test_monthly_date_schedule_label_uses_ordinal_monthly_text(self):
        schedule = DoctorSchedule(
            schedule_type=DoctorSchedule.ScheduleType.MONTHLY_DATE,
            day_of_month=16,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
        )

        self.assertEqual(schedule.schedule_label, "16th Date of every month")

    def test_returns_available_schedule_data_for_current_slot(self):
        schedule = DoctorSchedule(
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
            is_active=True,
        )

        data = build_doctor_schedule_data(
            [schedule],
            now=_kolkata_datetime(2026, 9, 9, 10, 0),
        )

        self.assertTrue(data["is_available"])
        self.assertEqual(data["next_available"], "Available today, 9 AM - 12 PM")
        self.assertEqual(data["full_schedule"][0]["schedule_label"], "Every Wednesday")
        self.assertEqual(data["full_schedule"][0]["start_time"], "09:00:00")
        self.assertEqual(data["full_schedule"][0]["end_time"], "12:00:00")
        self.assertTrue(data["is_today"])
        self.assertNotIn("is_today", data["full_schedule"][0])

    def test_returns_next_available_schedule_data(self):
        schedule = DoctorSchedule(
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.THURSDAY,
            start_time=time(15, 0),
            end_time=time(18, 0),
            consultation_type=DoctorSchedule.ConsultationType.BY_APPOINTMENT,
            is_active=True,
        )

        data = build_doctor_schedule_data(
            [schedule],
            now=_kolkata_datetime(2026, 9, 9, 18, 0),
        )

        self.assertFalse(data["is_available"])
        self.assertEqual(
            data["next_available"],
            "Available tomorrow, 3 PM - 6 PM (By Appointment)",
        )
        self.assertFalse(data["is_today"])
        self.assertNotIn("is_today", data["full_schedule"][0])

    def test_returns_by_appointment_text_for_current_appointment_slot(self):
        schedule = DoctorSchedule(
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.BY_APPOINTMENT,
            is_active=True,
        )

        data = build_doctor_schedule_data(
            [schedule],
            now=_kolkata_datetime(2026, 9, 9, 10, 0),
        )

        self.assertTrue(data["is_available"])
        self.assertEqual(
            data["next_available"],
            "Available today, 9 AM - 12 PM (By Appointment)",
        )

    def test_returns_no_next_available_when_no_active_schedule_exists(self):
        schedule = DoctorSchedule(
            schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
            weekday=DoctorSchedule.Weekday.WEDNESDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
            consultation_type=DoctorSchedule.ConsultationType.WALK_IN,
            is_active=False,
        )

        data = build_doctor_schedule_data(
            [schedule],
            now=_kolkata_datetime(2026, 9, 9, 10, 0),
        )

        self.assertFalse(data["is_available"])
        self.assertEqual(data["next_available"], "")
        self.assertFalse(data["is_today"])
        self.assertEqual(data["full_schedule"], [])


def _kolkata_datetime(year, month, day, hour, minute):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )


