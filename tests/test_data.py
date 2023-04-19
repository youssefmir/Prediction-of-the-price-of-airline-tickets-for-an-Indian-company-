"""Tests du chargement et du nettoyage des données."""

import pytest

from flight_prices.data import clean, economy_only, load_raw, parse_duration, split_airline_cabin


@pytest.mark.parametrize(
    ("text", "minutes"), [("2h 50m", 170), ("19h", 1140), ("5m", 5), ("47h 40m", 2860)]
)
def test_parse_duration(text, minutes):
    assert parse_duration(text) == minutes


def test_parse_duration_rejects_unknown_format():
    with pytest.raises(ValueError):
        parse_duration("2 hours")


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Jet Airways Business", ("Jet Airways", "Business")),
        ("Vistara Premium economy", ("Vistara", "Premium economy")),
        ("IndiGo", ("IndiGo", "Economy")),
    ],
)
def test_split_airline_cabin(label, expected):
    assert split_airline_cabin(label) == expected


@pytest.fixture(scope="module")
def cleaned():
    return clean(load_raw())


def test_cleaning_steps(cleaned):
    tidy, report = cleaned
    assert [removed for _, removed, _ in report.steps] == [1, 220, 1]
    assert len(tidy) == 10_461


def test_labels_are_harmonised(cleaned):
    tidy, _ = cleaned
    assert "New Delhi" not in set(tidy["destination"])
    assert "Banglore" not in set(tidy["source"])
    assert not tidy["additional_info"].eq("No Info").any()


def test_stops_match_route(cleaned):
    tidy, _ = cleaned
    assert (tidy["route"].str.count("→") - 1).eq(tidy["n_stops"]).all()


def test_business_class_is_excluded(cleaned):
    tidy, _ = cleaned
    flights = economy_only(tidy)
    assert len(tidy) - len(flights) == 7
    assert flights["cabin"].ne("Business").all()
