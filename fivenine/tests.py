import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities.models import Community, Event

from .models import Goal, Task, UserProfile


def make_user(email="d@example.com"):
    return get_user_model().objects.create_user(
        username=email, email=email, password="pw-12345"
    )


class DashboardSmokeTests(TestCase):
    def test_dashboard_renders_with_completed_profile(self):
        user = make_user()
        UserProfile.objects.create(user=user, quiz_done=True)
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)


class GoalTickBoxTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.goal = Goal.objects.create(user=self.user, title="Run a 5k", category="health")
        self.step = Task.objects.create(
            user=self.user, title="Buy running shoes", goal=self.goal, kind="goal"
        )

    def test_goal_card_shows_tick_box_for_step(self):
        response = self.client.get(reverse("goal_list"))
        self.assertContains(response, "Buy running shoes")
        self.assertContains(
            response,
            f'href="{reverse("task_toggle", args=[self.step.pk])}?next={reverse("goal_list")}"',
        )

    def test_ticking_step_marks_it_done(self):
        self.client.get(
            reverse("task_toggle", args=[self.step.pk]), {"next": reverse("goal_list")}
        )
        self.step.refresh_from_db()
        self.assertTrue(self.step.done)


class CalendarSlotTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.task = Task.objects.create(
            user=self.user, title="Laundry", due_date=date.today(), kind="chore"
        )

    def test_calendar_shows_tick_box_for_task(self):
        response = self.client.get(reverse("calendar"))
        self.assertContains(response, "Laundry")
        self.assertContains(
            response,
            f'href="{reverse("task_toggle", args=[self.task.pk])}?next={reverse("calendar")}"',
        )

    def test_plan_schedules_undated_tasks(self):
        undated = Task.objects.create(user=self.user, title="Clean bathroom", kind="chore")
        response = self.client.post(reverse("calendar"), {"plan": "1"})
        self.assertRedirects(response, reverse("calendar"))
        undated.refresh_from_db()
        self.assertIsNotNone(undated.due_date)

    def test_plan_button_hidden_when_nothing_undated(self):
        response = self.client.get(reverse("calendar"))
        self.assertNotContains(response, "unscheduled task")

    def test_plan_button_shown_when_something_undated(self):
        Task.objects.create(user=self.user, title="Clean bathroom", kind="chore")
        response = self.client.get(reverse("calendar"))
        self.assertContains(response, "unscheduled task")


class PwaTests(TestCase):
    def test_manifest_is_served(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = json.loads(b"".join(response.streaming_content))
        self.assertEqual(data["name"], "Life 5-9")
        self.assertEqual(data["display"], "standalone")
        self.assertTrue(any(icon["sizes"] == "512x512" for icon in data["icons"]))

    def test_service_worker_is_served(self):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertEqual(response["Cache-Control"], "no-cache")

    def test_offline_page_renders(self):
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "offline")


class AssistantEventTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_event_needs_a_community(self):
        from .assistant import apply_actions

        reply = 'Sure.\n```action {"op": "create_event", "title": "Meetup", "date": "2030-01-01"}```'
        result = apply_actions(self.user, reply)

        self.assertIn("community", result.lower())
        self.assertEqual(Event.objects.count(), 0)

    def test_event_goes_into_users_community(self):
        from .assistant import apply_actions

        community = Community.objects.create(name="My Club", created_by=self.user)
        reply = 'Sure.\n```action {"op": "create_event", "title": "Meetup", "date": "2030-01-01", "start_time": "18:30"}```'
        result = apply_actions(self.user, reply)

        event = Event.objects.get()
        self.assertEqual(event.community, community)
        self.assertEqual(event.title, "Meetup")
        self.assertIn("My Club", result)
