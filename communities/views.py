"""Views for the communities tab.

The list can be filtered by the three things onboarding collects — company,
location and skills — and surfaces communities that match the signed-in
apprentice's own profile. A community has a detail page with its members,
events and chat.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from onboarding.models import Apprentice, Technology

from .forms import CommunityForm, EventForm, MessageForm
from .models import Community, Event, EventRSVP, Membership


def profile_for(user):
    """The signed-in user's onboarding profile, or ``None``."""
    if not user.is_authenticated:
        return None
    return (
        Apprentice.objects.filter(user=user)
        .prefetch_related("technologies")
        .first()
    )


def display_names(users):
    """Display names for a set of users: onboarding first name, else username.

    Onboarding stores the email in ``User.username``, so falling back to the
    username is a last resort for accounts without a profile.
    """
    profiles = {
        apprentice.user_id: apprentice
        for apprentice in Apprentice.objects.filter(user__in=users)
    }
    names = {}
    for user in users:
        apprentice = profiles.get(user.id)
        names[user.id] = (apprentice.first_name if apprentice else "") or user.username
    return names


def match_reasons(community, apprentice):
    """Why ``community`` suits ``apprentice``, as a list of short phrases."""
    if apprentice is None:
        return []
    reasons = []
    if apprentice.company and community.company:
        if apprentice.company.strip().lower() == community.company.strip().lower():
            reasons.append("same company")
    if apprentice.city and community.city:
        if apprentice.city.strip().lower() == community.city.strip().lower():
            reasons.append("same town or city")
    if apprentice.country and community.country:
        if apprentice.country.strip().lower() == community.country.strip().lower():
            reasons.append("same country")
    mine = {tech.key for tech in apprentice.technologies.all()}
    shared = [tech.name for tech in community.technologies.all() if tech.key in mine]
    if shared:
        reasons.append("shares " + ", ".join(shared[:3]))
    return reasons


def _set_technologies(community, names):
    """Attach technologies by name, creating any that don't exist yet."""
    technologies = [
        Technology.objects.get_or_create(key=name.lower(), defaults={"name": name})[0]
        for name in names
    ]
    community.technologies.set(technologies)


@login_required
def community_list(request):
    """Browse and filter communities, with profile-matched suggestions."""
    apprentice = profile_for(request.user)

    communities = (
        Community.objects.select_related("created_by")
        .prefetch_related("technologies", "memberships")
    )

    query = request.GET.get("q", "").strip()
    company = request.GET.get("company", "").strip()
    city = request.GET.get("city", "").strip()
    country = request.GET.get("country", "").strip()
    technology = request.GET.get("technology", "").strip()
    scope = request.GET.get("scope", "").strip()

    if query:
        communities = communities.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    if company:
        communities = communities.filter(company__iexact=company)
    if city:
        communities = communities.filter(city__iexact=city)
    if country:
        communities = communities.filter(country__iexact=country)
    if technology:
        communities = communities.filter(technologies__key=technology)
    if scope == "joined":
        communities = communities.filter(memberships__user=request.user)
    elif scope == "mine":
        communities = communities.filter(created_by=request.user)

    communities = communities.distinct()

    my_ids = set(
        Membership.objects.filter(user=request.user).values_list(
            "community_id", flat=True
        )
    )
    created = Community.objects.filter(created_by=request.user).first()

    # Suggestions: communities that match the profile and haven't been joined.
    recommended = []
    if apprentice is not None:
        for community in (
            Community.objects.prefetch_related("technologies")
            .exclude(pk__in=my_ids)
        ):
            reasons = match_reasons(community, apprentice)
            if reasons:
                recommended.append((community, reasons))
        recommended.sort(key=lambda pair: -len(pair[1]))
        recommended = recommended[:3]

    return render(
        request,
        "communities/community_list.html",
        {
            "communities": communities,
            "recommended": recommended,
            "my_ids": my_ids,
            "created": created,
            "apprentice": apprentice,
            "filters": {
                "q": query,
                "company": company,
                "city": city,
                "country": country,
                "technology": technology,
                "scope": scope,
            },
            "companies": _distinct_values("company"),
            "cities": _distinct_values("city"),
            "countries": _distinct_values("country"),
            "technologies": Technology.objects.filter(
                communities__isnull=False
            ).distinct(),
        },
    )


def _distinct_values(field):
    """Non-empty, de-duplicated values of a community text field."""
    return (
        Community.objects.exclude(**{field: ""})
        .values_list(field, flat=True)
        .distinct()
        .order_by(field)
    )


@login_required
def community_detail(request, pk):
    """A community's members, events and chat."""
    community = get_object_or_404(
        Community.objects.select_related("created_by").prefetch_related(
            "technologies", "memberships__user"
        ),
        pk=pk,
    )
    is_member = community.is_member(request.user)
    now = timezone.now()

    member_users = [membership.user for membership in community.memberships.all()]
    messages = list(community.messages.select_related("author"))
    names = display_names(
        [community.created_by, *member_users, *(m.author for m in messages)]
    )

    members = [{"user": user, "name": names[user.id]} for user in member_users]
    message_rows = [
        {
            "author_name": names[message.author_id],
            "body": message.body,
            "created_at": message.created_at,
            "is_me": message.author_id == request.user.id,
        }
        for message in messages
    ]

    events = community.events.select_related("created_by").prefetch_related("rsvps")
    my_event_ids = set(
        EventRSVP.objects.filter(user=request.user).values_list("event_id", flat=True)
    )

    return render(
        request,
        "communities/community_detail.html",
        {
            "community": community,
            "creator_name": names[community.created_by_id],
            "members": members,
            "is_member": is_member,
            "is_owner": community.created_by_id == request.user.id,
            "upcoming_events": events.filter(starts_at__gte=now),
            "past_events": events.filter(starts_at__lt=now),
            "my_event_ids": my_event_ids,
            "messages": message_rows,
            "message_form": MessageForm(),
            "event_form": EventForm(),
        },
    )


@login_required
def community_create(request):
    """Create the one community a user is allowed to own."""
    existing = Community.objects.filter(created_by=request.user).first()
    if existing is not None:
        messages.info(request, "You can only create one community — here it is.")
        return redirect("communities:detail", pk=existing.pk)

    form = CommunityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        community = form.save(commit=False)
        community.created_by = request.user
        community.save()
        _set_technologies(community, form.cleaned_data["technologies"])
        Membership.objects.get_or_create(community=community, user=request.user)
        messages.success(request, f"“{community.name}” is live. Invite your people!")
        return redirect("communities:detail", pk=community.pk)

    return render(request, "communities/community_form.html", {"form": form})


@login_required
@require_POST
def community_join(request, pk):
    community = get_object_or_404(Community, pk=pk)
    Membership.objects.get_or_create(community=community, user=request.user)
    messages.success(request, f"You joined “{community.name}”.")
    return redirect("communities:detail", pk=pk)


@login_required
@require_POST
def community_leave(request, pk):
    community = get_object_or_404(Community, pk=pk)
    if community.created_by_id == request.user.id:
        messages.error(request, "You can't leave a community you created.")
    else:
        Membership.objects.filter(community=community, user=request.user).delete()
        messages.success(request, f"You left “{community.name}”.")
    return redirect("communities:detail", pk=pk)


@login_required
def event_create(request, pk):
    """Add an event to a community you belong to."""
    community = get_object_or_404(Community, pk=pk)
    if not community.is_member(request.user):
        messages.error(request, "Join the community before adding an event.")
        return redirect("communities:detail", pk=pk)

    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.community = community
        event.created_by = request.user
        event.save()
        EventRSVP.objects.get_or_create(event=event, user=request.user)
        messages.success(request, f"“{event.title}” added.")
        return redirect("communities:detail", pk=pk)

    return render(
        request,
        "communities/event_form.html",
        {"form": form, "community": community},
    )


@login_required
@require_POST
def event_join(request, pk):
    event = get_object_or_404(Event, pk=pk)
    EventRSVP.objects.get_or_create(event=event, user=request.user)
    return redirect("communities:detail", pk=event.community_id)


@login_required
@require_POST
def event_leave(request, pk):
    event = get_object_or_404(Event, pk=pk)
    EventRSVP.objects.filter(event=event, user=request.user).delete()
    return redirect("communities:detail", pk=event.community_id)


@login_required
@require_POST
def message_create(request, pk):
    """Post a chat message to a community you belong to."""
    community = get_object_or_404(Community, pk=pk)
    if not community.is_member(request.user):
        messages.error(request, "Join the community to join the chat.")
        return redirect("communities:detail", pk=pk)

    form = MessageForm(request.POST)
    if form.is_valid():
        message = form.save(commit=False)
        message.community = community
        message.author = request.user
        message.save()
    return redirect("communities:detail", pk=pk)
