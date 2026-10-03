from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from onboarding.models import Apprentice, Technology

from .models import Community, Event, EventRSVP, Membership, Message

User = get_user_model()


def make_user(email):
    return User.objects.create_user(username=email, email=email, password="pw-12345")


def make_apprentice(user, name="Ada Lovelace", company="Acme", city="Manchester", country="UK", techs=()):
    apprentice = Apprentice.objects.create(
        user=user, name=name, company=company, city=city, country=country
    )
    for name in techs:
        tech, _ = Technology.objects.get_or_create(key=name.lower(), defaults={"name": name})
        apprentice.technologies.add(tech)
    return apprentice


class CommunityModelTests(TestCase):
    def test_one_community_per_user(self):
        user = make_user("owner@example.com")
        Community.objects.create(name="First", created_by=user)
        with self.assertRaises(Exception):
            Community.objects.create(name="Second", created_by=user)

    def test_user_can_join_many_communities(self):
        owner_a = make_user("a@example.com")
        owner_b = make_user("b@example.com")
        joiner = make_user("joiner@example.com")
        first = Community.objects.create(name="First", created_by=owner_a)
        second = Community.objects.create(name="Second", created_by=owner_b)
        Membership.objects.create(community=first, user=joiner)
        Membership.objects.create(community=second, user=joiner)
        self.assertEqual(joiner.community_memberships.count(), 2)


class CommunityViewTests(TestCase):
    def setUp(self):
        self.user = make_user("ada@example.com")
        make_apprentice(self.user, techs=["Python", "SQL"])
        self.client.force_login(self.user)

    def test_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("communities:list"))
        self.assertEqual(response.status_code, 302)

    def test_create_community_joins_creator(self):
        response = self.client.post(
            reverse("communities:create"),
            {
                "name": "Manchester Python",
                "description": "For Python folks",
                "company": "Acme",
                "city": "Manchester",
                "country": "UK",
                "technologies": "Python, SQL",
            },
        )
        community = Community.objects.get(name="Manchester Python")
        self.assertRedirects(response, reverse("communities:detail", args=[community.pk]))
        self.assertTrue(community.is_member(self.user))
        self.assertEqual(
            set(community.technologies.values_list("name", flat=True)),
            {"Python", "SQL"},
        )

    def test_second_create_redirects_to_existing(self):
        existing = Community.objects.create(name="Mine", created_by=self.user)
        response = self.client.get(reverse("communities:create"))
        self.assertRedirects(response, reverse("communities:detail", args=[existing.pk]))

    def test_filter_by_company(self):
        owner = make_user("owner@example.com")
        Community.objects.create(name="Acme Club", company="Acme", created_by=owner)
        other = make_user("other@example.com")
        Community.objects.create(name="Globex Club", company="Globex", created_by=other)
        response = self.client.get(reverse("communities:list"), {"company": "Acme"})
        names = [c.name for c in response.context["communities"]]
        self.assertEqual(names, ["Acme Club"])

    def test_filter_by_skill(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Python Club", created_by=owner)
        tech, _ = Technology.objects.get_or_create(key="python", defaults={"name": "Python"})
        community.technologies.add(tech)
        response = self.client.get(reverse("communities:list"), {"technology": "python"})
        self.assertEqual([c.name for c in response.context["communities"]], ["Python Club"])

    def test_recommends_profile_match(self):
        owner = make_user("owner@example.com")
        match = Community.objects.create(
            name="Acme Manchester", company="Acme", city="Manchester", created_by=owner
        )
        Community.objects.create(name="Unrelated", company="Globex", created_by=make_user("x@example.com"))
        response = self.client.get(reverse("communities:list"))
        recommended = [c for c, _ in response.context["recommended"]]
        self.assertIn(match, recommended)

    def test_chat_requires_membership(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Private", created_by=owner)
        response = self.client.post(
            reverse("communities:message_create", args=[community.pk]),
            {"body": "hello"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 0)

    def test_member_can_chat(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Open", created_by=owner)
        Membership.objects.create(community=community, user=self.user)
        self.client.post(
            reverse("communities:message_create", args=[community.pk]),
            {"body": "hello"},
        )
        self.assertEqual(Message.objects.get().body, "hello")

    def test_event_creation_requires_membership(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Open", created_by=owner)
        response = self.client.post(
            reverse("communities:event_create", args=[community.pk]),
            {
                "title": "Meetup",
                "starts_at": "2030-01-01T18:30",
                "location": "Cafe",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Event.objects.count(), 0)

    def test_member_can_create_and_rsvp_event(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Open", created_by=owner)
        Membership.objects.create(community=community, user=self.user)
        self.client.post(
            reverse("communities:event_create", args=[community.pk]),
            {
                "title": "Meetup",
                "starts_at": "2030-01-01T18:30",
                "location": "Cafe",
            },
        )
        event = Event.objects.get()
        self.assertEqual(event.community, community)
        self.assertTrue(EventRSVP.objects.filter(event=event, user=self.user).exists())

    def test_detail_page_renders(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Renders Fine", created_by=owner)
        Membership.objects.create(community=community, user=self.user)
        response = self.client.get(reverse("communities:detail", args=[community.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Renders Fine")

    def test_member_list_shows_first_name(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Names", created_by=owner)
        Membership.objects.create(community=community, user=self.user)
        response = self.client.get(reverse("communities:detail", args=[community.pk]))
        self.assertContains(response, "Ada")
        self.assertNotContains(response, '<span class="badge">ada@example.com</span>')

    def test_chat_and_creator_use_first_names(self):
        owner = make_user("owner@example.com")
        make_apprentice(owner, name="Grace Hopper")
        community = Community.objects.create(name="Names", created_by=owner)
        Membership.objects.create(community=community, user=self.user)
        self.client.post(
            reverse("communities:message_create", args=[community.pk]), {"body": "hi"}
        )
        response = self.client.get(reverse("communities:detail", args=[community.pk]))
        self.assertContains(response, "Created by Grace")
        self.assertContains(response, "<strong>Ada</strong>")

    def test_create_and_event_forms_render(self):
        owner = make_user("owner@example.com")
        community = Community.objects.create(name="Open", created_by=owner)
        Membership.objects.create(community=community, user=self.user)
        self.assertEqual(self.client.get(reverse("communities:create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("communities:event_create", args=[community.pk])).status_code,
            200,
        )

    def test_owner_cannot_leave_own_community(self):
        community = Community.objects.create(name="Mine", created_by=self.user)
        Membership.objects.create(community=community, user=self.user)
        self.client.post(reverse("communities:leave", args=[community.pk]))
        self.assertTrue(community.is_member(self.user))
