"""Failed sign-in counting and lockout for the Django Admin and API logins (audit findings M1, L4).

Failures are recorded from Django's ``user_login_failed`` signal, so every login path that uses
``authenticate()`` is counted. After MAX_FAILURES failures inside WINDOW_SECONDS, further attempts
are refused (HTTP 429) until the window passes:
  * per username: rotating IP addresses does not help an attacker (L4);
  * per client IP: the admin login cannot be hammered across many usernames (M1).

Counters live in Django's cache. The default local-memory cache is per process and resets on
restart; configure a shared cache (e.g. Redis or the database cache) before running several workers.
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse

MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60
BLOCKED_MESSAGE = 'Too many failed sign-in attempts. Try again in 15 minutes.'


def _username_key(username):
    return f'login-failures:user:{(username or "").strip().lower()}'


def _ip_key(request):
    return f'login-failures:ip:{request.META.get("REMOTE_ADDR", "unknown")}'


def _bump(key):
    try:
        cache.add(key, 0, WINDOW_SECONDS)
        cache.incr(key)
    except ValueError:  # key expired between add() and incr()
        cache.set(key, 1, WINDOW_SECONDS)


def record_failure(sender, credentials=None, request=None, **kwargs):
    """Receiver for ``user_login_failed``."""
    username = (credentials or {}).get('username')
    if username:
        _bump(_username_key(username))
    if request is not None:
        _bump(_ip_key(request))


def clear_username(sender, request=None, user=None, **kwargs):
    """Receiver for ``user_logged_in``: a successful sign-in resets that account's counter."""
    if user is not None:
        cache.delete(_username_key(user.get_username()))


def username_blocked(username):
    return cache.get(_username_key(username), 0) >= MAX_FAILURES


def ip_blocked(request):
    return cache.get(_ip_key(request), 0) >= MAX_FAILURES


def throttled_admin_login(login_view):
    """Wrap AdminSite.login so blocked usernames or client IPs get 429 before any password check."""
    @wraps(login_view)
    def wrapper(request, *args, **kwargs):
        if request.method == 'POST' and (ip_blocked(request) or username_blocked(request.POST.get('username'))):
            return HttpResponse(BLOCKED_MESSAGE, status=429, content_type='text/plain; charset=utf-8')
        return login_view(request, *args, **kwargs)
    return wrapper
