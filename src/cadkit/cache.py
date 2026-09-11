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
    cached = lru_cache(maxsize=128)(fn)

    @wraps(fn)
    def build(*args, **kwargs):
        return cached(
            *(_key(a) for a in args), **{k: _key(v) for k, v in kwargs.items()}
        )

    build.cache_clear = cached.cache_clear
    return build
