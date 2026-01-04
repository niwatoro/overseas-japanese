from __future__ import annotations

import math
from enum import Enum

from flask import abort, Flask, jsonify, render_template

from data.loader import METRIC_LABELS, aggregate_by_region, top_countries
app = Flask(__name__, template_folder="../templates", static_folder="../static")

class Metric(str, Enum):
    total = "total"
    long_term = "long_term"
    permanent = "permanent"


VALUE_KEYS = ("total", "long_term", "permanent", "adults")


def _cast_to_int(value: int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_values(values: dict[str, object]) -> dict[str, int | None]:
    return {key: _cast_to_int(values.get(key)) for key in VALUE_KEYS}


def _build_metric_summary(name: Metric) -> dict[str, str]:
    label = METRIC_LABELS[name.value]
    return {
        "name": name,
        "label": label,
        "description": f"{label}を基準にしたランキングです",
    }


def _build_country_response(record: dict[str, object]) -> dict[str, object]:
    return {
        "country": record["country"],
        "region": record["region"],
        "iso_alpha3": record["iso_alpha3"],
        "iso_alpha2": record.get("iso_alpha2"),
        "values": _normalize_values(record["values"]),
    }


def _get_country_responses(metric: Metric, limit: int | None) -> list[dict[str, object]]:
    try:
        records = top_countries(metric.value, limit)
    except KeyError as err:
        abort(400, str(err))
    return [_build_country_response(record) for record in records]


@app.route("/api/metrics")
def list_metrics():
    return jsonify([_build_metric_summary(metric) for metric in Metric])


@app.route("/api/data")
def country_metrics():
    metric = Metric.total
    limit = 25
    return jsonify(_get_country_responses(metric, limit))


@app.route("/api/data/all")
def all_country_metrics():
    metric = Metric.total
    return jsonify(_get_country_responses(metric, None))


@app.route("/api/regions")
def region_totals():
    return jsonify([
        {"region": summary["region"], "totals": _normalize_values(summary["totals"])}
        for summary in aggregate_by_region()
    ])

@app.route("/")
def index() -> str:
    return render_template("index.html")

if __name__ == "__main__":
    app.run(port=8000)
