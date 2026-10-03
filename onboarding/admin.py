from django.contrib import admin

from .models import Apprentice, Technology


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ("name", "key")
    search_fields = ("name", "key")
    ordering = ("name",)


@admin.register(Apprentice)
class ApprenticeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "company",
        "location",
        "work_start",
        "work_end",
        "free_time_hours",
        "created_at",
    )
    list_filter = ("country", "company")
    list_select_related = ("user",)
    search_fields = (
        "name",
        "user__email",
        "user__username",
        "company",
        "city",
        "country",
        "technologies__name",
    )
    filter_horizontal = ("technologies",)
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    @admin.display(ordering="user__email")
    def email(self, obj):
        return obj.user.email
