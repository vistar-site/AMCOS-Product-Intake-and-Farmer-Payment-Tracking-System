"""Unit tests for the allocation maths (no database needed)."""
from decimal import Decimal

import pytest

from app.services.allocation import allocate, from_grams, scale_grams, to_grams


def test_parts_always_sum_to_total():
    parts = allocate(1_000_000, [333_000, 333_000, 334_000])
    assert sum(parts) == 1_000_000
    assert parts == [333_000, 333_000, 334_000]


def test_remainder_goes_to_largest_fraction():
    # 10 g split three ways equally: 3,3,3 + 1 leftover to the first (tie -> position)
    assert allocate(10, [1, 1, 1]) == [4, 3, 3]
    # 100 g over weights 1,2: exact thirds = 33.33 / 66.67 -> 33 / 67
    assert allocate(100, [1, 2]) == [33, 67]


@pytest.mark.parametrize("n", [1, 7, 97, 1000])
def test_many_farmers_no_drift(n):
    weights = [((i * 7919) % 50_000) + 1 for i in range(n)]
    total = 4_321_987
    parts = allocate(total, weights)
    assert sum(parts) == total
    assert all(p >= 0 for p in parts)


def test_zero_weights():
    assert allocate(0, [0, 0]) == [0, 0]
    with pytest.raises(ValueError):
        allocate(5, [0, 0])


def test_gram_conversion_and_scaling():
    assert to_grams(Decimal("82.5")) == 82_500
    assert from_grams(82_500) == Decimal("82.500")
    assert scale_grams(950_000, 1_000_000, 950_000) == 1_000_000   # absorbed: sold 950 of 950 accepted -> 1000 delivered
    assert scale_grams(1, 1, 2) == 1                                # half rounds up
