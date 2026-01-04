from __future__ import annotations

from enum import Enum

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.wsgi import WSGIMiddleware
from pydantic import BaseModel, Field

from app.data import METRIC_LABELS, aggregate_by_region, top_countries
from app.flask_app import create_dashboard_app


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


flask_app = create_dashboard_app()
app = FastAPI(title="Overseas Japanese Distribution API")
app.mount("/ui", WSGIMiddleware(flask_app))


@app.get("/api/metrics", response_model=list[MetricSummary])
def list_metrics() -> list[MetricSummary]:
    return [_build_metric_summary(metric) for metric in Metric]


@app.get("/api/data", response_model=list[CountryResponse])
def country_metrics(
    metric: Metric = Metric.total, limit: int = Query(25, ge=1, le=100)
) -> list[CountryResponse]:
    try:
        records = top_countries(metric.value, limit)
    except KeyError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return [
        CountryResponse(
            country=record["country"],
            region=record["region"],
            iso_alpha3=record["iso_alpha3"],
            values=CountryValues(**record["values"]),
        )
        for record in records
    ]


@app.get("/api/regions", response_model=list[RegionTotals])
def region_totals() -> list[RegionTotals]:
    summaries = aggregate_by_region()
    return [
        RegionTotals(region=summary["region"], totals=CountryValues(**summary["totals"]))
        for summary in summaries
    ]
