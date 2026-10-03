"""Link Apprentice to django.contrib.auth and add town/city + country.

Written by hand rather than generated because ``user`` is non-nullable and
replaces ``email`` as the profile's identity. The steps are ordered so that a
database which already holds profiles keeps working:

1. add ``user`` as nullable,
2. create/link an account for every existing profile, using its email,
3. drop ``email`` (now redundant with ``user.email``),
4. tighten ``user`` to non-nullable.
"""

from django.conf import settings
from django.db import migrations, models

import django.db.models.deletion


def link_existing_profiles(apps, schema_editor):
    Apprentice = apps.get_model("onboarding", "Apprentice")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    orphans = Apprentice.objects.filter(user__isnull=True).exclude(email="")
    for profile in orphans.iterator():
        email = profile.email.strip().lower()
        user = (
            User.objects.filter(email__iexact=email).first()
            or User.objects.filter(username=email).first()
        )
        if user is None:
            user = User(username=email, email=email)
            # "!" is what set_unusable_password() stores; historical models
            # don't carry the real model's methods.
            user.password = "!"

        first, _, rest = (profile.name or "").partition(" ")
        user.first_name = first[:30]
        user.last_name = rest[:150]
        user.save()

        profile.user = user
        profile.save(update_fields=["user"])


def unlink_profiles(apps, schema_editor):
    Apprentice = apps.get_model("onboarding", "Apprentice")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    for profile in Apprentice.objects.exclude(user__isnull=True).iterator():
        profile.email = profile.user.email
        profile.save(update_fields=["email"])
    User.objects.filter(apprentice_profile__isnull=False, password="!").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="apprentice",
            name="user",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="apprentice_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(link_existing_profiles, unlink_profiles),
        migrations.RemoveField(
            model_name="apprentice",
            name="email",
        ),
        migrations.AlterField(
            model_name="apprentice",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="apprentice_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="apprentice",
            name="city",
            field=models.CharField(default="", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprentice",
            name="country",
            field=models.CharField(default="", max_length=80),
            preserve_default=False,
        ),
    ]
