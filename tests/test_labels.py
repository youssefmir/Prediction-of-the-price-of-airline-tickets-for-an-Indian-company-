"""Tests des formats numériques à la française."""

from flight_prices.labels import fr, fr_pct


def test_fr_uses_narrow_spaces_and_decimal_comma():
    assert fr(12345.678, 1, "₹") == "12 345,7 ₹"


def test_fr_uses_a_true_minus_sign():
    assert fr(-3) == "−3"


def test_fr_pct():
    assert fr_pct(0.0686) == "6,9 %"
    assert fr_pct(0.115, signed=True) == "+11,5 %"
