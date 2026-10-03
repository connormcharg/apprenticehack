from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CommunityEvent, EnergyLog, Goal, Task


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ('username',)


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


class PlanForm(forms.Form):
    minutes_available = forms.IntegerField(min_value=15, max_value=300, initial=120, label='Minutes tonight')
    energy = forms.ChoiceField(
        choices=[('1', 'Drained'), ('2', 'Low'), ('3', 'OK'), ('4', 'Good'), ('5', 'Great')],
        initial='3',
    )
