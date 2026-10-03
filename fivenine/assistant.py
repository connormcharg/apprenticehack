"""AI assistant backed by OpenRouter (free-tier friendly).

No third-party HTTP dependency — uses stdlib urllib so requirements.txt stays lean.
Configure via OPENROUTER_API_KEY in .env (see .env.example).
"""
import json
import re
import urllib.request

from django.conf import settings


ACTION_SPEC = """You can also DO things, not just talk. To create or complete something, end your reply with one fenced block per action:
```action {"op": "create_goal", "title": "Run 5k", "category": "health"}
Valid ops and fields (dates YYYY-MM-DD, times HH:MM 24h):
- {"op": "create_goal", "title": "...", "category": "health|study|career|money|social|home", "target_date": "2026-11-01"}
- {"op": "create_task", "title": "...", "kind": "goal|chore|study|rest|social", "minutes": 30, "energy_cost": 1, "due_date": "2026-10-04", "start_time": "18:30", "goal_title": "Run 5k"}
- {"op": "create_subtask", "parent_task_title": "...", "title": "...", "minutes": 20}
- {"op": "create_event", "title": "...", "kind": "hackathon|social|multi-company|learning", "date": "2026-10-09", "location": "...", "topic": "...", "description": "..."}
- {"op": "complete_task", "title": "..."}
Rules: only use actions the user actually asked for (creating, adding, booking, done/finished). Resolve relative dates yourself ("tomorrow", "Thursday", "at 6:30pm"). Keep the visible reply short and confirm what you did in words too.
Bias to action: if the user states something they are doing or want tracked ("tennis tomorrow 6:30", "remind me to...", "my goal is to..."), create it IMMEDIATELY and confirm — never ask "want me to add it?".
Personal activities (tennis, gym, dinner, studying) are create_task; organised group things (meetups, hackathons, societies) are create_event.
"""

SYSTEM_PROMPT = """You are the 5-9 Planner buddy for apprentices — life AFTER work/uni (roughly 5-9pm).
Help the user organise their tools: goals, household tasks, study, energy/burnout guard, evening plans, and community events.

Rules:
- Be short, warm, practical. Max ~120 words unless they ask for detail.
- Write in plain English: short sentences (under 20 words), simple everyday words, active voice ("you can…", not "it can be done"), no jargon. If you must use a tricky word, explain it.
- Respect low energy: if their energy is low, suggest light tasks + rest, never hustle.
- When suggesting a plan, reference their actual tasks/goals by name.
- Never invent tasks or events they don't have; only use the context given.
- Format for a chat bubble (HTML is NOT supported — it will be stripped):
  plain text only, short lines, blank line between ideas, "- " for lists, **bold** for task names at most.
  No headings, no tables, no code blocks, no emojis, max 1 list per reply.
"""


def user_context_summary(user=None):
    """Summarise the user's current state for the system prompt (lazy imports avoid cycles)."""
    from django.utils import timezone
    from .models import CommunityEvent, EnergyLog, Goal, Task

    if user is not None and user.is_authenticated:
        goals = list(Goal.objects.filter(user=user, done=False).order_by('target_date')[:8])
        tasks = list(Task.objects.filter(user=user, done=False).order_by('due_date')[:15])
        energy = EnergyLog.objects.filter(user=user).first()
        try:
            p = user.profile
            prof = (f'{p.get_person_type_display()}, {p.get_chronotype_display()}, '
                    f'{p.evenings_per_week} evenings/week x {p.minutes_per_evening}min, '
                    f'{p.get_social_balance_display()}, {p.get_task_style_display()}'
                    + (f', {p.company}' if p.company else '')
                    + (f', {p.location}' if p.location else '')
                    + (f', skills: {p.skills}' if p.skills else ''))
        except Exception:
            prof = 'quiz not completed yet'
    else:
        goals, tasks, energy, prof = [], [], None, 'unknown (not logged in)'
    events = list(CommunityEvent.objects.filter(date__gte=timezone.now().date()).order_by('date')[:8])

    lines = []
    lines.append('Open goals: ' + ('; '.join(f'{g.title} [{g.get_category_display()}]' for g in goals) if goals else 'none'))
    lines.append('Open tasks: ' + ('; '.join(
        f'{t.title} ({t.get_kind_display()}, {t.minutes}m, energy {t.energy_cost}' +
        (f', due {t.due_date}' if t.due_date else '') + ')' for t in tasks) if tasks else 'none'))
    lines.append(f'Latest energy: {energy.level}/5 on {energy.date}' + (f' ({energy.note})' if energy and energy.note else '') if energy else 'Latest energy: not logged yet')
    lines.append('Upcoming events: ' + ('; '.join(f'{e.title} ({e.get_kind_display()}, {e.date})' for e in events) if events else 'none'))
    lines.append('Person profile: ' + prof)
    return '\n'.join(lines)


def chat(messages, user=None):
    """Send messages to OpenRouter. Returns (reply_text, error_text)."""
    from django.utils import timezone
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        return None, 'no-key'
    today = timezone.now().date()
    system = (SYSTEM_PROMPT + '\n\n' + ACTION_SPEC
              + f'\nToday is {today:%A %Y-%m-%d}.'
              + '\n\nLive user context:\n' + user_context_summary(user))
    payload = {
        'model': settings.OPENROUTER_MODEL,
        'messages': [{'role': 'system', 'content': system}, *messages],
        'max_tokens': 800,
        'temperature': 0.3,
    }
    req = urllib.request.Request(
        f'{settings.OPENROUTER_BASE_URL}/chat/completions',
        data=json.dumps(payload).encode(),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'http://localhost:8000',
            'X-Title': settings.OPENROUTER_APP_NAME,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:  # network / 401 / rate-limit etc.
        return None, str(exc)
    try:
        raw = data['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, AttributeError):
        return None, f'Unexpected response: {str(data)[:200]}'
    if user is not None and user.is_authenticated:
        raw = apply_actions(user, raw)
    return raw, None


ACTION_RE = re.compile(r'```action\b(.*?)```', re.DOTALL)


def _parse_date(s):
    from datetime import date
    try:
        return date.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None


def _parse_time(s):
    from datetime import datetime
    try:
        return datetime.strptime(str(s).strip(), '%H:%M').time()
    except (ValueError, TypeError):
        return None


def _find_task(user, title):
    from .models import Task
    qs = Task.objects.filter(user=user, title__icontains=title).order_by('done', 'due_date')
    return qs.first()


def _find_goal(user, title):
    from .models import Goal
    return Goal.objects.filter(user=user, title__icontains=title).order_by('done').first()


def apply_actions(user, reply):
    """Execute ```action {...}``` blocks in the model reply against the user's data.
    Returns the reply with blocks replaced by human confirmations."""
    from .models import CommunityEvent, EventAttendee, Goal, Task

    notes = []

    def run(op):
        kind = op.get('op')
        if kind == 'create_goal':
            title = (op.get('title') or '').strip()
            if not title:
                return "Couldn't create a goal with no title."
            cat = op.get('category') if op.get('category') in dict(Goal.CATEGORIES) else 'career'
            goal = Goal.objects.filter(user=user, title__iexact=title).first()
            if goal is None:
                goal = Goal.objects.create(user=user, title=title, category=cat,
                                           target_date=_parse_date(op.get('target_date')))
                return f"Created goal '{goal.title}'."
            return f"Goal '{goal.title}' already exists."
        if kind == 'create_task':
            title = (op.get('title') or '').strip()
            if not title:
                return "Couldn't create a task with no title."
            tkind = op.get('kind') if op.get('kind') in dict(Task.KINDS) else 'goal'
            try:
                minutes = max(5, int(op.get('minutes', 30)))
            except (TypeError, ValueError):
                minutes = 30
            energy = op.get('energy_cost', 2)
            energy = energy if energy in (1, 2, 3) else 2
            goal = _find_goal(user, op.get('goal_title', '')) if op.get('goal_title') else None
            task = Task.objects.create(user=user, title=title, kind=tkind, minutes=minutes,
                                       energy_cost=energy, due_date=_parse_date(op.get('due_date')),
                                       start_time=_parse_time(op.get('start_time')), goal=goal)
            when = f' for {task.due_date}' + (f' at {task.start_time:%H:%M}' if task.start_time else '') if task.due_date else ''
            return f"Added '{task.title}'{when}."
        if kind == 'create_subtask':
            parent = _find_task(user, op.get('parent_task_title', ''))
            title = (op.get('title') or '').strip()
            if parent is None:
                return f"Couldn't find a task matching '{op.get('parent_task_title', '')}'."
            if not title:
                return "Couldn't create a sub-task with no title."
            try:
                minutes = max(5, int(op.get('minutes', 20)))
            except (TypeError, ValueError):
                minutes = 20
            Task.objects.create(user=user, parent=parent, title=title, kind=parent.kind,
                                minutes=minutes, energy_cost=parent.energy_cost, goal=parent.goal)
            return f"Added sub-task '{title}' under '{parent.title}'."
        if kind == 'create_event':
            title = (op.get('title') or '').strip()
            day = _parse_date(op.get('date'))
            if not title or not day:
                return "Couldn't create that event — I need a name and a date."
            ekind = op.get('kind') if op.get('kind') in dict(CommunityEvent.KINDS) else 'social'
            event = CommunityEvent.objects.filter(title__iexact=title, date=day).first()
            created = event is None
            if created:
                event = CommunityEvent.objects.create(
                    title=title, kind=ekind, date=day, location=op.get('location', ''),
                    topic=op.get('topic', ''), description=op.get('description', ''))
            EventAttendee.objects.get_or_create(event=event, user=user)
            return f"Added event '{event.title}' on {event.date} — you're on the list." if created else f"Event '{event.title}' already exists — you're on the list."
        if kind == 'complete_task':
            task = Task.objects.filter(user=user, done=False, title__icontains=op.get('title', '')).order_by('due_date').first()
            if task is None:
                return f"Couldn't find an open task matching '{op.get('title', '')}'."
            task.done = True
            task.save()
            return f"Marked '{task.title}' done."
        return f"Ignored unknown action '{kind}'."

    def replace(match):
        try:
            op = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            notes.append('Ignored a malformed action.')
            return ''
        notes.append(run(op) if isinstance(op, dict) else 'Ignored a malformed action.')
        return ''

    clean = ACTION_RE.sub(replace, reply).strip()
    # Tolerate a block cut off by the token limit (no closing fence).
    m = re.search(r'```action\b(.*)$', clean, re.DOTALL)
    if m:
        try:
            op = json.loads(m.group(1).strip().rstrip('`').strip())
            notes.append(run(op) if isinstance(op, dict) else 'Ignored a malformed action.')
        except json.JSONDecodeError:
            notes.append('I started adding that but got cut off — please say it again briefly.')
        clean = clean[:m.start()].strip()
    if notes:
        clean = (clean + '\n' + '\n'.join(f'- {n}' for n in notes)).strip()
    return clean or '\n'.join(f'- {n}' for n in notes)
