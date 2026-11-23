"""Exact proportional allocation (largest remainder method), in whole grams.

Problem: split a sold lot of 1,000.000 kg among farmers who delivered 333, 333 and
334 kg. Naive rounding of each share can make the parts add up to 999.999 or
1,000.001 kg — a gram created or lost. Over thousands of farmers that drifts.

Solution:
1. Work in integer grams (no floating point at all).
2. Give everyone floor(total * weight / sum).
3. Hand the leftover grams, one each, to the largest fractional remainders
   (ties broken by position, so the result is deterministic and repeatable).
The parts ALWAYS sum exactly to the total.
"""
from decimal import ROUND_HALF_UP, Decimal

GRAMS = Decimal("1000")


def to_grams(kg: Decimal) -> int:
    return int((kg * GRAMS).to_integral_value(rounding=ROUND_HALF_UP))


def from_grams(g: int) -> Decimal:
    return (Decimal(g) / GRAMS).quantize(Decimal("0.001"))


def allocate(total: int, weights: list[int]) -> list[int]:
    """Split integer `total` proportionally to integer `weights`; parts sum to `total`."""
    if total < 0 or any(w < 0 for w in weights):
        raise ValueError("Negative values cannot be allocated")
    s = sum(weights)
    if s == 0:
        if total:
            raise ValueError("Cannot allocate a positive total over zero weights")
        return [0] * len(weights)
    base = [total * w // s for w in weights]
    remainders = [(total * w) % s for w in weights]
    leftover = total - sum(base)
    # indices sorted by largest remainder first, then by original position
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        base[i] += 1
    return base


def scale_grams(value: int, numerator: int, denominator: int) -> int:
    """round_half_up(value * numerator / denominator) using integers only."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    q, r = divmod(value * numerator, denominator)
    return q + (1 if 2 * r >= denominator else 0)
