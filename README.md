# Overseas Japanese Distribution

This project pairs a FastAPI data surface with a Flask-powered dashboard so you can explore
the latest *海外在留邦人数調査* release without dropping into a notebook.
The API normalizes the CSV download, resolves each 国・地域 to ISO codes, and exposes
metrics for total, long-term, and permanent residents by country. The UI mounts under `/ui/`
and uses Plotly to render the distributions on a choropleth map plus companion tables.

## Prerequisites

- Python **>=3.13**
- `pip install -e .` will pull in FastAPI, Flask, pandas, Plotly, and the tooling listed in
  `pyproject.toml`.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The bundled CSV (`海外在留邦人数調査統計（令和7年10月1日現在：機械判別用）.csv`) must remain in the repository root so the data loader can
locate it. The loader accepts `.csv`, `.xlsx`, or `.xls` files encoded as UTF-8 (with or without
signature) or Shift_JIS.

## Run the app

```sh
uvicorn app.main:app --reload
```

- Visit `http://localhost:8000/ui/` for the Flask dashboard (map, rankings, region totals).
- The API stays mounted at `/api`: use `/api/metrics` to list available indicators, `/api/data`
  with `metric=total|long_term|permanent` (optionally `&limit=<n>`) to retrieve the top-N
  country records, and `/api/regions` for aggregated region totals.

## Extending

- Drop additional CSVs beside the existing one and point `CSV_FILENAME` inside `app/main.py` at
  the desired file.
- The FastAPI app is defined as `app` so you can reuse it in other ASGI workflows or wrap
  additional routers as needed.
