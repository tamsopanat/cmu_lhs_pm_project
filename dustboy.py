"""Fetch DustBoy observations and retain the last successful response per station."""

import json
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_URL = "https://open-api.cmuccdc.org/api/dustboy"
CACHE_PATH = Path(os.getenv("DUST_BOY_CACHE_PATH", "cache/dustboy.sqlite3"))
PROVINCES = ("เชียงราย", "เชียงใหม่", "แม่ฮ่องสอน", "ลำปาง", "ลำพูน", "น่าน", "แพร่", "พะเยา")
_recent_result = None
_recent_at = 0


def _db():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CACHE_PATH, timeout=30)
    connection.execute("CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched_at TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS observations (station_id TEXT NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY (station_id, date))")
    return connection


def _cached(key):
    with closing(_db()) as connection:
        row = connection.execute("SELECT payload, fetched_at FROM snapshots WHERE key = ?", (key,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else (None, None)


def _save(key, payload):
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with closing(_db()) as connection:
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO snapshots (key, payload, fetched_at) VALUES (?, ?, ?)",
                (key, json.dumps(payload, ensure_ascii=False), fetched_at),
            )
    return fetched_at


def _save_observations(station_list):
    rows = [(station["id"], row["date"], json.dumps(row, ensure_ascii=False))
            for station in station_list if (row := _row(station, station))]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30) + timedelta(hours=7)).strftime("%Y-%m-%d")
    with closing(_db()) as connection:
        with connection:
            connection.executemany(
                "INSERT OR REPLACE INTO observations (station_id, date, payload) VALUES (?, ?, ?)", rows
            )
            connection.execute("DELETE FROM observations WHERE date < ?", (cutoff,))


def _saved_observations(selected_stations):
    ids = [station["id"] for station in selected_stations]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with closing(_db()) as connection:
        values = connection.execute(
            f"SELECT payload FROM observations WHERE station_id IN ({placeholders})", ids
        ).fetchall()
    return [json.loads(value[0]) for value in values]


def _request(path):
    key = os.getenv("DUST_BOY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DUST_BOY_API_KEY is not configured")
    response = requests.get(
        f"{BASE_URL}/{path}",
        headers={"Authorization": f"Bearer {key}"},
        timeout=(5, 15),
    )
    response.raise_for_status()
    return response.json()


def _place(name, prefix):
    match = re.search(rf"(?:^|[^ก-๙]){prefix}\.\s*([ก-๙]+)", name or "")
    if not match:
        full = {"ต": "ตำบล", "อ": "อำเภอ", "จ": "จังหวัด"}[prefix]
        match = re.search(rf"{full}\s*([ก-๙]+)", name or "")
    return match.group(1) if match else None


def _station(raw):
    name = (raw.get("dustboy_name") or "").replace("เเม่", "แม่")
    province = _place(name, "จ")
    if province not in PROVINCES:
        province = next((p for p in PROVINCES if p in name), None)
    if province not in PROVINCES:
        return None
    amphoe = _place(name, "อ")
    if amphoe and (amphoe.startswith("เมือง") or amphoe == "มือง"):
        amphoe = "เมือง"
    tambon = _place(name, "ต") or "ไม่ระบุตำบล"
    if not raw.get("id"):
        return None
    return {
        "id": str(raw["id"]), "province": province, "amphoe": amphoe or "ไม่ระบุอำเภอ",
        "tambon": tambon, "name": name.split(" ต.")[0].strip() or name,
        "pm25": raw.get("pm25"), "temp": raw.get("temp"),
        "log_datetime": raw.get("log_datetime"),
    }


def stations(force=False):
    """Refresh on page entry and reuse that result for nearby filter requests."""
    global _recent_result, _recent_at
    if not force and _recent_result and time.monotonic() - _recent_at < 300:
        return _recent_result
    try:
        raw = _request("geography")
        if not isinstance(raw, list):
            raise ValueError("Unexpected geography response")
        parsed = [station for item in raw if isinstance(item, dict) if (station := _station(item))]
        if not parsed:
            raise ValueError("No usable DustBoy stations")
        fetched_at = _save("geography", parsed)
        _save_observations(parsed)
        result = (parsed, False, fetched_at)
    except (requests.RequestException, ValueError, RuntimeError):
        parsed, fetched_at = _cached("geography")
        if not parsed:
            raise RuntimeError("DustBoy is unavailable and no station cache exists")
        result = (parsed, True, fetched_at)
    _recent_result, _recent_at = result, time.monotonic()
    return result


def _number(value):
    try:
        result = float(value)
        if not 0 <= result < 10000:
            return None
        return result
    except (TypeError, ValueError):
        return None


def _temperature(value):
    result = _number(value)
    return result if result and -20 < result < 70 else None


def _row(station, item):
    stamp = item.get("log_datetime")
    pm25 = _number(item.get("pm25"))
    if not stamp or pm25 is None:
        return None
    try:
        datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    return {
        "date": datetime.fromisoformat(stamp).strftime("%Y-%m-%d %H:%M:%S"),
        "station_id": station["id"],
        "province": station["province"],
        "amphoe": station["amphoe"], "tambon": station["tambon"],
        "local_name": station["name"], "pm25_avg": pm25,
        "temperature_avg": _temperature(item.get("temp")),
    }


def _history(station):
    cache_key = f"history:{station['id']}"
    try:
        data = _request(f"data30day/{station['id']}")
        values = data.get("value") if isinstance(data, dict) else None
        if not isinstance(values, list):
            raise ValueError("Unexpected station history response")
        rows = [row for item in values if isinstance(item, dict) if (row := _row(station, item))]
        if not rows:
            raise ValueError("Station history has no usable readings")
        _save(cache_key, rows)
        return rows, False
    except (requests.RequestException, ValueError, RuntimeError):
        rows, _ = _cached(cache_key)
        return rows or [], True


def observations(selected_stations):
    """Use fresh geography readings plus saved snapshots for a bounded trend."""
    if not selected_stations:
        return []
    rows = _saved_observations(selected_stations)
    # The 30-day endpoint has a separate, restrictive quota. Only request it
    # for a single selected station, at most once per hour across the site.
    if len(selected_stations) == 1:
        station = selected_stations[0]
        saved_history, _ = _cached(f"history:{station['id']}")
        last_attempt, _ = _cached("history:last_attempt")
        due = not last_attempt or datetime.now().timestamp() - last_attempt > 3600
        if due:
            _save("history:last_attempt", datetime.now().timestamp())
            saved_history, _ = _history(station)
        rows.extend({**row, "station_id": station["id"],
                     "date": datetime.fromisoformat(row["date"]).strftime("%Y-%m-%d %H:%M:%S")}
                    for row in saved_history or [])
    for station in selected_stations:
        latest = _row(station, station)
        if latest:
            rows.append(latest)
    # A current reading can also appear in history or the saved snapshots.
    unique = {(row["station_id"], row["date"]): row for row in rows}
    return list(unique.values())
