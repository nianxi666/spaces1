"""
Shared defaults and helpers for NetMind configuration.
"""

DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS = 30


def sanitize_rate_limit_window(value, fallback=None):
    """
    Ensures the window duration is a positive integer (seconds).
    """
    if fallback is None:
        fallback = DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(1, parsed)


def sanitize_rate_limit_max_requests(value, fallback=None):
    """
    Ensures the request cap is a non-negative integer.
    """
    if fallback is None:
        fallback = DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, parsed)


def get_rate_limit_config(settings=None):
    """
    Returns a tuple of (max_requests, window_seconds) using defaults when unset.
    """
    settings = settings or {}
    window = sanitize_rate_limit_window(settings.get('rate_limit_window_seconds'))
    max_requests = sanitize_rate_limit_max_requests(settings.get('rate_limit_max_requests'))
    return max_requests, window
