from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

MODULE = Path(__file__).parents[1] / "skills/gde-benzin/scripts/gde_benzin.py"
spec = importlib.util.spec_from_file_location("gde_benzin", MODULE)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
NOW = datetime.now(timezone.utc)


def station(sid=1, lat=55.75, lon=37.62, fuel="ai95", available=True, age=60, price=75.5, price_age=120):
    return {"id": sid, "name": "Тестовая АЗС", "address": "Тестовый адрес", "lat": lat, "lon": lon,
            "fuels": {fuel: {"available": available, "freshness_seconds": age,
                             "last_report_at": (NOW - timedelta(seconds=age)).isoformat(),
                             "expires_in_seconds": 21600 - age}},
            "prices": {fuel: {"price": price, "freshness_seconds": price_age}}}


def payload(*stations, truncated=False):
    return {"count": len(stations), "stations": list(stations), "truncated": truncated, "limit": 3000}


def args(*options):
    return api.parser().parse_args(["search", "--lat", "55.75", "--lon", "37.62", *options])


class SelectionTests(unittest.TestCase):
    def search(self, stations, *options):
        client = Mock()
        client.get.return_value = payload(*stations)
        return api.search(client, args(*options))

    def test_fuel_availability_is_not_inferred_from_price(self):
        out = self.search([station(available=None)], "--fuel", "95")
        self.assertEqual(out["status"], "no_matches")

    def test_unavailable_grade_is_not_returned(self):
        self.assertEqual(self.search([station(available=False)], "--fuel", "95")["stations"], [])

    def test_no_automatic_fuel_substitution(self):
        for requested in ("ДТ", "95", "100"):
            with self.subTest(requested=requested):
                self.assertEqual(self.search([station(fuel="ai92")], "--fuel", requested)["status"], "no_matches")

    def test_no_fuel_search_preserves_unknown_catalog_stations(self):
        out = self.search([station(available=None)])
        self.assertEqual(len(out["stations"]), 1)
        self.assertIsNone(out["stations"][0]["fuels"]["ai95"]["available"])

    def test_old_grade_is_not_rescued_by_another_fresh_grade(self):
        s = station(age=25000)
        s["fuels"]["ai92"] = station(fuel="ai92")["fuels"]["ai92"]
        self.assertEqual(self.search([s], "--fuel", "95")["status"], "no_matches")

    def test_expired_grade_is_not_rescued_by_low_age(self):
        s = station()
        s["fuels"]["ai95"]["expires_in_seconds"] = 0
        self.assertEqual(self.search([s], "--fuel", "95")["status"], "no_matches")

    def test_age_is_checked_against_real_timestamp(self):
        s = station()
        s["fuels"]["ai95"]["last_report_at"] = (NOW - timedelta(days=2)).isoformat()
        self.assertEqual(self.search([s], "--fuel", "95")["status"], "no_matches")

    def test_future_and_invalid_observation_times_are_not_current(self):
        for stamp in ((NOW + timedelta(hours=2)).isoformat(), "invalid", "2026-11-09T07:00:00"):
            s = station();s["fuels"]["ai95"]["last_report_at"] = stamp
            with self.subTest(stamp=stamp):
                self.assertEqual(self.search([s], "--fuel", "95")["status"], "no_matches")

    def test_price_uses_its_own_grade_and_time(self):
        s = station(price_age=2000)
        s["prices"]["ai92"] = {"price": 60, "freshness_seconds": 10}
        f = self.search([s], "--fuel", "95")["stations"][0]["fuels"]["ai95"]
        self.assertEqual((f["price_rub_per_liter"], f["price_age_seconds"]), (75.5, 2000))

    def test_old_price_does_not_hide_fresh_availability(self):
        out = self.search([station(price_age=90000)], "--fuel", "95")["stations"][0]["fuels"]["ai95"]
        self.assertTrue(out["available"])
        self.assertIsNone(out["price_rub_per_liter"])

    def test_all_five_grades_display_their_own_price(self):
        for fuel in api.LABELS:
            with self.subTest(fuel=fuel):
                out = self.search([station(fuel=fuel, price=80)], "--fuel", fuel)
                self.assertIn("80.00 ₽/л", api.render(out, fuel))

    def test_invalid_price_is_hidden(self):
        for value in (True, -1, 0, float("nan"), "75"):
            with self.subTest(value=value):
                f = self.search([station(price=value)])["stations"][0]["fuels"]["ai95"]
                self.assertIsNone(f["price_rub_per_liter"])

    def test_station_outside_circle_is_not_returned(self):
        self.assertEqual(self.search([station(lat=55.80, lon=37.67)])["matching_count"], 0)

    def test_filters_full_bbox_before_limiting_nearest(self):
        rows = [station(sid=i, lon=37.62 + i * .0001, available=False) for i in range(1, 40)]
        rows.append(station(sid=100, lon=37.63))
        self.assertEqual(self.search(rows, "--fuel", "95")["stations"][0]["id"], 100)

    def test_sorting_limit_and_duplicate_ids(self):
        rows = [station(2, lat=55.76), station(1), station(1)]
        out = self.search(rows, "--limit", "1")
        self.assertEqual((out["matching_count"], out["shown_count"], out["stations"][0]["id"]), (2, 1, 1))

    def test_incomplete_bbox_fails_instead_of_claiming_no_fuel(self):
        client = Mock()
        for bad in (payload(truncated=True), {"stations": []}, [], {"count": 9, "stations": [], "truncated": False}):
            client.get.return_value = bad
            with self.subTest(bad=bad), self.assertRaises(api.IncompleteResult):
                api.search(client, args())

    def test_internal_fields_do_not_leak(self):
        s = station()
        s.update(source_type="parser", reporter_key="internal", user_confirmations=0)
        s["fuels"]["ai95"]["source_type"] = "mixed"
        raw = json.dumps(self.search([s]), ensure_ascii=False)
        for field in ("source_type", "reporter_key", "user_confirmations", '"parser"', '"mixed"'):
            self.assertNotIn(field, raw)

    def test_missing_and_invalid_station_fields_are_failures(self):
        for change in ({"id": True}, {"id": "1"}, {"lat": 500}, {"fuels": []}, {"prices": []}, {"fuels": {"ai95": "yes"}}):
            s = station();s.update(change)
            with self.subTest(change=change), self.assertRaises(api.ApiError):
                self.search([s])


class GeographyTests(unittest.TestCase):
    def test_distance_and_polar_bbox(self):
        self.assertEqual(api.distance_km(0, 0, 0, 0), 0)
        self.assertAlmostEqual(api.distance_km(0, 0, 0, 1), 111.195, places=2)
        self.assertEqual(api.bounding_boxes(90, 0, 5)[0][1::2], (-180, 180))

    def test_dateline_split_both_directions(self):
        for lon in (179.99, -179.99):
            boxes = api.bounding_boxes(65, lon, 5)
            self.assertEqual(len(boxes), 2)
            for south, west, north, east in boxes:
                self.assertTrue(-90 <= south < north <= 90)
                self.assertTrue(-180 <= west < east <= 180)

    def test_bbox_contains_circle_at_different_latitudes(self):
        for lat in (0, 45, 60, 78):
            south, west, north, east = api.bounding_boxes(lat, 40, 50)[0]
            self.assertLessEqual(api.distance_km(lat, 40, north, 40), 50.00001)
            self.assertGreater(east - west, .8)

    def test_dateline_search_queries_two_boxes_and_deduplicates(self):
        client = Mock()
        client.get.return_value = payload(station(1, lat=65, lon=-179.99))
        a = args();a.lat = 65;a.lon = 179.99
        out = api.search(client, a)
        self.assertEqual(client.get.call_count, 2)
        self.assertEqual(out["matching_count"], 1)


class OutputAndCliTests(unittest.TestCase):
    def attribution_cases(self):
        return (
            (["search", "--lat", "55.75", "--lon", "37.62"], payload(station()), None),
            (["search", "--lat", "55.75", "--lon", "37.62"], payload(), None),
            (["station", "1"], station(), None),
            (["locate", "Тверь"], {"items": [{"n": "Тверь", "lat": 56, "lon": 35}]}, None),
            (["station", "1"], None, api.ApiError("offline")),
            (["search", "--lat", "55.75", "--lon", "37.62"], payload(truncated=True), None),
        )

    def test_every_json_response_exposes_both_required_links(self):
        for command, result, error in self.attribution_cases():
            client = Mock();client.get.return_value = result;client.get.side_effect = error
            output = io.StringIO()
            with self.subTest(command=command, error=error, result=result), contextlib.redirect_stdout(output):
                api.main(command + ["--format", "json"], client)
            data = json.loads(output.getvalue())
            attribution = data["attribution"]
            self.assertTrue(attribution["required"])
            self.assertEqual(attribution["website_url"], "https://gde-benzin.ru/")
            self.assertEqual(attribution["author_url"], "https://www.youtube.com/@d_tylnyi")
            self.assertEqual(attribution["terms_version"], "1.0")
            self.assertEqual(urlsplit(attribution["terms_url"]).hostname, "github.com")

    def test_every_text_response_has_one_common_credit_block(self):
        for command, result, error in self.attribution_cases():
            client = Mock();client.get.return_value = result;client.get.side_effect = error
            output = io.StringIO()
            with self.subTest(command=command, error=error, result=result), contextlib.redirect_stdout(output):
                api.main(command, client)
            result_text = output.getvalue()
            self.assertEqual(result_text.count("https://www.youtube.com/@d_tylnyi"), 1)
            self.assertEqual(result_text.count("Данные: [Где бензин]("), 1)
            self.assertIn("utm_source=ai_agent", result_text)

    def test_author_credit_is_not_repeated_per_station(self):
        client = Mock(get=Mock(return_value=payload(station(1), station(2))))
        result_text = api.render(api.search(client, args()))
        self.assertEqual(result_text.count("https://www.youtube.com/@d_tylnyi"), 1)
        for sid in (1, 2):
            self.assertIn(api.map_url(sid), result_text)

    def test_links_have_station_fragment_and_referral_parameters(self):
        for sid in (1, 41134):
            u = urlsplit(api.map_url(sid))
            self.assertEqual((u.scheme, u.netloc, u.fragment), ("https", "gde-benzin.ru", f"station={sid}"))
            self.assertEqual(parse_qs(u.query), {k: [v] for k, v in api.UTM.items()})
            self.assertNotIn("lat", u.query)

    def test_markdown_api_text_is_escaped(self):
        s = station();s["name"] = "[click](https://evil.invalid)\n\x1b[31m"
        out = api.search(Mock(get=Mock(return_value=payload(s))), args())
        rendered = api.render(out)
        self.assertNotIn("\x1b", rendered)
        self.assertIn(r"\[click\]\(https://evil.invalid\)", rendered)
        self.assertIn(api.map_url(1), rendered)

    def test_fuel_aliases(self):
        for val in ("95", "АИ-95", "ai95", "аи 95"):
            self.assertEqual(api.fuel_code(val), "ai95")
        for val in ("ДТ", "дизель", "diesel", "dt"):
            self.assertEqual(api.fuel_code(val), "dt")

    def test_invalid_arguments_fail_before_network(self):
        client = Mock()
        cases = [["search", "--lat", "nan", "--lon", "37"], ["search", "--lat", "91", "--lon", "37"],
                 ["search", "--lat", "55", "--lon", "inf"], ["search", "--lat", "55", "--lon", "37", "--fuel", "газ"],
                 ["search", "--lat", "55", "--lon", "37", "--radius-km", "51"], ["station", "-1"], ["locate", "x"]]
        for case in cases:
            with self.subTest(case=case), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
                api.main(case, client)
            self.assertEqual(e.exception.code, 2)
        client.get.assert_not_called()

    def test_main_network_failure_and_incomplete_have_distinct_codes(self):
        for error, code, status in ((api.ApiError("timeout"), 3, "error"), (api.IncompleteResult("partial"), 4, "incomplete")):
            client = Mock();client.get.side_effect = error
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = api.main(["search", "--lat", "55", "--lon", "37", "--format", "json"], client)
            self.assertEqual(rc, code)
            self.assertEqual(json.loads(output.getvalue())["status"], status)

    def test_no_matches_is_not_a_transport_failure(self):
        client = Mock(get=Mock(return_value=payload()))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = api.main(["search", "--lat", "55", "--lon", "37", "--format", "json"], client)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "no_matches")

    def test_locate_does_not_choose_ambiguous_result(self):
        client = Mock(get=Mock(return_value={"items": [{"n": "Тверь", "lat": 56, "lon": 35}, {"n": "Другой вариант", "lat": 57, "lon": 36}]}))
        self.assertEqual(len(api.locate(client, "Тверь")["places"]), 2)

    def test_station_command_uses_detail_endpoint(self):
        client = Mock(get=Mock(return_value=station()))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(["station", "1"], client), 0)
        client.get.assert_called_once_with("/stations/1")


class Response(io.BytesIO):
    def __init__(self, raw, content_type="application/json"):
        super().__init__(raw)
        self.headers = {"Content-Type": content_type}


class TransportTests(unittest.TestCase):
    def client(self, effects):
        opener, sleep = Mock(), Mock()
        opener.open.side_effect = effects
        return api.Client(opener=opener, sleep=sleep), opener, sleep

    def test_bounded_retry_and_identifying_user_agent(self):
        client, opener, sleep = self.client([URLError("offline"), Response(b'{}')])
        self.assertEqual(client.get("/stations", {"bbox": "1,2,3,4"}), {})
        self.assertEqual(opener.open.call_count, 2)
        sleep.assert_called_once_with(1)
        request = opener.open.call_args[0][0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("GdeBenzinSkill", request.get_header("User-agent"))

    def test_retry_after_is_respected(self):
        e = HTTPError(api.API, 429, "slow", {"Retry-After": "3"}, None)
        client, opener, sleep = self.client([e, Response(b'{}')])
        client.get("/stations")
        sleep.assert_called_once_with(3)

    def test_long_retry_after_and_404_are_not_retried(self):
        for code in (429, 404):
            client, opener, sleep = self.client([HTTPError(api.API, code, "error", {"Retry-After": "60"}, None)])
            with self.assertRaises(api.ApiError):
                client.get("/stations")
            self.assertEqual(opener.open.call_count, 1)
            sleep.assert_not_called()

    def test_retry_is_bounded_even_if_second_attempt_fails(self):
        client, opener, sleep = self.client([URLError("a"), URLError("b")])
        with self.assertRaises(api.ApiError):
            client.get("/stations")
        self.assertEqual(opener.open.call_count, 2)

    def test_html_invalid_json_and_nan_are_errors(self):
        for body, mime in ((b'<html>challenge</html>', "text/html"), (b'{oops', "application/json"), (b'{"x":NaN}', "application/json")):
            client, _, _ = self.client([Response(body, mime)])
            with self.subTest(body=body), self.assertRaises(api.ApiError):
                client.get("/stations")

    def test_size_cap_fails_without_accepting_partial_body(self):
        client, _, _ = self.client([Response(b' ' * (api.MAX_BODY + 1))])
        with self.assertRaises(api.IncompleteResult):
            client.get("/stations")

    def test_redirects_outside_official_https_origin_are_blocked(self):
        handler = api.OfficialRedirects()
        for target in ("http://gde-benzin.ru/api/", "https://evil.invalid/api/", "https://gde-benzin.ru:444/api/"):
            with self.subTest(target=target), self.assertRaises(api.ApiError):
                handler.redirect_request(None, None, 302, "", {}, target)


if __name__ == "__main__":
    unittest.main()
