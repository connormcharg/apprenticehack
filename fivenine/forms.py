from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CommunityEvent, EnergyLog, Goal, Task, UserProfile


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ('username',)


class EveningsForm(forms.ModelForm):
    """Step 3 of onboarding: how the 5-9 should work.
    Company/location/skills come from the onboarding profile, not asked twice."""
    weekly_tasks = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. food shop\nlaundry\nclean bathroom'}),
        help_text='One per line — each becomes a household task.')
    first_goal = forms.CharField(
        required=False, max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Run a 5k'}),
        help_text='Your headline goal for the next few weeks.')
    first_goal_category = forms.ChoiceField(choices=Goal.CATEGORIES, initial='career', required=False)

    class Meta:
        model = UserProfile
        fields = ['person_type', 'chronotype', 'evenings_per_week', 'minutes_per_evening',
                  'social_balance', 'task_style']
        widgets = {
            'person_type': forms.RadioSelect,
            'chronotype': forms.RadioSelect,
            'social_balance': forms.RadioSelect,
            'task_style': forms.RadioSelect,
        }


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['title', 'category', 'description', 'target_date']
        widgets = {'target_date': forms.DateInput(attrs={'type': 'date'})}


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'kind', 'goal', 'parent', 'minutes', 'energy_cost', 'due_date', 'start_time']
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'}),
                   'start_time': forms.TimeInput(attrs={'type': 'time'})}


class EnergyForm(forms.ModelForm):
    class Meta:
        model = EnergyLog
        fields = ['date', 'level', 'note']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class EventForm(forms.ModelForm):
    class Meta:
        model = CommunityEvent
        fields = ['title', 'kind', 'topic', 'date', 'location', 'description']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}
