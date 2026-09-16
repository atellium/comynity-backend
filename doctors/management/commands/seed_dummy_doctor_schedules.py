from datetime import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from doctors.models import Doctor, DoctorSchedule


DEFAULT_SCHEDULES_PER_DOCTOR = 3

WEEKLY_SLOT_PATTERNS = [
    [
        (0, time(9, 0), time(12, 0)),
        (2, time(9, 0), time(12, 0)),
        (4, time(16, 0), time(20, 0)),
    ],
    [
        (1, time(10, 0), time(13, 0)),
        (3, time(10, 0), time(13, 0)),
        (5, time(17, 0), time(20, 0)),
    ],
    [
        (0, time(17, 0), time(20, 30)),
        (3, time(17, 0), time(20, 30)),
        (6, time(10, 0), time(13, 0)),
    ],
    [
        (2, time(8, 30), time(11, 30)),
        (4, time(8, 30), time(11, 30)),
        (5, time(15, 0), time(18, 0)),
    ],
]


class Command(BaseCommand):
    help = "Create repeatable dummy weekly schedules for all doctors."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schedules-per-doctor",
            type=int,
            default=DEFAULT_SCHEDULES_PER_DOCTOR,
            help="Number of weekly schedule slots to create for each doctor.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive doctors. By default only active doctors are seeded.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        schedules_per_doctor = options["schedules_per_doctor"]
        if schedules_per_doctor < 1:
            raise CommandError("schedules-per-doctor must be at least 1.")
        if schedules_per_doctor > len(WEEKLY_SLOT_PATTERNS[0]):
            raise CommandError(
                "schedules-per-doctor cannot exceed "
                f"{len(WEEKLY_SLOT_PATTERNS[0])}."
            )

        doctors = Doctor.objects.order_by("name", "id")
        if not options["include_inactive"]:
            doctors = doctors.filter(is_active=True)
        doctors = list(doctors)

        if not doctors:
            raise CommandError("No doctors found. Seed doctors first.")

        created_count = 0
        updated_count = 0

        for index, doctor in enumerate(doctors):
            pattern = WEEKLY_SLOT_PATTERNS[index % len(WEEKLY_SLOT_PATTERNS)]
            slots = _slots_for_doctor(pattern, schedules_per_doctor)

            for weekday, start_time, end_time in slots:
                _, created = DoctorSchedule.objects.update_or_create(
                    doctor=doctor,
                    schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                    defaults={
                        "week_of_month": None,
                        "day_of_month": None,
                        "consultation_type": (
                            DoctorSchedule.ConsultationType.BY_APPOINTMENT
                            if index % 2
                            else DoctorSchedule.ConsultationType.WALK_IN
                        ),
                        "is_active": True,
                    },
                )
                created_count += int(created)
                updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded dummy schedules for {len(doctors)} doctors: "
                f"{created_count} created, {updated_count} updated."
            )
        )


def _slots_for_doctor(pattern, schedules_per_doctor):
    slots = []
    for index in range(schedules_per_doctor):
        slots.append(pattern[index % len(pattern)])
    return slots
