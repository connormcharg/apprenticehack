from django.contrib import admin

from .models import CommunityEvent, EnergyLog, EventAttendee, Goal, Task, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'person_type', 'evenings_per_week', 'minutes_per_evening', 'quiz_done')
    readonly_fields = ('calendar_token',)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'target_date', 'done')
    list_filter = ('category', 'done')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'goal', 'parent', 'minutes', 'energy_cost', 'due_date', 'start_time', 'done')
    list_filter = ('kind', 'done', 'energy_cost')


@admin.register(EnergyLog)
class EnergyLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'level', 'note')


@admin.register(CommunityEvent)
class CommunityEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'topic', 'date', 'location')
    list_filter = ('kind',)


@admin.register(EventAttendee)
class EventAttendeeAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'joined_at')
