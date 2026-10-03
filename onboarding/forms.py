"""The onboarding forms.

Account creation and sign-in are ordinary stacked forms. The two onboarding
steps are rendered as "fill in the blank" sentences, so their fields carry the
presentation attributes (placeholder, autocomplete, sizing hook) that the
templates need and nothing else.

The technologies blank is posted as a single free-text string. That keeps the
form fully usable without JavaScript, where the visitor simply types
"Python, SQL, React"; the front end progressively enhances the same input into
a tag/chip editor.
"""

import re
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from fivenine.models import Goal, UserProfile

from .models import find_account, hours_between

MAX_TECHNOLOGIES = 12
MAX_TECHNOLOGY_LENGTH = 40
# The email doubles as User.username, so it has to fit in that column.
MAX_USERNAME_LENGTH = 150

# Commas, semicolons, line breaks and a plain-English "and" all separate
# technologies, so "Python, SQL and React" parses the way it reads.
TECHNOLOGY_SEPARATOR = re.compile(r"[,;\n]|\s+and\s+", re.IGNORECASE)
RUNNING_WHITESPACE = re.compile(r"\s+")
HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

BLANK_WIDGET_ATTRS = {
    "class": "blank__input",
    "data-autosize": "",
}


def split_technologies(raw):
    """Split free text into unique, trimmed technology names.

    Order is preserved and duplicates are dropped case-insensitively, keeping
    the first spelling the visitor used.
    """
    tokens = {}
    for part in TECHNOLOGY_SEPARATOR.split(raw or ""):
        # rstrip(".") so a trailing sentence full stop is dropped but ".NET"
        # and "Node.js" survive.
        token = part.strip().rstrip(".").strip()
        if token:
            tokens.setdefault(token.lower(), token)
    return list(tokens.values())


def normalize_blank(value, message):
    """Collapse whitespace and reject answers too short to be real."""
    text = RUNNING_WHITESPACE.sub(" ", value.strip())
    if len(text) < 2:
        raise forms.ValidationError(message)
    return text


def check_password_strength(password, email="", name=""):
    """Run Django's configured AUTH_PASSWORD_VALIDATORS over a new password.

    Returns a list of messages, empty when the password is acceptable.
    """
    candidate = get_user_model()(
        username=email,
        email=email,
        first_name=(name or "").partition(" ")[0][:30],
    )
    try:
        validate_password(password, candidate)
    except DjangoValidationError as error:
        return error.messages
    return []


class SignUpForm(forms.Form):
    """Account creation: an email address and a password, nothing else."""

    email = forms.EmailField(
        label="Email address",
        error_messages={
            "required": "We need an email address to create your account.",
            "invalid": "That email doesn't look quite right — mind checking it?",
        },
        widget=forms.EmailInput(
            attrs={
                "class": "field__input",
                "placeholder": "ada@company.com",
                "autocomplete": "email",
                "inputmode": "email",
                "spellcheck": "false",
                "autofocus": True,
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "field__input",
                "placeholder": "At least 8 characters",
                "autocomplete": "new-password",
            }
        ),
    )

    password_confirm = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "field__input",
                "placeholder": "Type it once more",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if len(email) > MAX_USERNAME_LENGTH:
            raise forms.ValidationError(
                f"That email is too long to use as your sign-in — please keep it "
                f"under {MAX_USERNAME_LENGTH} characters."
            )
        if find_account(email) is not None:
            raise forms.ValidationError(
                "There's already an account with that email. Try signing in instead."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password") or ""
        confirm = cleaned.get("password_confirm") or ""

        if not password:
            return cleaned

        if confirm != password:
            self.add_error("password_confirm", "Those two passwords don't match.")
        else:
            for message in check_password_strength(password, cleaned.get("email", "")):
                self.add_error("password", message)
        return cleaned


class SignInForm(AuthenticationForm):
    """Django's AuthenticationForm, relabelled for email-as-username.

    Onboarding stores the email in ``User.username``, so the stock form's
    "Username" field is really an email address.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That email and password don't match. Please try again.",
    }

    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "class": "field__input",
                "placeholder": "ada@company.com",
                "autocomplete": "email",
                "inputmode": "email",
                "spellcheck": "false",
                "autofocus": True,
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "field__input",
                "placeholder": "Your password",
                "autocomplete": "current-password",
            }
        ),
    )


class OnboardingForm(forms.Form):
    """Step 1: name, company, location and technologies.

    The account already exists by this point, so there is no email or password
    blank here — see :class:`SignUpForm`.
    """

    name = forms.CharField(
        label="Your name",
        max_length=120,
        error_messages={
            "required": "Let's start with your name.",
            "max_length": "That's a long name — please keep it under 120 characters.",
        },
        widget=forms.TextInput(
            attrs={
                **BLANK_WIDGET_ATTRS,
                "placeholder": "Ada Lovelace",
                "autocomplete": "name",
                "autocapitalize": "words",
                "spellcheck": "false",
            }
        ),
    )

    company = forms.CharField(
        label="Your company",
        max_length=120,
        error_messages={
            "required": "Which company are you apprenticing at?",
            "max_length": "Please keep the company name under 120 characters.",
        },
        widget=forms.TextInput(
            attrs={
                **BLANK_WIDGET_ATTRS,
                "placeholder": "Acme",
                "autocomplete": "organization",
                "autocapitalize": "words",
            }
        ),
    )

    city = forms.CharField(
        label="Your town or city",
        max_length=80,
        error_messages={
            "required": "Which town or city are you based in?",
            "max_length": "Please keep the town or city under 80 characters.",
        },
        widget=forms.TextInput(
            attrs={
                **BLANK_WIDGET_ATTRS,
                "placeholder": "Manchester",
                "autocomplete": "address-level2",
                "autocapitalize": "words",
            }
        ),
    )

    country = forms.CharField(
        label="Your country",
        max_length=80,
        error_messages={
            "required": "And which country is that in?",
            "max_length": "Please keep the country under 80 characters.",
        },
        widget=forms.TextInput(
            attrs={
                **BLANK_WIDGET_ATTRS,
                "placeholder": "United Kingdom",
                "autocomplete": "country-name",
                "autocapitalize": "words",
            }
        ),
    )

    technologies = forms.CharField(
        label="Technologies you work with",
        required=False,
        widget=forms.TextInput(
            attrs={
                **BLANK_WIDGET_ATTRS,
                "class": "blank__input blank__input--tokens",
                "placeholder": "Python, SQL",
                "data-technologies-source": "",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )

    def clean_name(self):
        name = normalize_blank(self.cleaned_data["name"], "Let's start with your name.")
        if not HAS_LETTER.search(name):
            raise forms.ValidationError("Let's start with your name.")
        return name

    def clean_company(self):
        return normalize_blank(
            self.cleaned_data["company"], "Which company are you apprenticing at?"
        )

    def clean_city(self):
        return normalize_blank(
            self.cleaned_data["city"], "Which town or city are you based in?"
        )

    def clean_country(self):
        return normalize_blank(
            self.cleaned_data["country"], "And which country is that in?"
        )

    def clean_technologies(self):
        """Turn the free-text blank into a list of technology names."""
        tokens = split_technologies(self.cleaned_data.get("technologies", ""))

        if not tokens:
            raise forms.ValidationError(
                "Add at least one technology you work with — even a guess helps."
            )

        overlong = next(
            (token for token in tokens if len(token) > MAX_TECHNOLOGY_LENGTH), None
        )
        if overlong:
            raise forms.ValidationError(
                f"Keep each technology under {MAX_TECHNOLOGY_LENGTH} characters — "
                f'"{overlong[:MAX_TECHNOLOGY_LENGTH]}…" is too long.'
            )

        if len(tokens) > MAX_TECHNOLOGIES:
            raise forms.ValidationError(
                f"That's an impressive stack! Please narrow it down to your "
                f"{MAX_TECHNOLOGIES} main technologies."
            )

        return tokens


class WorkingHoursForm(forms.Form):
    """Step 2: the working day, and how much of it to keep free."""

    work_start = forms.TimeField(
        label="Your start time",
        error_messages={"required": "What time do you usually start work?"},
        widget=forms.TimeInput(
            format="%H:%M",
            # Django's TimeInput still renders type="text"; asking for the
            # native picker explicitly is what gets the mobile time wheel.
            attrs={"type": "time", "class": "blank__input blank__input--time"},
        ),
    )

    work_end = forms.TimeField(
        label="Your finish time",
        error_messages={"required": "What time do you usually finish work?"},
        widget=forms.TimeInput(
            format="%H:%M",
            attrs={"type": "time", "class": "blank__input blank__input--time"},
        ),
    )

    free_time_hours = forms.DecimalField(
        label="Free time you want each day",
        min_value=Decimal("0"),
        max_value=Decimal("24"),
        error_messages={
            "required": "How many hours a day would you like to keep free?",
            "invalid": "Give the free time as a number of hours, like 2 or 1.5.",
            "min_value": "Free time can't be negative.",
            "max_value": "There are only 24 hours in a day.",
        },
        widget=forms.NumberInput(
            attrs={
                "class": "blank__input blank__input--number",
                "step": "0.5",
                "min": "0",
                "max": "24",
                "inputmode": "decimal",
                "placeholder": "2",
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("work_start")
        end = cleaned.get("work_end")
        free = cleaned.get("free_time_hours")

        if start is None or end is None:
            return cleaned

        if start == end:
            self.add_error(
                "work_end", "Your finish time needs to be different from your start."
            )
            return cleaned

        # An earlier finish is read as a shift that runs past midnight.
        self.work_hours = hours_between(start, end)

        if free is not None:
            available = Decimal("24") - Decimal(str(self.work_hours))
            if free > available:
                # float() so 16.0 renders as "16" rather than Decimal's "16.0".
                self.add_error(
                    "free_time_hours",
                    f"You work {self.work_hours:g} hours that day, so at most "
                    f"{float(available):g} hours are left for everything else.",
                )
        return cleaned


class ChoiceSelect(forms.RadioSelect):
    """Radio buttons rendered as stacked, tappable choice cards."""

    template_name = "onboarding/_choice_group.html"
    option_template_name = "onboarding/_choice_option.html"


class QuizForm(forms.ModelForm):
    """Step 3: how the apprentice wants their 5-9 to look.

    The professional details (company, location, skills) are already collected
    in step 1, so they are deliberately absent here — the view copies them onto
    the profile so the planner's own copy stays in step.
    """

    weekly_tasks = forms.CharField(
        label="Your regular weekly tasks",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "field__input",
                "rows": 3,
                "placeholder": "e.g. food shop\nlaundry\nclean bathroom",
            }
        ),
        help_text="One per line — each becomes a household task.",
    )

    first_goal = forms.CharField(
        label="One headline goal",
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "field__input", "placeholder": "e.g. Run a 5k"}
        ),
        help_text="Your headline goal for the next few weeks.",
    )

    first_goal_category = forms.ChoiceField(
        label="Goal area",
        choices=Goal.CATEGORIES,
        initial="career",
        required=False,
        widget=forms.Select(attrs={"class": "field__input"}),
    )

    class Meta:
        model = UserProfile
        fields = [
            "person_type",
            "chronotype",
            "evenings_per_week",
            "minutes_per_evening",
            "social_balance",
            "task_style",
        ]
        widgets = {
            "person_type": ChoiceSelect,
            "chronotype": ChoiceSelect,
            "social_balance": ChoiceSelect,
            "task_style": ChoiceSelect,
            "evenings_per_week": forms.NumberInput(
                attrs={
                    "class": "field__input",
                    "min": "1",
                    "max": "7",
                    "inputmode": "numeric",
                }
            ),
            "minutes_per_evening": forms.NumberInput(
                attrs={
                    "class": "field__input",
                    "min": "15",
                    "max": "600",
                    "step": "15",
                    "inputmode": "numeric",
                }
            ),
        }
