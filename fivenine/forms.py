from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import EnergyLog, Goal, Task


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
        fields = ['title', 'kind', 'goal', 'minutes', 'energy_cost', 'due_date', 'start_time']
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'}),
                   'start_time': forms.TimeInput(attrs={'type': 'time'})}


class EnergyForm(forms.ModelForm):
    class Meta:
        model = EnergyLog
        fields = ['date', 'level', 'note']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}
