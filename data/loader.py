from __future__ import annotations

import csv
import gettext
import math
import unicodedata
from collections import defaultdict
from functools import lru_cache
from typing import Literal

import pycountry
from babel import Locale

CSV_FILENAME = "data/海外在留邦人数調査統計（令和7年10月1日現在：機械判別用）.csv"

Metric = Literal["total", "long_term", "permanent"]

COLUMN_MAP = {
    "西暦（暦年）": "year",
    "地　域": "region",
    "国（地域）名・在外公館名": "country",
    "全体集計合計": "total",
    "長期滞在者合計": "long_term",
    "永住者合計": "permanent",
    "成人数": "adults",
}

METRIC_LABELS: dict[Metric, str] = {
    "total": "全体在留邦人数",
    "long_term": "長期滞在邦人数",
    "permanent": "永住邦人数",
}

NUMERIC_KEYS = ("total", "long_term", "permanent", "adults")


def _normalize_for_index(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def _build_japanese_country_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    loc = Locale("ja")
    for code, name in loc.territories.items():
        if isinstance(code, str) and len(code) == 2 and code.isalpha() and name:
            index[_normalize_for_index(name)].add(code.upper())

    translation = gettext.translation(
        "iso3166-1", pycountry.LOCALES_DIR, languages=["ja"], fallback=True
    )
    _ = translation.gettext

    for country in pycountry.countries:
        for attr in ("name", "official_name", "common_name"):
            name = getattr(country, attr, None)
            if not name:
                continue
            jp_name = _(name)
            if jp_name:
                index[_normalize_for_index(jp_name)].add(country.alpha_2)

    return index


JAPANESE_COUNTRY_INDEX = _build_japanese_country_index()


def _clean_text(value: str | float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip().replace('"', "")
    return text.replace("\u3000", " ").strip()


def _parse_int(value: str | float | int | None) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return int(text)
    except ValueError:
        return None


def _sanitize_country(value: str | None) -> str:
    normalized = _clean_text(value)
    for delim in ("（", "(", "-", "－"):
        if delim in normalized:
            normalized = normalized.split(delim)[0].strip()
    return normalized


def _alpha2_to_alpha3(alpha2: str | None) -> str | None:
    if not alpha2:
        return None
    country = pycountry.countries.get(alpha_2=alpha2)
    return country.alpha_3 if country else None


def _alpha3_to_alpha2(alpha3: str | None) -> str | None:
    if not alpha3:
        return None
    country = pycountry.countries.get(alpha_3=alpha3)
    return country.alpha_2 if country else None


def _resolve_iso(value: str | None) -> str | None:
    sanitized = _sanitize_country(value)
    if not sanitized:
        return None
    normalized = _normalize_for_index(sanitized)
    codes = JAPANESE_COUNTRY_INDEX.get(normalized)
    if codes:
        alpha3_candidates = {
            iso
            for iso in (_alpha2_to_alpha3(code) for code in codes)
            if iso
        }
        if len(alpha3_candidates) == 1:
            return next(iter(alpha3_candidates))
    try:
        match = pycountry.countries.search_fuzzy(normalized)
    except (LookupError, AttributeError):
        return None
    if match:
        return match[0].alpha_3
    return None


def _read_csv_rows() -> list[dict[str, object | None]]:
    with open(CSV_FILENAME, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        rows: list[dict[str, object | None]] = []
        for raw in reader:
            mapped: dict[str, object | None] = {}
            for source, dest in COLUMN_MAP.items():
                mapped[dest] = raw.get(source)
            rows.append(mapped)
        return rows


@lru_cache(maxsize=1)
def load_data() -> tuple[dict[str, object | None], ...]:
    seen: set[tuple[str, str]] = set()
    records: list[dict[str, object | None]] = []
    for row in _read_csv_rows():
        country_raw = _clean_text(row.get("country"))
        region_raw = _clean_text(row.get("region"))
        if not country_raw or not region_raw:
            continue
        region = region_raw.replace("\u3000", " ").strip()
        country = _sanitize_country(country_raw)
        if not country:
            continue
        key = (country, region)
        if key in seen:
            continue
        seen.add(key)

        values = {metric: _parse_int(row.get(metric)) for metric in NUMERIC_KEYS}
        iso_alpha3 = _resolve_iso(country)
        iso_alpha2 = _alpha3_to_alpha2(iso_alpha3)

        records.append(
            {
                "country": country,
                "region": region,
                "iso_alpha3": iso_alpha3,
                "iso_alpha2": iso_alpha2,
                **values,
            }
        )
    return tuple(records)


def aggregate_by_region() -> list[dict[str, object]]:
    region_totals: dict[str, dict[str, dict[str, int]]] = {}
    for record in load_data():
        stats = region_totals.setdefault(
            record["region"],
            {key: {"sum": 0, "count": 0} for key in NUMERIC_KEYS},
        )
        for key in NUMERIC_KEYS:
            value = record.get(key)
            if value is None:
                continue
            stats[key]["sum"] += value
            stats[key]["count"] += 1

    return [
        {
            "region": region,
            "totals": {
                key: stats[key]["sum"] if stats[key]["count"] else None
                for key in NUMERIC_KEYS
            },
        }
        for region, stats in region_totals.items()
    ]


METRIC_KEYS = tuple(METRIC_LABELS.keys())


def top_countries(metric: str, limit: int | None) -> list[dict[str, object]]:
    if metric not in METRIC_KEYS:
        raise KeyError(f"Unknown metric '{metric}'")
    records = [
        record
        for record in load_data()
        if record.get(metric) is not None
    ]
    ranked = sorted(records, key=lambda item: item.get(metric), reverse=True)
    sliced = ranked[:limit] if limit is not None else ranked
    return [
        {
            "country": row["country"],
            "region": row["region"],
            "iso_alpha3": row["iso_alpha3"],
            "iso_alpha2": row["iso_alpha2"],
            "values": {key: row.get(key) for key in NUMERIC_KEYS},
        }
        for row in sliced
    ]
