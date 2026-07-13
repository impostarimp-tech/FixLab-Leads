from unittest.mock import MagicMock, patch

import requests

import routes_geocoding as geo


def _fake_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get")
def test_nominatim_geocode_returns_coords_on_success(mock_get, _mock_sleep):
    mock_get.return_value = _fake_response([{"lat": "-34.6083", "lon": "-58.3712"}])
    result = geo.nominatim_geocode("Av. Rivadavia 100, Buenos Aires, Argentina")
    assert result == (-34.6083, -58.3712)


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get")
def test_nominatim_geocode_returns_none_on_empty_results(mock_get, _mock_sleep):
    mock_get.return_value = _fake_response([])
    assert geo.nominatim_geocode("direccion inexistente") is None


@patch("routes_geocoding.time.sleep", return_value=None)
@patch(
    "routes_geocoding.requests.get",
    side_effect=requests.exceptions.ConnectionError("network down"),
)
def test_nominatim_geocode_returns_none_after_retries_exhausted(mock_get, _mock_sleep):
    assert geo.nominatim_geocode("cualquier direccion", max_retries=2) is None
    assert mock_get.call_count == 3  # initial attempt + 2 retries


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_prefers_maps_url_over_nominatim(mock_nominatim):
    coords, source = geo.geocode_lead(
        negocio="Taller X", direccion="Dir X",
        maps_url="https://maps.google.com/@-34.6,-58.4,15z",
    )
    assert coords == (-34.6, -58.4)
    assert source == "maps_url"
    mock_nominatim.assert_not_called()


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_falls_back_to_direccion(mock_nominatim):
    mock_nominatim.return_value = (-34.7, -58.5)
    coords, source = geo.geocode_lead(negocio="Taller X", direccion="Dir X", maps_url=None)
    assert coords == (-34.7, -58.5)
    assert source == "direccion"
    mock_nominatim.assert_called_once_with("Dir X, Buenos Aires, Argentina")


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_falls_back_to_negocio_when_direccion_fails(mock_nominatim):
    mock_nominatim.side_effect = [None, (-34.8, -58.6)]
    coords, source = geo.geocode_lead(negocio="Taller X", direccion="Dir X", maps_url=None)
    assert coords == (-34.8, -58.6)
    assert source == "negocio"


@patch("routes_geocoding.nominatim_geocode", return_value=None)
def test_geocode_lead_returns_fallido_when_all_fail(mock_nominatim):
    coords, source = geo.geocode_lead(negocio="Taller X", direccion="Dir X", maps_url=None)
    assert coords is None
    assert source == "fallido"


def test_geocode_lead_skips_direccion_when_blank():
    with patch("routes_geocoding.nominatim_geocode", return_value=(-34.9, -58.7)) as mock_nominatim:
        coords, source = geo.geocode_lead(negocio="Taller X", direccion="", maps_url=None)
        mock_nominatim.assert_called_once_with("Taller X, Buenos Aires, Argentina")
        assert source == "negocio"


def test_geocode_free_text_appends_city_and_country():
    with patch("routes_geocoding.nominatim_geocode", return_value=(-34.6, -58.4)) as mock_nominatim:
        result = geo.geocode_free_text("Av. Corrientes 1000")
        mock_nominatim.assert_called_once_with("Av. Corrientes 1000, Buenos Aires, Argentina")
        assert result == (-34.6, -58.4)


def test_expand_abbreviations_replaces_known_abbreviations():
    direccion = "Av. Cnel. Díaz 1862, C1425 Cdad. Autónoma de Buenos Aires, Argentina"
    assert geo._expand_abbreviations(direccion) == (
        "Av. Coronel Díaz 1862, C1425 Ciudad Autónoma de Buenos Aires, Argentina"
    )


def test_expand_abbreviations_leaves_addresses_without_abbreviations_unchanged():
    direccion = "Av. Rivadavia 2000, Buenos Aires, Argentina"
    assert geo._expand_abbreviations(direccion) == direccion


def test_expand_abbreviations_handles_multiple_different_abbreviations():
    direccion = "Gral. Güemes 897, Dr. Ricardo Balbín 2570"
    assert geo._expand_abbreviations(direccion) == "General Güemes 897, Doctor Ricardo Balbín 2570"


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_expands_abbreviations_before_querying_direccion(mock_nominatim):
    mock_nominatim.return_value = (-34.6, -58.4)
    geo.geocode_lead(
        negocio="Taller X",
        direccion="Av. Cnel. Díaz 1862, Cdad. Autónoma de Buenos Aires, Argentina",
        maps_url=None,
    )
    mock_nominatim.assert_called_once_with(
        "Av. Coronel Díaz 1862, Ciudad Autónoma de Buenos Aires, Argentina"
    )


def test_insert_postal_code_comma_separates_extended_cpa_code():
    direccion = "Rincón 37, C1081ABA Ciudad Autónoma de Buenos Aires, Argentina"
    assert geo._insert_postal_code_comma(direccion) == (
        "Rincón 37, C1081ABA, Ciudad Autónoma de Buenos Aires, Argentina"
    )


def test_insert_postal_code_comma_separates_simple_code_before_provincia():
    direccion = "Av. Maipú 88, B1602 Provincia de Buenos Aires, Argentina"
    assert geo._insert_postal_code_comma(direccion) == (
        "Av. Maipú 88, B1602, Provincia de Buenos Aires, Argentina"
    )


def test_insert_postal_code_comma_leaves_already_separated_address_unchanged():
    direccion = "Rincón 37, C1081ABA, Ciudad Autónoma de Buenos Aires, Argentina"
    assert geo._insert_postal_code_comma(direccion) == direccion


@patch("routes_geocoding.nominatim_geocode")
def test_geocode_lead_inserts_postal_code_comma_before_querying_direccion(mock_nominatim):
    mock_nominatim.return_value = (-34.6, -58.4)
    geo.geocode_lead(
        negocio="Taller X",
        direccion="Rincón 37, C1081ABA Cdad. Autónoma de Buenos Aires, Argentina",
        maps_url=None,
    )
    mock_nominatim.assert_called_once_with(
        "Rincón 37, C1081ABA, Ciudad Autónoma de Buenos Aires, Argentina"
    )


def test_with_city_suffix_skips_when_buenos_aires_already_mentioned():
    text = "Av. Coronel Díaz 1862, Ciudad Autónoma de Buenos Aires, Argentina"
    assert geo._with_city_suffix(text) == text


def test_with_city_suffix_appends_when_not_mentioned():
    assert geo._with_city_suffix("Av. Rivadavia 100") == "Av. Rivadavia 100, Buenos Aires, Argentina"


def test_with_city_suffix_is_case_insensitive():
    text = "Av. Rivadavia 100, BUENOS AIRES, argentina"
    assert geo._with_city_suffix(text) == text


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get")
def test_nominatim_geocode_rejects_results_outside_amba_bounds(mock_get, _mock_sleep):
    mock_get.return_value = _fake_response([{"lat": "-36.0158034", "lon": "-59.0941764"}])
    assert geo.nominatim_geocode("direccion ambigua") is None


@patch("routes_geocoding.time.sleep", return_value=None)
@patch("routes_geocoding.requests.get")
def test_nominatim_geocode_accepts_results_inside_amba_bounds(mock_get, _mock_sleep):
    mock_get.return_value = _fake_response([{"lat": "-34.5895263", "lon": "-58.4106593"}])
    assert geo.nominatim_geocode("Av. Coronel Diaz 1862") == (-34.5895263, -58.4106593)
