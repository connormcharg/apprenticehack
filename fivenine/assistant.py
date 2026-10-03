"""AI assistant backed by OpenRouter (free-tier friendly).

No third-party HTTP dependency — uses stdlib urllib so requirements.txt stays lean.
Configure via OPENROUTER_API_KEY in .env (see .env.example).
"""
import json
import urllib.request

from django.conf import settings


SYSTEM_PROMPT = """You are the 5-9 Planner buddy for apprentices — life AFTER work/uni (roughly 5-9pm).
Help the user organise their tools: goals, household tasks, study, energy/burnout guard, evening plans, and community events.

Rules:
- Be short, warm, practical. Max ~120 words unless they ask for detail.
- Respect low energy: if their energy is low, suggest light tasks + rest, never hustle.
- When suggesting a plan, reference their actual tasks/goals by name.
- You can suggest creating goals/tasks/events — tell them which page to use.
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
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        return None, 'no-key'
    payload = {
        'model': settings.OPENROUTER_MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT + '\n\nLive user context:\n' + user_context_summary(user)},
            *messages,
        ],
        'max_tokens': 500,
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
        return data['choices'][0]['message']['content'].strip(), None
    except (KeyError, IndexError, AttributeError):
        return None, f'Unexpected response: {str(data)[:200]}'
