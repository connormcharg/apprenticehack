from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q


def find_account(email):
    """The user account for an email address, matched on email or username.

    The email doubles as the username, so either column can be the one that
    matches. Ordering by pk keeps the result stable if both somehow match
    different rows.
    """
    if not email:
        return None
    user_model = get_user_model()
    return (
        user_model.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
        .order_by("pk")
        .first()
    )


def hours_between(start, end):
    """Hours from ``start`` to ``end``, treating an earlier end as crossing midnight."""
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60
    return (end_minutes - start_minutes) / 60


class Technology(models.Model):
    """A language, tool or framework an apprentice works with.

    ``key`` is the case-insensitive identity used for lookups so that
    "python" and "Python" collapse onto a single row, while ``name`` keeps
    the casing the first apprentice typed.
    """

    name = models.CharField(max_length=80)
    key = models.CharField(max_length=80, unique=True, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "technologies"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        if not self.key:
            self.key = self.name.lower()
        super().save(*args, **kwargs)


class Apprentice(models.Model):
    """The onboarding profile for an authenticated user.

    Identity and credentials live on ``django.contrib.auth.User``; this model
    holds only what the onboarding sentence collects. The email address is
    therefore not duplicated here — read it through :attr:`email`.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="apprentice_profile",
    )
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    country = models.CharField(max_length=80)
    technologies = models.ManyToManyField(
        Technology, related_name="apprentices", blank=True
    )

    # Step 2 of onboarding. Nullable because a profile exists as soon as step 1
    # is saved, and step 2 can be skipped.
    work_start = models.TimeField(null=True, blank=True)
    work_end = models.TimeField(null=True, blank=True)
    free_time_hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Hours a day to keep free of activities.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def email(self):
        return self.user.email

    @property
    def first_name(self):
        """The first token of the name, for greetings."""
        return self.name.split()[0] if self.name else ""

    @property
    def location(self):
        """Town/city and country as one display string."""
        return ", ".join(part for part in (self.city, self.country) if part)

    @property
    def has_working_hours(self):
        return self.work_start is not None and self.work_end is not None

    @property
    def work_hours(self):
        """Hours worked per day, or ``None`` if step 2 hasn't been filled in."""
        if not self.has_working_hours:
            return None
        return hours_between(self.work_start, self.work_end)
