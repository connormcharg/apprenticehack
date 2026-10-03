from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from fivenine.models import Goal, Task, UserProfile

from .forms import OnboardingForm, QuizForm, SignInForm, SignUpForm, WorkingHoursForm
from .models import Apprentice, Technology


def home(request):
    """Send visitors to their profile if they have one, otherwise to sign-up."""
    if request.user.is_authenticated:
        return redirect("onboarding:welcome")
    return redirect("onboarding:sign_up")


def _profile_for(user):
    """The signed-in visitor's onboarding profile, or ``None``."""
    if not user.is_authenticated:
        return None
    return (
        Apprentice.objects.filter(user=user)
        .select_related("user")
        .prefetch_related("technologies")
        .first()
    )


def _initial_from(apprentice):
    return {
        "name": apprentice.name,
        "company": apprentice.company,
        "city": apprentice.city,
        "country": apprentice.country,
        "technologies": ", ".join(t.name for t in apprentice.technologies.all()),
    }


@require_http_methods(["GET", "POST"])
def sign_up(request):
    """Create an account, then hand straight over to onboarding step 1."""
    if request.user.is_authenticated:
        return redirect("onboarding:welcome")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = get_user_model()(
                username=form.cleaned_data["email"],
                email=form.cleaned_data["email"],
            )
            user.set_password(form.cleaned_data["password"])
            user.save()
            login(request, user)
            return redirect("onboarding:about_you")
    else:
        form = SignUpForm()

    return render(request, "onboarding/sign_up.html", {"form": form})


@transaction.atomic
def _save_apprentice(user, cleaned):
    """Create or refresh the signed-in user's profile.

    The account already exists, so this only touches profile data — plus the
    user's first/last name, which the admin and auth machinery like to have.
    """
    first, _, rest = cleaned["name"].partition(" ")
    user.first_name = first[:30]
    user.last_name = rest[:150]
    user.save(update_fields=["first_name", "last_name"])

    apprentice, _created = Apprentice.objects.update_or_create(
        user=user,
        defaults={
            "name": cleaned["name"],
            "company": cleaned["company"],
            "city": cleaned["city"],
            "country": cleaned["country"],
        },
    )
    technologies = [
        Technology.objects.get_or_create(key=name.lower(), defaults={"name": name})[0]
        for name in cleaned["technologies"]
    ]
    apprentice.technologies.set(technologies)


@require_http_methods(["GET", "POST"])
def about_you(request):
    """Step 1: the fill-in-the-blank sentence about the apprentice."""
    if not request.user.is_authenticated:
        return redirect("onboarding:sign_up")

    existing = _profile_for(request.user)

    if request.method == "POST":
        form = OnboardingForm(request.POST)
        if form.is_valid():
            _save_apprentice(request.user, form.cleaned_data)
            return redirect("onboarding:hours")
    else:
        form = OnboardingForm(initial=_initial_from(existing) if existing else None)

    return render(request, "onboarding/about_you.html", {"form": form})


@require_http_methods(["GET", "POST"])
def hours(request):
    """Step 2: working hours and the free time to protect."""
    if not request.user.is_authenticated:
        return redirect("onboarding:sign_in")

    apprentice = _profile_for(request.user)
    if apprentice is None:
        return redirect("onboarding:about_you")

    if request.method == "POST":
        if "skip" in request.POST:
            return redirect("onboarding:quiz")

        form = WorkingHoursForm(request.POST)
        if form.is_valid():
            apprentice.work_start = form.cleaned_data["work_start"]
            apprentice.work_end = form.cleaned_data["work_end"]
            apprentice.free_time_hours = form.cleaned_data["free_time_hours"]
            apprentice.save()
            return redirect("onboarding:quiz")
    else:
        form = WorkingHoursForm(
            initial={
                "work_start": apprentice.work_start,
                "work_end": apprentice.work_end,
                "free_time_hours": apprentice.free_time_hours,
            }
        )

    return render(request, "onboarding/hours.html", {"form": form})


def _seed_from_quiz(user, cleaned):
    """Turn the quiz's free-text answers into starter tasks and a goal."""
    for line in (cleaned.get("weekly_tasks") or "").splitlines():
        title = line.strip().lstrip("-*• ").strip()
        if title and not Task.objects.filter(user=user, title__iexact=title).exists():
            Task.objects.create(
                user=user, title=title, kind="chore", minutes=30, energy_cost=1
            )

    first_goal = (cleaned.get("first_goal") or "").strip()
    if first_goal and not Goal.objects.filter(user=user, title__iexact=first_goal).exists():
        Goal.objects.create(
            user=user,
            title=first_goal,
            category=cleaned.get("first_goal_category") or "career",
        )


@require_http_methods(["GET", "POST"])
def quiz(request):
    """Step 3: the 5-9 preferences that tune the planner.

    This is the quiz that used to be a separate page after sign-up; it now
    completes onboarding. The professional details are already collected in
    step 1, so they are copied onto the profile rather than asked again.
    """
    if not request.user.is_authenticated:
        return redirect("onboarding:sign_in")

    apprentice = _profile_for(request.user)
    if apprentice is None:
        return redirect("onboarding:about_you")

    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    first_time = not profile.quiz_done
    form = QuizForm(request.POST or None, instance=profile)

    if request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.quiz_done = True
        # Keep the planner's copy of the professional details in step with
        # what step 1 collected.
        profile.company = apprentice.company
        profile.location = apprentice.location
        profile.skills = ", ".join(t.name for t in apprentice.technologies.all())
        profile.save()
        if first_time:
            _seed_from_quiz(request.user, form.cleaned_data)
        return redirect("onboarding:welcome" if first_time else "dashboard")

    return render(
        request,
        "onboarding/quiz.html",
        {"form": form, "first_time": first_time},
    )


@require_GET
def welcome(request):
    """Confirmation screen shown once onboarding is done."""
    if not request.user.is_authenticated:
        return redirect("onboarding:sign_in")

    apprentice = _profile_for(request.user)
    if apprentice is None:
        return redirect("onboarding:about_you")
    profile = UserProfile.objects.filter(user=request.user).first()
    return render(
        request,
        "onboarding/welcome.html",
        {"apprentice": apprentice, "profile": profile},
    )


sign_in = LoginView.as_view(
    template_name="onboarding/sign_in.html",
    authentication_form=SignInForm,
    # Someone who is already signed in has no business on this page.
    redirect_authenticated_user=True,
)

sign_out = LogoutView.as_view()
