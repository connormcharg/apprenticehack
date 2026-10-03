from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from fivenine.models import Goal, Task, UserProfile

from .models import Apprentice

User = get_user_model()

QUIZ_DATA = {
    "person_type": "planner",
    "chronotype": "early",
    "evenings_per_week": "4",
    "minutes_per_evening": "120",
    "social_balance": "balanced",
    "task_style": "many_small",
    "weekly_tasks": "food shop\nlaundry",
    "first_goal": "Run a 5k",
    "first_goal_category": "health",
}


class OnboardingQuizTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ada@example.com", email="ada@example.com", password="pw-12345"
        )
        self.apprentice = Apprentice.objects.create(
            user=self.user,
            name="Ada Lovelace",
            company="Acme",
            city="Manchester",
            country="UK",
        )
        self.client.force_login(self.user)

    def test_hours_redirects_to_quiz(self):
        response = self.client.post(
            reverse("onboarding:hours"),
            {"work_start": "09:00", "work_end": "17:30", "free_time_hours": "2"},
        )
        self.assertRedirects(response, reverse("onboarding:quiz"))

    def test_hours_skip_redirects_to_quiz(self):
        response = self.client.post(reverse("onboarding:hours"), {"skip": "1"})
        self.assertRedirects(response, reverse("onboarding:quiz"))

    def test_quiz_requires_profile(self):
        Apprentice.objects.all().delete()
        response = self.client.get(reverse("onboarding:quiz"))
        self.assertRedirects(response, reverse("onboarding:about_you"))

    def test_quiz_page_renders(self):
        response = self.client.get(reverse("onboarding:quiz"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Step 3 of 3")
        self.assertContains(response, 'class="choice"')

    def test_completing_quiz_marks_done_and_seeds(self):
        response = self.client.post(reverse("onboarding:quiz"), QUIZ_DATA)
        self.assertRedirects(response, reverse("onboarding:welcome"))

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.quiz_done)
        self.assertEqual(profile.person_type, "planner")
        # Professional details are copied across from the onboarding profile.
        self.assertEqual(profile.company, "Acme")
        self.assertEqual(profile.location, "Manchester, UK")

        self.assertEqual(
            set(Task.objects.filter(user=self.user).values_list("title", flat=True)),
            {"food shop", "laundry"},
        )
        goal = Goal.objects.get(user=self.user)
        self.assertEqual(goal.title, "Run a 5k")
        self.assertEqual(goal.category, "health")

    def test_retake_redirects_to_dashboard(self):
        UserProfile.objects.create(user=self.user, quiz_done=True)
        response = self.client.post(reverse("onboarding:quiz"), QUIZ_DATA)
        self.assertRedirects(response, reverse("dashboard"))

    def test_welcome_shows_quiz_summary(self):
        self.client.post(reverse("onboarding:quiz"), QUIZ_DATA)
        response = self.client.get(reverse("onboarding:welcome"))
        self.assertContains(response, "Your 5-9")
        self.assertContains(response, "Planner")

    def test_fivenine_quiz_redirects_into_onboarding(self):
        response = self.client.get(reverse("quiz"))
        self.assertRedirects(response, reverse("onboarding:quiz"))
