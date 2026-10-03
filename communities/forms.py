"""Forms for creating communities, their events and chat messages.

The community's technologies blank is posted as free text and parsed with the
same helper onboarding uses, so "Python, SQL and React" means the same thing in
both places and the two features share one ``Technology`` table.
"""

from django import forms

from onboarding.forms import split_technologies

from .models import Community, Event, Message


class CommunityForm(forms.ModelForm):
    """Create a community, described by the onboarding profile fields."""

    technologies = forms.CharField(
        label="Technologies",
        required=False,
        help_text="Comma-separated, e.g. Python, SQL, React.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Python, SQL",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )

    class Meta:
        model = Community
        fields = ["name", "description", "company", "city", "country"]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What is this community for?"}
            ),
            "company": forms.TextInput(attrs={"placeholder": "Acme"}),
            "city": forms.TextInput(attrs={"placeholder": "Manchester"}),
            "country": forms.TextInput(attrs={"placeholder": "United Kingdom"}),
        }

    def clean_technologies(self):
        return split_technologies(self.cleaned_data.get("technologies", ""))


class EventForm(forms.ModelForm):
    """Organise a meet-up inside a community."""

    class Meta:
        model = Event
        fields = ["title", "kind", "topic", "description", "starts_at", "location"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "topic": forms.TextInput(
                attrs={"placeholder": "e.g. cybersecurity, climbing, CV help"}
            ),
            "location": forms.TextInput(attrs={"placeholder": "Place or link"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # datetime-local posts "2026-10-03T18:30"; accept exactly that.
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]


class MessageForm(forms.ModelForm):
    """A single chat message."""

    class Meta:
        model = Message
        fields = ["body"]
        widgets = {
            "body": forms.TextInput(
                attrs={"placeholder": "Say something…", "autocomplete": "off"}
            )
        }
