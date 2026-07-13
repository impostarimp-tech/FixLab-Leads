import routes_algorithm as algo


def test_haversine_zero_for_same_point():
    assert algo.haversine_meters(-34.6, -58.4, -34.6, -58.4) == 0


def test_haversine_known_distance_buenos_aires_points():
    # Obelisco (-34.6037,-58.3816) to Congreso (-34.6095,-58.3925), roughly 1.1km apart
    d = algo.haversine_meters(-34.6037, -58.3816, -34.6095, -58.3925)
    assert 900 < d < 1300


def test_select_n_nearest_returns_closest_sorted_by_distance():
    origin = (-34.60, -58.38)
    candidates = [
        {"id": 1, "lat": -34.61, "lng": -58.39},    # farther
        {"id": 2, "lat": -34.601, "lng": -58.381},  # closest
        {"id": 3, "lat": -34.605, "lng": -58.385},  # middle
    ]
    result = algo.select_n_nearest(origin, candidates, n=2)
    assert [c["id"] for c in result] == [2, 3]


def test_select_n_nearest_caps_at_available_candidates():
    origin = (-34.60, -58.38)
    candidates = [{"id": 1, "lat": -34.601, "lng": -58.381}]
    result = algo.select_n_nearest(origin, candidates, n=5)
    assert len(result) == 1


def test_order_nearest_neighbor_visits_closest_unvisited_each_step():
    origin = (0.0, 0.0)
    points = [
        {"id": "far", "lat": 0.03, "lng": 0.0},
        {"id": "near", "lat": 0.01, "lng": 0.0},
        {"id": "mid", "lat": 0.02, "lng": 0.0},
    ]
    ordered = algo.order_nearest_neighbor(origin, points)
    assert [p["id"] for p in ordered] == ["near", "mid", "far"]


def test_chunk_into_sublotes_splits_preserving_order():
    points = [{"id": i} for i in range(20)]
    chunks = algo.chunk_into_sublotes(points, max_size=9)
    assert [len(c) for c in chunks] == [9, 9, 2]
    assert [p["id"] for p in chunks[0]] == list(range(9))
    assert [p["id"] for p in chunks[2]] == [18, 19]


def test_chunk_into_sublotes_handles_exact_multiple():
    points = [{"id": i} for i in range(18)]
    chunks = algo.chunk_into_sublotes(points, max_size=9)
    assert len(chunks) == 2
    assert all(len(c) == 9 for c in chunks)
