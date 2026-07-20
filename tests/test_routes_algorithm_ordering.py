import routes_algorithm as algo


def test_haversine_zero_for_same_point():
    assert algo.haversine_meters(-34.6, -58.4, -34.6, -58.4) == 0


def test_haversine_known_distance_buenos_aires_points():
    # Obelisco (-34.6037,-58.3816) to Congreso (-34.6095,-58.3925), roughly 1.1km apart
    d = algo.haversine_meters(-34.6037, -58.3816, -34.6095, -58.3925)
    assert 900 < d < 1300


def test_build_route_cheapest_insertion_visits_closest_first_on_a_line():
    origin = (0.0, 0.0)
    points = [
        {"id": "far", "lat": 0.03, "lng": 0.0},
        {"id": "near", "lat": 0.01, "lng": 0.0},
        {"id": "mid", "lat": 0.02, "lng": 0.0},
    ]
    route = algo.build_route_cheapest_insertion(origin, points, n=3)
    assert [p["id"] for p in route] == ["near", "mid", "far"]


def test_build_route_cheapest_insertion_caps_at_n():
    origin = (-34.60, -58.38)
    candidates = [
        {"id": 1, "lat": -34.601, "lng": -58.381},
        {"id": 2, "lat": -34.602, "lng": -58.382},
        {"id": 3, "lat": -34.603, "lng": -58.383},
    ]
    route = algo.build_route_cheapest_insertion(origin, candidates, n=2)
    assert len(route) == 2


def test_build_route_cheapest_insertion_caps_at_available_candidates():
    origin = (-34.60, -58.38)
    candidates = [{"id": 1, "lat": -34.601, "lng": -58.381}]
    route = algo.build_route_cheapest_insertion(origin, candidates, n=5)
    assert len(route) == 1


def test_build_route_cheapest_insertion_prefers_a_cheap_continuation_over_the_nearest_point():
    # B is farther from origin (3.34km) than C (3.11km), so a naive "n
    # nearest to origin" cutoff (n=2) would pick {A, C} and never consider B
    # at all. But B is a near-straight continuation past A (only +2.22km),
    # while C is off in another direction (+3.31km from A) -- so {A, B}
    # (3.34km total) is actually the shorter route vs {A, C} (4.42km total).
    # Cheapest insertion re-evaluates every remaining candidate against the
    # route built so far (not just against origin), so it catches this.
    origin = (0.0, 0.0)
    a = {"id": "A", "lat": 0.01, "lng": 0.0}
    b = {"id": "B", "lat": 0.03, "lng": 0.0}
    c = {"id": "C", "lat": 0.0, "lng": -0.028}

    route = algo.build_route_cheapest_insertion(origin, [a, b, c], n=2)

    assert [p["id"] for p in route] == ["A", "B"]


def test_two_opt_fixes_out_of_order_points_on_a_straight_line():
    origin = (0.0, 0.0)
    p_near = {"id": "near", "lat": 0.0, "lng": 0.001}
    p_mid = {"id": "mid", "lat": 0.0, "lng": 0.002}
    p_far = {"id": "far", "lat": 0.0, "lng": 0.003}
    # deliberately out of order: visits far, backtracks to near, then to mid
    scrambled = [p_far, p_near, p_mid]

    result = algo.two_opt(origin, scrambled)

    assert [p["id"] for p in result] == ["near", "mid", "far"]


def test_two_opt_uncrosses_a_bowtie_route():
    origin = (0.0, 0.0)
    nw = {"id": "nw", "lat": 0.002, "lng": 0.000}
    ne = {"id": "ne", "lat": 0.002, "lng": 0.002}
    se = {"id": "se", "lat": 0.000, "lng": 0.002}
    sw = {"id": "sw", "lat": 0.000, "lng": 0.001}
    # nw->se and ne->sw are the crossing diagonals of the square
    crossed = [nw, se, ne, sw]

    def route_length(points):
        total = 0.0
        lat, lng = origin
        for p in points:
            total += algo.haversine_meters(lat, lng, p["lat"], p["lng"])
            lat, lng = p["lat"], p["lng"]
        return total

    result = algo.two_opt(origin, crossed)

    assert route_length(result) < route_length(crossed)


def test_two_opt_leaves_already_optimal_route_unchanged():
    origin = (0.0, 0.0)
    points = [
        {"id": "near", "lat": 0.0, "lng": 0.001},
        {"id": "mid", "lat": 0.0, "lng": 0.002},
        {"id": "far", "lat": 0.0, "lng": 0.003},
    ]

    result = algo.two_opt(origin, points)

    assert [p["id"] for p in result] == ["near", "mid", "far"]


def test_two_opt_never_makes_the_route_longer():
    origin = (-34.60, -58.40)
    points = [
        {"id": 1, "lat": -34.61, "lng": -58.41},
        {"id": 2, "lat": -34.59, "lng": -58.42},
        {"id": 3, "lat": -34.60, "lng": -58.39},
        {"id": 4, "lat": -34.615, "lng": -58.395},
        {"id": 5, "lat": -34.585, "lng": -58.405},
    ]
    ordered = algo.build_route_cheapest_insertion(origin, points, n=len(points))

    def route_length(pts):
        total = 0.0
        lat, lng = origin
        for p in pts:
            total += algo.haversine_meters(lat, lng, p["lat"], p["lng"])
            lat, lng = p["lat"], p["lng"]
        return total

    result = algo.two_opt(origin, ordered)

    assert route_length(result) <= route_length(ordered) + 1e-9
    assert {p["id"] for p in result} == {p["id"] for p in ordered}


def test_build_route_picks_cheapest_insertion_when_it_wins(monkeypatch):
    origin = (0.0, 0.0)
    short_route = [{"id": "short", "lat": 0.001, "lng": 0.0}]
    long_route = [{"id": "long", "lat": 0.05, "lng": 0.05}]

    monkeypatch.setattr(algo, "_build_route_nearest_neighbor", lambda o, c, n: long_route)
    monkeypatch.setattr(algo, "build_route_cheapest_insertion", lambda o, c, n: short_route)

    result = algo.build_route(origin, [], n=1)

    assert [p["id"] for p in result] == ["short"]


def test_build_route_picks_nearest_neighbor_when_it_wins(monkeypatch):
    origin = (0.0, 0.0)
    short_route = [{"id": "short", "lat": 0.001, "lng": 0.0}]
    long_route = [{"id": "long", "lat": 0.05, "lng": 0.05}]

    monkeypatch.setattr(algo, "_build_route_nearest_neighbor", lambda o, c, n: short_route)
    monkeypatch.setattr(algo, "build_route_cheapest_insertion", lambda o, c, n: long_route)

    result = algo.build_route(origin, [], n=1)

    assert [p["id"] for p in result] == ["short"]


def test_build_route_returns_n_stops_on_real_data():
    origin = (-34.60, -58.40)
    candidates = [
        {"id": i, "lat": -34.60 + i * 0.001, "lng": -58.40 + i * 0.0005}
        for i in range(15)
    ]
    result = algo.build_route(origin, candidates, n=10)
    assert len(result) == 10
    assert len({p["id"] for p in result}) == 10


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
