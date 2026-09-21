"""Bounded memoization for expensive pure geometry builders."""

from functools import lru_cache, wraps
from .math import vec


def _key(value):
    if isinstance(value, (list, tuple)):
        return vec(_key(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _key(v)) for k, v in value.items()))
    return value


def memoize_shape(fn):
    """Cache up to 128 argument combinations of a pure geometry builder.

    Args:
        fn (Callable): Builder whose output depends only on explicit arguments.

    Returns:
        (Callable): Decorated builder with a `cache_clear()` method. Nested lists
            and dictionaries are converted to stable hashable keys.

    The cached object itself is returned, not a copy. Do not mutate it. Changing
    module globals does not invalidate entries; pass design inputs explicitly
    or call `cache_clear()` after changing them.
    """
    cached = lru_cache(maxsize=128)(fn)

    @wraps(fn)
    def build(*args, **kwargs):
        return cached(
            *(_key(a) for a in args), **{k: _key(v) for k, v in kwargs.items()}
        )

    build.cache_clear = cached.cache_clear
    return build
