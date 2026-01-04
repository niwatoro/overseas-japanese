from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template


def create_dashboard_app() -> Flask:
    root = Path(__file__).resolve().parent.parent
    template_folder = root / "templates"
    static_folder = root / "static"

    flask_app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder),
        static_url_path="/static",
    )

    @flask_app.route("/")
    def index() -> str:
        return render_template("index.html")

    return flask_app
