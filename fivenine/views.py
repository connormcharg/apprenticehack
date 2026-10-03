import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import EnergyForm, EventForm, GoalForm, SignupForm, TaskForm
from .models import CommunityEvent, EnergyLog, EventAttendee, Goal, Task, UserProfile, display_name_for


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
        messages.success(request, 'Account created! Tell us about yourself.')
        return redirect('onboarding:about_you')
    return render(request, 'fivenine/signup.html', {'form': form})


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
        return 'Your energy has been low lately — keep tonight light, then rest.'
    return None


@login_required
def dashboard(request):
    """Home: today-only day view + capacity + energy check-in."""
    from datetime import timedelta as _td
    user = request.user
    today = timezone.now().date()
    selected = today

    if request.method == 'POST':
        eform = EnergyForm(request.POST)
        if eform.is_valid():
            entry = eform.save(commit=False)
            entry.user = user
            entry.save()
            messages.success(request, 'Energy logged.')
            return redirect('/home/')
    else:
        eform = EnergyForm(initial={'date': today, 'level': 3})

    hour = timezone.now().hour
    greeting = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 18 else 'Good evening'
    monday = selected - _td(days=selected.weekday())

    day_tasks = list(Task.objects.filter(user=user, done=False, due_date=selected).order_by('energy_cost'))
    day_events = list(CommunityEvent.objects.filter(date=selected))
    overdue = list(Task.objects.filter(user=user, done=False, due_date__lt=today).order_by('due_date'))

    slots = [{'css': f'slot-e-{e.kind}', 'title': e.title, 'time': '', 'event_id': e.pk,
              'meta': f'{e.get_kind_display()}' + (f' · {e.location}' if e.location else ''),
              'right': e.date.strftime('%a'), 'toggle': None} for e in day_events]
    slots += [{'css': f'slot-t-{t.kind}', 'title': t.title,
               'time': f'{t.start_time:%H:%M}' if t.start_time else '',
               'meta': f'{t.get_kind_display()} · {t.minutes} min' + (f' · {t.goal.title}' if t.goal else ''),
               'right': f'{t.minutes}m', 'toggle': t.pk} for t in day_tasks]
    slots.sort(key=lambda s: (s['time'] == '', s['time']))

    planned = sum(t.minutes for t in day_tasks)
    profile = get_profile(user)
    recent_energy = EnergyLog.objects.filter(user=user)[:3]
    warning = burnout_warning(user)

    # Week capacity + at-a-glance (mockup hero).
    week_end = monday + _td(days=6)
    week_tasks = Task.objects.filter(user=user, done=False, due_date__range=(monday, week_end))
    planned_week = sum(t.minutes for t in week_tasks)
    budget = (profile.minutes_per_evening * profile.evenings_per_week) if profile else 600
    cap_pct = min(100, round(100 * planned_week / budget)) if budget else 0
    ring_off = round(276.5 * (1 - cap_pct / 100))
    if cap_pct >= 90:
        cap_note = 'Busy week. Tonight stays light and Sunday is protected.'
    elif cap_pct >= 60:
        cap_note = 'Steady week. Evenings balanced around your energy.'
    else:
        cap_note = 'Light week. Good space to push a goal forward.'
    study_week = [t for t in week_tasks if t.kind == 'study']
    study_mins = sum(t.minutes for t in study_week)
    networking = CommunityEvent.objects.filter(
        date__gte=today, kind__in=['hackathon', 'multi-company', 'learning']).count()
    free_mins = max(0, budget - planned_week)
    work_info = apprentice_work_info(user)
    glance = [
        {'label': 'Work', 'value': work_info['value'], 'sub': work_info['sub']},
        {'label': 'University', 'value': f'{study_mins // 60}h{study_mins % 60 and f"{study_mins % 60}m" or ""}' if study_mins else '0h',
         'sub': f'{len(study_week)} sessions + study' if study_week else 'No study planned'},
        {'label': 'Career', 'value': str(networking),
         'sub': 'Networking opportunities' if networking else 'No events yet'},
        {'label': 'Free time', 'value': f'{free_mins // 60}h{free_mins % 60 and f"{free_mins % 60}m" or ""}',
         'sub': 'Protected by AI'},
    ]
    recs = recommend_events(user, 1)
    recommendation = {'event': recs[0][0], 'reason': recs[0][1]} if recs else None
    return render(request, 'fivenine/dashboard.html', {
        'greeting': greeting, 'name': display_name_for(user),
        'date_label': f'{selected:%A} · {selected.day} {selected:%B}'.upper(),
        'today': today, 'selected': selected,
        'slots': slots, 'overdue': overdue,
        'planned': planned, 'profile': profile,
        'eform': eform, 'recent_energy': recent_energy, 'warning': warning,
        'cap_pct': cap_pct, 'cap_note': cap_note, 'ring_off': ring_off, 'glance': glance,
        'recommendation': recommendation,
    })


def apprentice_work_info(user):
    """Work hours from the onboarding Apprentice profile, if set."""
    try:
        from onboarding.models import Apprentice
        ap = Apprentice.objects.filter(user=user).first()
        if ap is not None and ap.has_working_hours:
            hrs = (ap.work_hours() or 0) * 5
            return {'value': f'{hrs:g}h',
                    'sub': f"Mon–Fri · {ap.work_start:%H:%M}–{ap.work_end:%H:%M}"}
    except Exception:
        pass
    return {'value': '—', 'sub': 'Set hours in onboarding'}


@login_required
def goal_list(request):
    """Goals + tasks on one page, with progress bars and next steps."""
    from .models import goal_next_steps, goal_progress
    user = request.user
    goals = Goal.objects.filter(user=user).order_by('done', 'target_date')
    top_tasks = Task.objects.filter(user=user, parent__isnull=True).order_by('done', 'due_date').prefetch_related('subtasks')
    is_post = request.method == 'POST'
    form_type = request.POST.get('form_type', 'goal') if is_post else 'goal'
    goal_form = GoalForm(request.POST if is_post and form_type == 'goal' else None)
    task_form = TaskForm(request.POST if is_post and form_type == 'task' else None)
    task_form.fields['goal'].queryset = Goal.objects.filter(user=user, done=False)
    task_form.fields['parent'].queryset = Task.objects.filter(user=user, parent__isnull=True, done=False)
    if is_post:
        if form_type == 'task' and task_form.is_valid():
            task = task_form.save(commit=False)
            task.user = user
            task.save()
            return redirect('goal_list')
        elif form_type == 'goal' and goal_form.is_valid():
            goal = goal_form.save(commit=False)
            goal.user = user
            goal.save()
            return redirect('goal_list')
    cards = []
    for g in goals:
        done, total = goal_progress(g)
        cards.append({'goal': g, 'done': done, 'total': total,
                      'pct': round(100 * done / total) if total else 0,
                      'steps': goal_next_steps(g)})
    from datetime import timedelta as _td
    today = timezone.now().date()
    monday = today - _td(days=today.weekday())
    week_actions = Task.objects.filter(
        user=user, done=False, due_date__range=(monday, monday + _td(days=6))).order_by('due_date')
    return render(request, 'fivenine/goals.html',
                  {'cards': cards, 'top_tasks': top_tasks, 'week_actions': week_actions,
                   'goal_form': goal_form, 'task_form': task_form})


@login_required
def goal_toggle(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    goal.done = not goal.done
    goal.save()
    return redirect('goal_list')


@login_required
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.done = not task.done
    task.save()
    return redirect(request.GET.get('next', 'dashboard'))


@login_required
def task_detail(request, pk):
    """Google-calendar-style detail page: facts + editable notes."""
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        if 'toggle' in request.POST:
            task.done = not task.done
            task.save()
            return redirect('task_detail', pk=pk)
        task.title = request.POST.get('title', task.title).strip() or task.title
        try:
            task.minutes = max(5, int(request.POST.get('minutes', task.minutes)))
        except (TypeError, ValueError):
            pass
        task.due_date = request.POST.get('due_date') or None
        task.start_time = request.POST.get('start_time') or None
        task.notes = request.POST.get('notes', '')
        task.save()
        messages.success(request, 'Saved.')
        return redirect('task_detail', pk=pk)
    return render(request, 'fivenine/task_detail.html', {'task': task})


@login_required
def event_detail(request, pk):
    event = get_object_or_404(CommunityEvent, pk=pk)
    joined = EventAttendee.objects.filter(event=event, user=request.user).exists()
    return render(request, 'fivenine/event_detail.html', {
        'event': event, 'joined': joined,
        'members': event.attendees.select_related('user'),
    })


@login_required
def event_list(request):
    kind = request.GET.get('kind', '')
    events = CommunityEvent.objects.order_by('date').prefetch_related('attendees__user')
    if kind:
        events = events.filter(kind=kind)
    form = EventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event = form.save()
        EventAttendee.objects.get_or_create(event=event, user=request.user)
        return redirect('event_list')
    upcoming = events.filter(date__gte=timezone.now().date())
    my_ids = set(EventAttendee.objects.filter(user=request.user).values_list('event_id', flat=True))
    return render(request, 'fivenine/events.html', {
        'events': events, 'upcoming': upcoming, 'form': form,
        'active_kind': kind, 'kinds': CommunityEvent.KINDS,
        'recommended': recommend_events(request.user, 3), 'my_ids': my_ids,
    })


@login_required
def event_join(request, pk):
    event = get_object_or_404(CommunityEvent, pk=pk)
    EventAttendee.objects.get_or_create(event=event, user=request.user)
    return redirect(request.GET.get('next', 'event_list'))


@login_required
def event_leave(request, pk):
    EventAttendee.objects.filter(event_id=pk, user=request.user).delete()
    return redirect(request.GET.get('next', 'event_list'))


HOUSEHOLD_STARTERS = [
    ('shop', 'Food shop', 60, 2, 'Most apprentices do a big shop weekly.'),
    ('laundry', 'Laundry + put away', 40, 1, 'Small loads beat mountain day.'),
    ('bathroom', 'Clean bathroom', 30, 2, 'Twenty focused minutes does it.'),
    ('bins', 'Bins out + quick tidy', 20, 1, 'Tie it to bin day so you never miss it.'),
    ('cook', 'Meal-prep lunches', 60, 2, 'Cook once, eat cheap all week.'),
    ('reset', '15-minute reset', 15, 1, 'Low-energy friendly: one room, one timer.'),
]


@login_required
def household(request):
    """Household hub: open chores, recommendations, one-tap weekly planning."""
    from datetime import timedelta as _td
    user = request.user
    chores = Task.objects.filter(user=user, kind='chore').order_by('done', 'due_date')
    open_chores = chores.filter(done=False)

    if request.method == 'POST':
        if 'add' in request.POST:
            key = request.POST['add']
            match = next((s for s in HOUSEHOLD_STARTERS if s[0] == key), None)
            if match is not None and not Task.objects.filter(user=user, title__iexact=match[1]).exists():
                Task.objects.create(user=user, title=match[1], kind='chore',
                                    minutes=match[2], energy_cost=match[3])
                messages.success(request, f"Added '{match[1]}'.")
            return redirect('household')
        if 'plan' in request.POST:
            profile = get_profile(user)
            evenings = profile.evenings_per_week if profile else 4
            undated = list(open_chores.filter(due_date__isnull=True).order_by('energy_cost'))
            today = timezone.now().date()
            for i, chore in enumerate(undated):
                chore.due_date = today + _td(days=i % max(1, evenings))
                chore.save(update_fields=['due_date'])
            messages.success(request, f'Spread {len(undated)} chores across your evenings.')
            return redirect('household')

    known = ' '.join(t.title.lower() for t in open_chores)
    recent = EnergyLog.objects.filter(user=user).order_by('-date', '-created_at')[:3]
    low_energy = len(recent) >= 2 and sum(e.level for e in recent) / len(recent) <= 2.2
    suggestions = []
    for key, title, minutes, energy, reason in HOUSEHOLD_STARTERS:
        if key == 'reset' and not low_energy:
            continue
        if key != 'reset' and key in known:
            continue
        if Task.objects.filter(user=user, title__iexact=title).exists():
            continue
        suggestions.append({'key': key, 'title': title, 'minutes': minutes,
                            'energy': {1: 'Low', 2: 'Medium', 3: 'High'}[energy],
                            'reason': reason})
    undated_count = open_chores.filter(due_date__isnull=True).count()
    return render(request, 'fivenine/household.html', {
        'chores': chores, 'suggestions': suggestions, 'undated_count': undated_count,
    })


def recommend_events(user, limit=3):
    """Upcoming events scored by skill overlap + popularity. Returns [(event, reason)].
    Cached 15 min per user (locmem) so home + community pages stay cheap."""
    from django.core.cache import cache
    key = f'fivenine:recs:{user.id}:{limit}'
    hit = cache.get(key)
    if hit is not None:
        return hit
    profile = get_profile(user)
    skills = [s.strip().lower() for s in ((profile.skills or '') if profile else '').split(',') if s.strip()]
    upcoming = list(CommunityEvent.objects.filter(date__gte=timezone.now().date()).prefetch_related('attendees'))
    scored = []
    for e in upcoming:
        text = f'{e.title} {e.topic} {e.description}'.lower()
        hits = [s for s in skills if len(s) > 2 and s in text]
        members = e.attendees.count()
        score = 2 * len(hits) + min(members, 5) * 0.2 + (1 if e.kind in ('hackathon', 'multi-company') else 0)
        if hits:
            reason = f'Matches your interest in {hits[0]}'
        elif members:
            reason = f'{members} going'
        else:
            reason = 'New and upcoming'
        scored.append((score, e, reason))
    scored.sort(key=lambda x: -x[0])
    result = [(e, r) for _, e, r in scored[:limit]]
    cache.set(key, result, 900)
    return result


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
        if t.start_time:
            dt = f'{d}T{t.start_time:%H%M%S}'
            lines += ['BEGIN:VEVENT',
                f'UID:task-{t.pk}-{uid}@five-nine', f'DTSTAMP:{stamp}', f'DTSTART:{dt}',
                f'DURATION:PT{t.minutes}M',
                f'SUMMARY:{esc(t.title)} (5-9)',
                f'DESCRIPTION:{esc(t.get_kind_display())} · energy {t.energy_cost}', 'END:VEVENT']
        else:
            lines += ['BEGIN:VEVENT',
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
                             'reply': 'Log in first and I can see your goals, tasks and energy.'})
    if not settings.OPENROUTER_API_KEY:
        return JsonResponse({'error': 'no-key',
                             'reply': 'No OpenRouter key yet — copy .env.example to .env and add your OPENROUTER_API_KEY, then restart the server.'})
    reply, err = _assistant.chat([*history, {'role': 'user', 'content': message}], user=request.user)
    if err:
        return JsonResponse({'error': 'provider', 'reply': f'AI hiccup ({err}). Try again in a moment.'})
    return JsonResponse({'reply': reply})
