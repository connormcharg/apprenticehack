from django.contrib import admin

from .models import Community, Event, EventRSVP, Membership, Message


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "location", "created_by", "created_at")
    list_filter = ("country", "company")
    search_fields = ("name", "description", "company", "city", "country")
    filter_horizontal = ("technologies",)
    raw_id_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "joined_at")
    list_filter = ("community",)
    raw_id_fields = ("user",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "community", "starts_at", "location")
    list_filter = ("community",)
    search_fields = ("title", "description", "location")
    raw_id_fields = ("created_by",)
    date_hierarchy = "starts_at"


@admin.register(EventRSVP)
class EventRSVPAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "created_at")
    raw_id_fields = ("user",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("community", "author", "created_at")
    list_filter = ("community",)
    search_fields = ("body",)
    raw_id_fields = ("author",)
