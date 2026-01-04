from __future__ import annotations

from enum import Enum

from flask import Flask, jsonify, render_template
from pydantic import BaseModel, Field

from data.loader import METRIC_LABELS, aggregate_by_region, top_countries

app = Flask(__name__, template_folder="../templates", static_folder="../static")

class Metric(str, Enum):
    total = "total"
    long_term = "long_term"
    permanent = "permanent"


class MetricSummary(BaseModel):
    name: Metric
    label: str
    description: str


class CountryValues(BaseModel):
    total: int | None = Field(None, description="全体在留邦人数")
    long_term: int | None = Field(None, description="長期滞在邦人数")
    permanent: int | None = Field(None, description="永住邦人数")
    adults: int | None = Field(None, description="成人邦人数")


class CountryResponse(BaseModel):
    country: str
    region: str
    iso_alpha3: str | None = Field(None, description="ISO 3166-1 alpha-3 コード")
    iso_alpha2: str | None = Field(None, description="ISO 3166-1 alpha-2 コード")
    values: CountryValues


class RegionTotals(BaseModel):
    region: str
    totals: CountryValues


def _build_metric_summary(name: Metric) -> MetricSummary:
    return MetricSummary(
        name=name,
        label=METRIC_LABELS[name.value],
        description=f"{METRIC_LABELS[name.value]}を基準にしたランキングです",
    )


def _build_country_response(record: dict[str, object]) -> CountryResponse:
    return CountryResponse(
        country=record["country"],
        region=record["region"],
        iso_alpha3=record["iso_alpha3"],
        iso_alpha2=record.get("iso_alpha2"),
        values=CountryValues(**record["values"]),
    )


def _get_country_responses(metric: Metric, limit: int | None) -> list[CountryResponse]:
    try:
        records = top_countries(metric.value, limit)
    except KeyError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return [_build_country_response(record) for record in records]


@app.route("/api/metrics")
def list_metrics():
    return jsonify([_build_metric_summary(metric).model_dump() for metric in Metric])


@app.route("/api/data")
def country_metrics():
    metric = Metric.total
    limit = 25
    return jsonify([response.dict() for response in _get_country_responses(metric, limit)])


@app.route("/api/data/all")
def all_country_metrics():
    metric = Metric.total
    return jsonify([response.dict() for response in _get_country_responses(metric, None)])


@app.route("/api/regions")
def region_totals():
    return jsonify([
        RegionTotals(region=summary["region"], totals=CountryValues(**summary["totals"])).model_dump()
        for summary in aggregate_by_region()
    ])

@app.route("/")
def index() -> str:
    return render_template("index.html")

if __name__ == "__main__":
    app.run(port=8000)
