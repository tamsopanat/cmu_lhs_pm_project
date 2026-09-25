"""Exercise live DustBoy responses and the persisted outage fallback."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import dustboy
import main


STATION = {
    "id": "4", "dustboy_name": "ไนท์บาร์ซาร์ ต.ช้างม่อย อ.เมือง จ.เชียงใหม่",
    "pm25": 160, "temp": 39, "log_datetime": "2026-09-25 13:00:00",
}
HISTORY = {"value": [
    {"log_datetime": "2026-09-24 13:00", "pm25": 40, "temp": 30},
    {"log_datetime": "2026-09-25 12:00:00", "pm25": 150, "temp": 38},
]}


class DustBoyIntegrationTest(unittest.TestCase):
    def test_province_load_uses_one_bulk_station_request(self):
        second = {**STATION, "id": "5", "dustboy_name": "โรงเรียน ต.สุเทพ อ.เมือง จ.เชียงใหม่"}
        with tempfile.TemporaryDirectory() as folder, patch.object(dustboy, "CACHE_PATH", Path(folder) / "readings.sqlite3"):
            with patch.object(dustboy, "_request", return_value=[STATION, second]) as request:
                data = main.get_dashboard_data(
                    province="เชียงใหม่", start_date="2026-09-25", end_date="2026-09-25", refresh=True
                )
            self.assertEqual(request.call_count, 1)
            self.assertEqual(data["environment"]["source"], "live")
            self.assertEqual(len(data["environment"]["stations"]), 2)

    def test_live_response_then_cached_response(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(dustboy, "CACHE_PATH", Path(folder) / "readings.sqlite3"):
            def live(path):
                return [STATION] if path == "geography" else HISTORY

            with patch.object(dustboy, "_request", side_effect=live):
                locations = main.get_locations()
                self.assertEqual(locations["เชียงใหม่"]["เมือง"], ["ช้างม่อย"])
                live_data = main.get_dashboard_data(
                    province="เชียงใหม่", start_date="2026-09-24", end_date="2026-09-25", refresh=True
                )
            self.assertEqual(live_data["environment"]["source"], "live")
            self.assertEqual(live_data["environment"]["stations"][0]["pm25"], 160)
            self.assertEqual(live_data["environment"]["pm25"], [40, 160])

            with patch.object(dustboy, "_request", side_effect=requests.ConnectionError("offline")):
                cached_data = main.get_dashboard_data(
                    province="เชียงใหม่", start_date="2026-09-24", end_date="2026-09-25", refresh=True
                )
            self.assertEqual(cached_data["environment"]["source"], "cache")
            self.assertEqual(cached_data["environment"]["pm25"], live_data["environment"]["pm25"])

    def test_missing_cache_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(dustboy, "CACHE_PATH", Path(folder) / "readings.sqlite3"):
            with patch.object(dustboy, "_request", side_effect=requests.ConnectionError("offline")):
                response = main.get_locations()
            self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
