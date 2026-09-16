from django.contrib import admin

from doctors.models import Doctor, DoctorSchedule, DoctorSpecialty


@admin.register(DoctorSpecialty)
class DoctorSpecialtyAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "label",
        "slug",
        "aliases",
        "body_part",
        "image",
        "sort_order",
        "is_active",
        "is_featured",
    )
    list_display = (
        "name",
        "label",
        "slug",
        "body_part",
        "sort_order",
        "is_active",
        "is_featured",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = ("sort_order", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "body_part")
    search_fields = ("name", "label", "slug", "aliases")
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    save_on_top = True


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "General Info",
            {
                "fields": (
                    "business",
                    "name",
                    "slug",
                    "specialties",
                    "qualification",
                    "gender",
                    "bio",
                )
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "profile_image",
                )
            },
        ),
        (
            "Registration",
            {
                "fields": (
                    "registration_number",
                    "registration_council",
                    "registration_year",
                )
            },
        ),
        (
            "Consultation",
            {
                "fields": (
                    "consultation_fee",
                )
            },
        ),
        (
            "Practice Details",
            {
                "fields": (
                    "languages",
                    "treatments",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_featured",
                )
            },
        ),
    )
    list_display = (
        "name",
        "business",
        "qualification",
        "consultation_fee",
        "gender",
        "is_active",
        "is_featured",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = ("is_active", "is_featured")
    list_filter = (
        "is_active",
        "is_featured",
        "gender",
        "specialties",
        "business",
    )
    search_fields = (
        "name",
        "slug",
        "qualification",
        "registration_number",
        "registration_council",
        "business__name",
        "business__slug",
        "specialties__name",
        "specialties__label",
    )
    autocomplete_fields = ("business", "specialties")
    ordering = ("-is_featured", "name")
    readonly_fields = ("slug", "created_at", "updated_at")
    list_per_page = 50
    save_on_top = True


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    fields = (
        "doctor",
        "schedule_type",
        "weekday",
        "week_of_month",
        "day_of_month",
        "start_time",
        "end_time",
        "consultation_type",
        "is_active",
    )
    list_display = (
        "doctor",
        "doctor_display",
        "schedule_type",
        "schedule_label_display",
        "start_time",
        "end_time",
        "consultation_type",
        "is_active",
        "updated_at",
    )
    list_display_links = ("doctor",)
    list_editable = ("is_active",)
    list_filter = (
        "is_active",
        "schedule_type",
        "weekday",
        "week_of_month",
        "consultation_type",
        "start_time",
    )
    search_fields = (
        "doctor__name",
        "doctor__slug",
    )
    raw_id_fields = ("doctor",)
    ordering = (
        "doctor",
        "schedule_type",
        "weekday",
        "week_of_month",
        "day_of_month",
        "start_time",
    )
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    save_on_top = True

    @admin.display(description="Doctor")
    def doctor_display(self, obj):
        return obj.doctor

    @admin.display(description="Schedule")
    def schedule_label_display(self, obj):
        return obj.schedule_label
