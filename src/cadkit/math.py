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
    """Return the sin of an angle expressed in degrees."""
    return math.sin(math.radians(angle))


def cos(angle):
    """Return the cos of an angle expressed in degrees."""
    return math.cos(math.radians(angle))


def tan(angle):
    """Return the tan of an angle expressed in degrees."""
    return math.tan(math.radians(angle))


def asin(value):
    """Return inverse sin in degrees."""
    return math.degrees(math.asin(value))


def acos(value):
    """Return inverse cos in degrees."""
    return math.degrees(math.acos(value))


def atan(value):
    """Return inverse tan in degrees."""
    return math.degrees(math.atan(value))


def atan2(y, x):
    """Return the signed angle of `(x, y)` in degrees using the standard two-argument arctangent."""
    return math.degrees(math.atan2(y, x))


def norm(value):
    """Return Euclidean vector length in the input coordinate units."""
    return math.sqrt(sum(x * x for x in value))


def concat(*values):
    """Concatenate coordinate sequences into an immutable vec."""
    return vec(x for value in values for x in value)


def sign(value):
    """Return -1, 0, or 1 according to the sign of the input."""
    return (value > 0) - (value < 0)


def require(condition, message="Design constraint violated"):
    """Raise ValueError with the supplied message when a design constraint is false."""
    if not condition:
        raise ValueError(message)


def inclusive_range(start, step_or_stop, stop=None):
    """Return a tuple including the end when reached by the step. Use `(start, stop)` for step 1 or `(start, step, stop)` for an explicit nonzero step. Supports fractional and descending steps."""
    step, end = (1, step_or_stop) if stop is None else (step_or_stop, stop)
    if step == 0:
        raise ValueError("Range step cannot be zero")
    count = max(0, int(math.floor((end - start) / step + 1e-9)) + 1)
    return tuple(start + i * step for i in range(count))


def concat_text(*values):
    """Join string representations of all values without a separator."""
    return "".join(str(value) for value in values)
