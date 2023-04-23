"""Tests des données du site : fond de carte, regroupements et écriture de data.js."""

import json

import pytest

from flight_prices.config import AIRPORTS
from flight_prices.data import clean, economy_only, load_raw
from flight_prices.geo import Projection, airport_positions, load_simplified_outline, outline_svg
from flight_prices.site_data import STRIP_SIZE, groupings, network, strip, write_data_js


@pytest.fixture(scope="module")
def flights():
    return economy_only(clean(load_raw())[0])


def test_projection_keeps_north_up_and_west_left():
    project = Projection((68.0, 6.0, 98.0, 37.0), width=1000)
    delhi = project(77.1, 28.6)
    cochin = project(76.4, 10.2)
    kolkata = project(88.4, 22.7)
    assert delhi[1] < cochin[1]
    assert delhi[0] < kolkata[0]
    assert 0 <= delhi[0] <= 1000


def test_simplified_outline_is_versioned_and_light():
    outline = load_simplified_outline()
    lon_min, lat_min, lon_max, lat_max = outline.bounds
    assert 67 < lon_min < 70 and 96 < lon_max < 98
    assert 6 < lat_min < 9 and 35 < lat_max < 38
    path, project = outline_svg(outline)
    assert path.startswith("M") and path.endswith("Z")
    assert len(path) < 40_000
    positions = airport_positions(project, ["DEL", "COK"])
    assert all(0 <= p["x"] <= project.width for p in positions.values())


def test_every_route_airport_has_coordinates(flights):
    codes = set(flights["route"].str.split(" → ").explode())
    assert codes <= set(AIRPORTS)


def test_groupings_cover_every_story_step(flights):
    index, groups = groupings(flights)
    assert list(groups) == ["stops", "airline", "duration", "period"]
    assert sum(g["n"] for g in groups["stops"]) == len(flights)
    medians = [g["median"] for g in groups["airline"]]
    assert medians == sorted(medians)
    assert groups["period"][0]["median"] > groups["period"][2]["median"]  # début mars > avril
    assert index["airline"].isna().sum() == 1  # Trujet, un seul vol


def test_strip_sample(flights):
    data = strip(flights)
    assert len(data["rows"]) == STRIP_SIZE
    assert all(len(row) == 1 + len(data["keys"]) for row in data["rows"])
    assert data["overall"]["n"] == len(flights)


def test_network_pairs(flights):
    data = network(flights)
    assert len(data["pairs"]) == 5
    assert data["pairs"][0]["from"] == "DEL" and data["pairs"][0]["to"] == "COK"


def test_write_data_js(tmp_path):
    path = tmp_path / "data.js"
    write_data_js({"a": 1, "texte": "é"}, path)
    text = path.read_text(encoding="utf-8")
    payload = text.split("window.SITE_DATA = ", 1)[1].rstrip().rstrip(";")
    assert json.loads(payload) == {"a": 1, "texte": "é"}
