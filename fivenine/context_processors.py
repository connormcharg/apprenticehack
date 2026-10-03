"""Makes {{ display_name }} available in every fivenine template."""


def display_name(request):
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        from .models import display_name_for
        return {'display_name': display_name_for(user)}
    return {}
