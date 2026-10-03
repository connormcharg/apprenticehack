import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subtasks',
                               help_text='Set to make this a sub-task of another task')
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=KINDS, default='goal')
    goal = models.ForeignKey(Goal, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    minutes = models.PositiveIntegerField(default=30, help_text='How long in minutes')
    energy_cost = models.PositiveSmallIntegerField(default=2, choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')])
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True, help_text='Optional start time, e.g. 18:30')
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def progress(self):
        """(done_count, total_count) including sub-tasks."""
        kids = list(self.subtasks.all())
        if not kids:
            return (1 if self.done else 0, 1)
        done = sum(1 for k in kids if k.done)
        return done, len(kids)


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


class CommunityEvent(models.Model):
    KINDS = [
        ('hackathon', 'Hackathon'),
        ('social', 'Social'),
        ('multi-company', 'Multi-company'),
        ('learning', 'Learning / CPD'),
    ]
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=KINDS, default='social')
    topic = models.CharField(max_length=120, blank=True, help_text='e.g. cybersecurity, climbing, CV help')
    date = models.DateField()
    location = models.CharField(max_length=200, blank=True, help_text='Place or link')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.title} ({self.date})'

    def member_count(self):
        return self.attendees.count()


class EventAttendee(models.Model):
    """Someone going to a community event (powers member display + RSVP)."""
    event = models.ForeignKey(CommunityEvent, on_delete=models.CASCADE, related_name='attendees')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_rsvps')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('event', 'user')]
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user.username} -> {self.event.title}'


def goal_progress(goal):
    """(done, total) across a goal's top-level tasks including their sub-tasks."""
    done = total = 0
    for task in goal.tasks.filter(parent__isnull=True):
        if task.subtasks.exists():
            for sub in task.subtasks.all():
                total += 1
                done += 1 if sub.done else 0
        else:
            total += 1
            done += 1 if task.done else 0
    return done, total


def goal_next_steps(goal, limit=3):
    """Oldest open tasks (top-level first) as the goal's next steps."""
    steps = []
    for task in goal.tasks.filter(parent__isnull=True, done=False).order_by('due_date'):
        open_subs = task.subtasks.filter(done=False)
        if open_subs.exists():
            steps.extend(open_subs.order_by('created_at')[:max(0, limit - len(steps))])
        else:
            steps.append(task)
        if len(steps) >= limit:
            break
    return steps[:limit]
