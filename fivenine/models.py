import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def display_name_for(user):
    """Real name for greetings — never a raw email/username handle."""
    try:
        from onboarding.models import Apprentice
        ap = Apprentice.objects.filter(user=user).first()
        if ap is not None and ap.first_name:
            return ap.first_name
    except Exception:
        pass
    if getattr(user, 'first_name', ''):
        return user.first_name
    handle = (getattr(user, 'email', '') or user.username).split('@')[0]
    return handle.replace('.', ' ').replace('_', ' ').strip().title() or 'there'


class UserProfile(models.Model):
    """Onboarding quiz answers: who you are + how much 5-9 time you'll commit."""
    PERSON_TYPES = [
        ('planner', 'Planner — I love a routine'),
        ('spontaneous', 'Go-with-the-flow'),
        ('balancer', 'A bit of both'),
    ]
    CHRONOTYPES = [
        ('early', 'Early bird — best right after work'),
        ('night', 'Night owl — best later in the evening'),
        ('either', 'Either — energy decides'),
    ]
    SOCIAL_BALANCE = [
        ('self', 'Mostly me-time (recharge solo)'),
        ('balanced', 'Balanced social + self'),
        ('social', 'Mostly social (recharge with people)'),
    ]
    TASK_STYLES = [
        ('few_big', 'Few bigger tasks per evening'),
        ('many_small', 'Many small tasks per evening'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    person_type = models.CharField(max_length=20, choices=PERSON_TYPES, default='balancer')
    chronotype = models.CharField(max_length=20, choices=CHRONOTYPES, default='either')
    evenings_per_week = models.PositiveSmallIntegerField(default=4, help_text='Evenings per week you want planned (1-7)')
    minutes_per_evening = models.PositiveSmallIntegerField(default=120, help_text='Free minutes on a typical evening')
    social_balance = models.CharField(max_length=20, choices=SOCIAL_BALANCE, default='balanced')
    task_style = models.CharField(max_length=20, choices=TASK_STYLES, default='many_small')
    company = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    skills = models.CharField(max_length=300, blank=True, help_text='Comma-separated, e.g. Python, presenting, CAD')
    calendar_token = models.UUIDField(default=uuid.uuid4, unique=True)
    quiz_done = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} profile'


class Goal(models.Model):
    CATEGORIES = [
        ('health', 'Health & Fitness'),
        ('study', 'Study / Uni'),
        ('career', 'Career / Skills'),
        ('money', 'Money'),
        ('social', 'Social'),
        ('home', 'Home & Life admin'),
    ]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='career')
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Task(models.Model):
    KINDS = [
        ('goal', 'Goal step'),
        ('chore', 'Household'),
        ('study', 'Study'),
        ('rest', 'Rest / Recharge'),
        ('social', 'Social'),
    ]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=KINDS, default='goal')
    goal = models.ForeignKey(Goal, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    minutes = models.PositiveIntegerField(default=30, help_text='How long in minutes')
    energy_cost = models.PositiveSmallIntegerField(default=2, choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')])
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True, help_text='Optional start time, e.g. 18:30')
    notes = models.TextField(blank=True, help_text='Details, links, anything you need')
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def energy_label(self):
        return {1: 'Low', 2: 'Medium', 3: 'High'}.get(self.energy_cost, 'Medium')


class EnergyLog(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='energy_logs')
    date = models.DateField(default=timezone.now)
    level = models.PositiveSmallIntegerField(choices=[(1, '1 - Drained'), (2, '2 - Low'), (3, '3 - OK'), (4, '4 - Good'), (5, '5 - Great')])
    note = models.CharField(max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.date}: {self.level}'


def goal_progress(goal):
    """(done, total) across a goal's tasks."""
    total = goal.tasks.count()
    done = goal.tasks.filter(done=True).count()
    return done, total


def goal_next_steps(goal, limit=3):
    """Oldest open tasks as the goal's next steps."""
    return list(goal.tasks.filter(done=False).order_by('due_date')[:limit])
