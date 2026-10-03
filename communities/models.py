"""Communities: groups of apprentices who connect, meet up and chat.

A community is described by the same things onboarding collects — company,
location and the technologies an apprentice works with — so the list can be
filtered by any of them. Each user may create at most one community (enforced
by the one-to-one ``created_by``) but join as many as they like.
"""

from django.conf import settings
from django.db import models


class Community(models.Model):
    """A group apprentices can join, with its own events and chat."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    # The onboarding profile fields, copied onto the community so it can be
    # filtered and matched without reaching across apps on every query.
    company = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True)
    technologies = models.ManyToManyField(
        "onboarding.Technology", related_name="communities", blank=True
    )

    # One community per user: the one-to-one is what enforces the limit.
    created_by = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_community",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "communities"

    def __str__(self):
        return self.name

    @property
    def location(self):
        """Town/city and country as one display string."""
        return ", ".join(part for part in (self.city, self.country) if part)

    def member_count(self):
        return self.memberships.count()

    def is_member(self, user):
        if not user.is_authenticated:
            return False
        return self.memberships.filter(user=user).exists()


class Membership(models.Model):
    """A user's membership of a community."""

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("community", "user")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.community}"


class Event(models.Model):
    """A meet-up organised inside a community."""

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="events"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True, help_text="Place or link")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_community_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return f"{self.title} ({self.starts_at:%Y-%m-%d %H:%M})"

    def attendee_count(self):
        return self.rsvps.count()


class EventRSVP(models.Model):
    """Someone going to a community event."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="rsvps"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_event_rsvps",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("event", "user")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} -> {self.event.title}"


class Message(models.Model):
    """A message in a community's chat."""

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.body[:40]}"
