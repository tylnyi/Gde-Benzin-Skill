"""Explicit, small live contract check. Not imported by offline unit tests."""
import importlib.util
import json
from pathlib import Path

root = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("client", root / "skills/gde-benzin/scripts/gde_benzin.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
client = api.Client()
cities = [("Москва", 55.7539, 37.6208), ("Санкт-Петербург", 59.9386, 30.3141),
          ("Казань", 55.7961, 49.1064), ("Красноярск", 56.0106, 92.8526),
          ("Владивосток", 43.1155, 131.8855), ("Калининград", 54.7104, 20.4522)]
for name, lat, lon in cities:
    args = api.parser().parse_args(["search", "--lat", str(lat), "--lon", str(lon), "--fuel", "95", "--limit", "2"])
    out = api.search(client, args)
    assert out["status"] in ("ok", "no_matches")
    assert out["shown_count"] <= 2
    for s in out["stations"]:
        assert s["fuels"]["ai95"]["available"] is True
        assert "#station=" in s["map_url"] and "utm_source=ai_agent" in s["map_url"]
    print(json.dumps({"city": name, "status": out["status"], "matches": out["matching_count"]}, ensure_ascii=False))
places = api.locate(client, "Тверь")
assert places["places"]
print("PASS: six regional searches and place lookup")
