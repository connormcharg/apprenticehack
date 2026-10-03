import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db.models import Avg
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import EnergyForm, EventForm, GoalForm, PlanForm, QuizForm, SignupForm, TaskForm
from .models import CommunityEvent, EnergyLog, Goal, Task, UserProfile


def manifest(request):
    path = finders.find('fivenine/manifest.webmanifest')
    return FileResponse(open(path, 'rb'), content_type='application/manifest+json')


def service_worker(request):
    path = finders.find('fivenine/sw.js')
    return FileResponse(open(path, 'rb'), content_type='application/javascript')


# ---------- auth + quiz ----------

def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Account created! Quick quiz so we can tailor your 5-9. 🌙')
        return redirect('quiz')
    return render(request, 'fivenine/signup.html', {'form': form})


@login_required
def quiz(request):
    """First-login quiz: person type + time commitment + company/skills/location."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = QuizForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        profile = form.save(commit=False)
        profile.quiz_done = True
        profile.save()
        messages.success(request, 'All set! Here is your 5-9. 🌙')
        return redirect('dashboard')
    return render(request, 'fivenine/quiz.html', {'form': form})


def needs_quiz(user):
    return not UserProfile.objects.filter(user=user, quiz_done=True).exists()


def get_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


# ---------- app views (login required, per-user data) ----------

def burnout_warning(user):
    """Return warning string if recent energy is low, else None."""
    recent = EnergyLog.objects.filter(user=user).order_by('-date', '-created_at')[:3]
    if len(recent) < 2:
        return None
    avg = sum(e.level for e in recent) / len(recent)
    if avg <= 2.2:
        return 'Your energy has been low lately — tonight is capped at something light + rest.'
    return None


@login_required
def dashboard(request):
    if needs_quiz(request.user):
        return redirect('quiz')
    user = request.user
    profile = get_profile(user)
    goals = Goal.objects.filter(user=user, done=False).order_by('target_date')[:6]
    tasks = Task.objects.filter(user=user, done=False).order_by('due_date')[:8]
    energy = EnergyLog.objects.filter(user=user).first()
    events = CommunityEvent.objects.filter(date__gte=timezone.now().date()).order_by('date')[:5]
    warning = burnout_warning(user)
    feed_url = request.build_absolute_uri(f'/calendar/feed-{profile.calendar_token}.ics') if profile else None
    return render(request, 'fivenine/dashboard.html', {
        'goals': goals, 'tasks': tasks, 'energy': energy,
        'events': events, 'warning': warning, 'profile': profile, 'feed_url': feed_url,
    })


@login_required
def goal_list(request):
    goals = Goal.objects.filter(user=request.user).order_by('done', 'target_date')
    form = GoalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        goal = form.save(commit=False)
        goal.user = request.user
        goal.save()
        return redirect('goal_list')
    return render(request, 'fivenine/goals.html', {'goals': goals, 'form': form})


@login_required
def goal_toggle(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    goal.done = not goal.done
    goal.save()
    return redirect('goal_list')


@login_required
def task_list(request):
    tasks = Task.objects.filter(user=request.user).order_by('done', 'due_date')
    form = TaskForm(request.POST or None)
    form.fields['goal'].queryset = Goal.objects.filter(user=request.user, done=False)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        return redirect('task_list')
    return render(request, 'fivenine/tasks.html', {'tasks': tasks, 'form': form})


@login_required
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.done = not task.done
    task.save()
    return redirect(request.GET.get('next', 'task_list'))


@login_required
def energy_log(request):
    logs = EnergyLog.objects.filter(user=request.user)[:14]
    avg = EnergyLog.objects.filter(user=request.user).aggregate(Avg('level'))['level__avg']
    form = EnergyForm(request.POST or None, initial={'date': timezone.now().date(), 'level': 3})
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.user = request.user
        entry.save()
        return redirect('energy_log')
    return render(request, 'fivenine/energy.html', {'logs': logs, 'form': form, 'avg': avg})


def build_plan(user, minutes_available, energy_level):
    """Energy-aware planner, personalised: task_style caps item count."""
    profile = get_profile(user)
    max_items = 2 if profile and profile.task_style == 'few_big' else 4
    qs = Task.objects.filter(user=user, done=False)
    if energy_level <= 2:
        qs = qs.filter(energy_cost=1)
        cap = min(minutes_available, 60)
    elif energy_level == 3:
        qs = qs.filter(energy_cost__lte=2)
        cap = min(minutes_available, 120)
    else:
        cap = minutes_available
    qs = qs.order_by('due_date', 'energy_cost')
    picked, total = [], 0
    for task in qs:
        if total + task.minutes <= cap:
            picked.append(task)
            total += task.minutes
        if len(picked) >= max_items or total >= cap:
            break
    return picked, total, cap


@login_required
def evening_plan(request):
    profile = get_profile(request.user)
    default_minutes = profile.minutes_per_evening if profile else 120
    form = PlanForm(request.GET or None, initial={'minutes_available': default_minutes, 'energy': '3'})
    picked, total, cap, warning = [], 0, 0, burnout_warning(request.user)
    if form.is_valid():
        minutes_available = form.cleaned_data['minutes_available']
        energy_level = int(form.cleaned_data['energy'])
        picked, total, cap = build_plan(request.user, minutes_available, energy_level)
        if energy_level <= 2 and not any(t.kind == 'rest' for t in picked):
            warning = (warning or '') + ' Add a rest block — wind down, no screens for 30m.'
    return render(request, 'fivenine/plan.html', {
        'form': form, 'picked': picked, 'total': total, 'cap': cap, 'warning': warning,
        'profile': profile,
    })


@login_required
def event_list(request):
    kind = request.GET.get('kind', '')
    events = CommunityEvent.objects.order_by('date')
    if kind:
        events = events.filter(kind=kind)
    form = EventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('event_list')
    upcoming = events.filter(date__gte=timezone.now().date())
    return render(request, 'fivenine/events.html', {
        'events': events, 'upcoming': upcoming, 'form': form,
        'active_kind': kind, 'kinds': CommunityEvent.KINDS,
    })


@login_required
def calendar_view(request):
    """Month grid: your tasks (by due_date) + community events."""
    import calendar as calmod
    from datetime import date
    today = timezone.now().date()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        date(year, month, 1)
    except ValueError:
        year, month = today.year, today.month
    prev_month = month - 1 or 12
    prev_year = year - (1 if month == 1 else 0)
    next_month = month + 1 if month < 12 else 1
    next_year = year + (1 if month == 12 else 0)

    tasks_by_day, events_by_day = {}, {}
    for t in Task.objects.filter(user=request.user, due_date__year=year, due_date__month=month):
        tasks_by_day.setdefault(t.due_date.day, []).append(t)
    for e in CommunityEvent.objects.filter(date__year=year, date__month=month):
        events_by_day.setdefault(e.date.day, []).append(e)

    weeks = []
    for week in calmod.Calendar(firstweekday=0).monthdayscalendar(year, month):
        days = []
        for day in week:
            days.append({
                'day': day,
                'tasks': tasks_by_day.get(day, []),
                'events': events_by_day.get(day, []),
                'is_today': day == today.day and month == today.month and year == today.year,
            })
        weeks.append(days)
    profile = get_profile(request.user)
    feed_url = request.build_absolute_uri(f'/calendar/feed-{profile.calendar_token}.ics') if profile else None
    return render(request, 'fivenine/calendar.html', {
        'year': year, 'month': month, 'month_name': calmod.month_name[month],
        'weeks': weeks, 'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month, 'feed_url': feed_url,
    })


def ics_feed(request, token):
    """Per-user iCal feed (secret URL) — subscribe in Google/Apple Calendar.
    Includes your tasks with due dates + all community events."""
    from datetime import datetime
    profile = get_object_or_404(UserProfile, calendar_token=token)
    user = profile.user
    stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//5-9 Planner//EN', 'CALSCALE:GREGORIAN',
             'X-WR-CALNAME:5-9 Planner']
    uid = 0

    def esc(text):
        return text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')

    for t in Task.objects.filter(user=user, done=False, due_date__isnull=False):
        uid += 1
        d = t.due_date.strftime('%Y%m%d')
        lines += [ 'BEGIN:VEVENT',
            f'UID:task-{t.pk}-{uid}@five-nine', f'DTSTAMP:{stamp}', f'DTSTART;VALUE=DATE:{d}',
            f'SUMMARY:{esc(t.title)} (5-9: {t.minutes}m)',
            f'DESCRIPTION:{esc(t.get_kind_display())} · energy {t.energy_cost}', 'END:VEVENT']
    for e in CommunityEvent.objects.all():
        uid += 1
        d = e.date.strftime('%Y%m%d')
        lines += ['BEGIN:VEVENT',
            f'UID:event-{e.pk}-{uid}@five-nine', f'DTSTAMP:{stamp}', f'DTSTART;VALUE=DATE:{d}',
            f'SUMMARY:{esc(e.title)} [{e.get_kind_display()}]',
            f'DESCRIPTION:{esc(e.description)}' + (f'\\n{esc(e.location)}' if e.location else ''),
            ('LOCATION:' + esc(e.location)) if e.location and not e.location.startswith('http') else 'TRANSP:TRANSPARENT',
            'END:VEVENT']
    lines.append('END:VCALENDAR')
    return HttpResponse('\r\n'.join(lines), content_type='text/calendar')


@login_required
def assistant_page(request):
    return render(request, 'fivenine/assistant.html', {
        'has_key': bool(settings.OPENROUTER_API_KEY),
    })


@csrf_exempt
def assistant_api(request):
    """POST JSON {message, history:[{role,content}]} -> {reply} or {error}."""
    from django.http import JsonResponse

    from . import assistant as _assistant

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    message = (data.get('message') or '').strip()
    if not message:
        return JsonResponse({'error': 'Empty message'}, status=400)
    history = [m for m in data.get('history', []) if m.get('role') in ('user', 'assistant') and m.get('content')][:10]
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login',
                             'reply': 'Log in first and I can see your goals, tasks and energy. 🔑'})
    if not settings.OPENROUTER_API_KEY:
        return JsonResponse({'error': 'no-key',
                             'reply': 'No OpenRouter key yet — copy .env.example to .env and add your OPENROUTER_API_KEY, then restart the server.'})
    reply, err = _assistant.chat([*history, {'role': 'user', 'content': message}], user=request.user)
    if err:
        return JsonResponse({'error': 'provider', 'reply': f'AI hiccup ({err}). Try again in a moment.'})
    return JsonResponse({'reply': reply})
