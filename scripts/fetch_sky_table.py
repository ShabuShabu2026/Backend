"""Fetch hourly JPL Horizons observer tables for 2026 through 2028."""

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np

BASE = "https://ssd.jpl.nasa.gov/api/horizons.api?"
COMMON = {"format": "text", "EPHEM_TYPE": "'OBSERVER'", "START_TIME": "'2026-01-01 00:00'",
          "STOP_TIME": "'2029-01-01 00:00'", "STEP_SIZE": "'1 h'", "APPARENT": "'AIRLESS'",
          "CSV_FORMAT": "'YES'"}
QUERIES = (
    {"COMMAND": "'301'", "CENTER": "'500@399'", "QUANTITIES": "'14,15,20'"},
    {"COMMAND": "'10'", "CENTER": "'500@301'", "QUANTITIES": "'13,20'"},
)
AU_M = 149_597_870_700.0
EARTH_RADIUS_M = 6_371_000.0


def query_url(query: dict[str, str]) -> str:
    return BASE + urlencode(COMMON | query)


def get_rows(query: dict[str, str]) -> tuple[str, list[list[str]]]:
    with urlopen(query_url(query), timeout=120) as response:
        text = response.read().decode("utf-8")
    if "$$SOE" not in text or "$$EOE" not in text:
        raise ValueError("Horizons response contains no ephemeris table.")
    part = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows = [row for row in csv.reader(io.StringIO(part), skipinitialspace=True) if row]
    rows = [row for row in rows if row[0].strip()[:4] in {"2026", "2027", "2028"}]
    if len(rows) != 26304:
        raise ValueError(f"Expected 26304 hourly rows, received {len(rows)}.")
    return text, rows


def timestamp(row: list[str]) -> np.datetime64:
    dt = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M").replace(tzinfo=UTC)
    return np.datetime64(dt.replace(tzinfo=None), "h")


def unit(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    lon, lat = np.deg2rad(lon), np.deg2rad(lat)
    return np.column_stack((np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)))


def main() -> None:
    header, earth_rows = get_rows(QUERIES[0])
    _, sun_rows = get_rows(QUERIES[1])
    if "MOON_ME" not in header or "Positive longitude is\nto the EAST" not in header:
        raise ValueError("Horizons lunar frame or longitude convention is unexpected.")
    times = np.array([timestamp(row) for row in earth_rows])
    sun_times = np.array([timestamp(row) for row in sun_rows])
    expected = np.arange(np.datetime64("2026-01-01T00", "h"), np.datetime64("2029-01-01T00", "h"))
    if not np.array_equal(times, expected) or not np.array_equal(sun_times, times):
        raise ValueError("Horizons hourly timestamps are not aligned.")
    earth = np.array([[float(row[i]) for i in (3, 4, 5, 6, 7)] for row in earth_rows])
    sun = np.array([[float(row[i]) for i in (3, 4)] for row in sun_rows])
    r_earth = unit(earth[:, 0], earth[:, 1]) * (earth[:, 4, None] * AU_M)
    r_sun = unit(earth[:, 2], earth[:, 3]) * (sun[:, 1, None] * AU_M)
    earth_longitudes = (earth[:, 0] + 180) % 360 - 180
    rotation = abs(float(np.median(np.diff(np.unwrap(np.deg2rad(earth[:, 2]))))))
    period_days = 2 * np.pi / rotation / 24
    if np.max(np.abs(earth_longitudes)) > 15 or np.max(np.abs(earth[:, 1])) > 15 or not 25 < period_days < 35:
        raise ValueError("Horizons physical sanity checks failed.")
    path = Path("artifacts/sky_table.npz")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, time=times, r_earth=r_earth, r_sun=r_sun,
                        rho_sun=sun[:, 0] / 7200,
                        rho_earth=np.rad2deg(np.arcsin(EARTH_RADIUS_M / (earth[:, 4] * AU_M))))
    print(f"Saved {len(times)} hourly records to {path}")
    print(f"Earth subpoint max absolute lon/lat: {np.max(np.abs(earth_longitudes)):.3f}, {np.max(np.abs(earth[:, 1])):.3f} deg")
    print(f"Median synodic rotation period: {period_days:.3f} days")


if __name__ == "__main__":
    main()
