from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Literal
from pathlib import Path

import gettext
import unicodedata
import pandas as pd
import pycountry
from babel import Locale

CSV_FILENAME = (
    Path(__file__).resolve().parents[1]
    / "海外在留邦人数調査統計（令和7年10月1日現在：機械判別用）.csv"
)

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


JAPANESE_COUNTRY_INDEX = _build_japanese_country_index()

def _clean_text(value: str | float | int | None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
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


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_FILENAME, encoding="utf-8-sig")
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
    df = df[df["country"].notna() & df["region"].notna()]

    for column in ("total", "long_term", "permanent", "adults"):
        if column in df:
            df[column] = df[column].map(_parse_int)

    df = df.assign(
        region=df["region"].astype(str).str.replace("\u3000", " ").str.strip(),
        country=df["country"].astype(str).map(_sanitize_country),
    )
    df["iso_alpha3"] = df["country"].map(_resolve_iso)
    df["iso_alpha2"] = df["iso_alpha3"].map(_alpha3_to_alpha2)
    return df.drop_duplicates(subset=("country", "region"))


def aggregate_by_region() -> list[dict[str, object]]:
    df = load_data()
    records: list[dict[str, object]] = []
    grouping = (
        df.groupby("region", sort=False)[["total", "long_term", "permanent", "adults"]]
        .sum(min_count=1)
        .reset_index()
    )
    for _, row in grouping.iterrows():
        records.append(
            {
                "region": row["region"],
                "totals": {
                    key: int(row[key]) if pd.notna(row[key]) else None
                    for key in ("total", "long_term", "permanent", "adults")
                },
            }
        )
    return records


METRIC_KEYS = tuple(METRIC_LABELS.keys())


def top_countries(metric: str, limit: int | None) -> list[dict[str, object]]:
    if metric not in METRIC_KEYS:
        raise KeyError(f"Unknown metric '{metric}'")
    df = load_data()
    metric_series = df[metric]
    ranked = df[metric_series.notna()].sort_values(metric, ascending=False)
    institutions = ranked.head(limit) if limit is not None else ranked
    return [
        {
            "country": row["country"],
            "region": row["region"],
            "iso_alpha3": row["iso_alpha3"],
            "iso_alpha2": row["iso_alpha2"],
            "values": {
                "total": row["total"],
                "long_term": row["long_term"],
                "permanent": row["permanent"],
                "adults": row.get("adults"),
            },
        }
        for _, row in institutions.iterrows()
    ]
