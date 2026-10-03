from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile


class DashboardSmokeTests(TestCase):
    def test_dashboard_renders_with_completed_profile(self):
        user = get_user_model().objects.create_user(
            username="d@example.com", email="d@example.com", password="pw-12345"
        )
        UserProfile.objects.create(user=user, quiz_done=True)
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
