import routes_geocoding as geo


def test_parses_coords_from_standard_maps_url():
    url = "https://www.google.com/maps/place/Taller+X/@-34.608300,-58.371200,17z/data=!4m5"
    assert geo.parse_coords_from_maps_url(url) == (-34.6083, -58.3712)


def test_returns_none_when_no_coords_in_url():
    url = "https://www.google.com/maps/place/Taller+X/data=!4m5!3m4"
    assert geo.parse_coords_from_maps_url(url) is None


def test_returns_none_for_empty_or_missing_url():
    assert geo.parse_coords_from_maps_url("") is None
    assert geo.parse_coords_from_maps_url(None) is None


def test_parses_coords_with_positive_latitude_and_longitude():
    url = "https://www.google.com/maps/@40.7128,74.0060,15z"
    assert geo.parse_coords_from_maps_url(url) == (40.7128, 74.0060)
