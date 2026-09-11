"""Degree-based geometry arithmetic. Model lengths are always millimetres."""

import math
from math import pi, sqrt, floor, ceil


class vec(tuple):
    """Immutable coordinate vector with elementwise arithmetic and stable cache keys."""

    def _op(self, other, op):
        if isinstance(other, (tuple, list)):
            if len(self) != len(other):
                raise ValueError("Vector dimensions must agree")
            return vec(op(a, b) for a, b in zip(self, other))
        return vec(op(a, other) for a in self)

    def __add__(self, other):
        return self._op(other, lambda a, b: a + b)

    def __sub__(self, other):
        return self._op(other, lambda a, b: a - b)

    def __mul__(self, other):
        return self._op(other, lambda a, b: a * b)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        return self._op(other, lambda a, b: a / b)

    def __neg__(self):
        return self * -1


def sin(angle):
    return math.sin(math.radians(angle))


def cos(angle):
    return math.cos(math.radians(angle))


def tan(angle):
    return math.tan(math.radians(angle))


def asin(value):
    return math.degrees(math.asin(value))


def acos(value):
    return math.degrees(math.acos(value))


def atan(value):
    return math.degrees(math.atan(value))


def atan2(y, x):
    return math.degrees(math.atan2(y, x))


def norm(value):
    return math.sqrt(sum(x * x for x in value))


def concat(*values):
    return vec(x for value in values for x in value)


def sign(value):
    return (value > 0) - (value < 0)


def require(condition, message="Design constraint violated"):
    if not condition:
        raise ValueError(message)


def inclusive_range(start, step_or_stop, stop=None):
    step, end = (1, step_or_stop) if stop is None else (step_or_stop, stop)
    if step == 0:
        raise ValueError("Range step cannot be zero")
    count = max(0, int(math.floor((end - start) / step + 1e-9)) + 1)
    return tuple(start + i * step for i in range(count))


def concat_text(*values):
    return "".join(str(value) for value in values)
