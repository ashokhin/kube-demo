import csv
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.repository import OrderSummary

# Templates are bundled with the application source; FileSystemLoader resolves
# paths relative to the caller — use __file__ to make it work regardless of CWD.
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)


def render_json(summary: OrderSummary, output_path: str) -> str:
    # mkdir -p: creates intermediate directories on first run when the PVC is empty.
    Path(output_path).mkdir(parents=True, exist_ok=True)
    # Date range in filename makes reports idempotent: re-running on the same day
    # overwrites the previous file instead of accumulating duplicates.
    filename = f"orders_{summary.period_start.date()}_{summary.period_end.date()}.json"
    filepath = os.path.join(output_path, filename)

    data = {
        "period_start": summary.period_start.isoformat(),
        "period_end": summary.period_end.isoformat(),
        "total_orders": summary.total_orders,
        "by_status": {
            "pending": summary.pending,
            "confirmed": summary.confirmed,
            "cancelled": summary.cancelled,
        },
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


def render_csv(summary: OrderSummary, output_path: str) -> str:
    Path(output_path).mkdir(parents=True, exist_ok=True)
    filename = f"orders_{summary.period_start.date()}_{summary.period_end.date()}.csv"
    filepath = os.path.join(output_path, filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["period_start", summary.period_start.isoformat()])
        writer.writerow(["period_end", summary.period_end.isoformat()])
        writer.writerow(["total_orders", summary.total_orders])
        writer.writerow(["pending", summary.pending])
        writer.writerow(["confirmed", summary.confirmed])
        writer.writerow(["cancelled", summary.cancelled])

    return filepath


def render_html(summary: OrderSummary, output_path: str) -> str:
    """Render an HTML report using the Jinja2 template in src/templates/."""
    Path(output_path).mkdir(parents=True, exist_ok=True)
    filename = f"orders_{summary.period_start.date()}_{summary.period_end.date()}.html"
    filepath = os.path.join(output_path, filename)

    total = summary.total_orders or 1  # avoid division by zero when no orders exist

    rows = [
        {"status": "pending",   "count": summary.pending,   "pct": summary.pending   / total * 100},
        {"status": "confirmed", "count": summary.confirmed, "pct": summary.confirmed / total * 100},
        {"status": "cancelled", "count": summary.cancelled, "pct": summary.cancelled / total * 100},
    ]

    template = _jinja_env.get_template("report.html.j2")
    html = template.render(
        period_start=summary.period_start.date(),
        period_end=summary.period_end.date(),
        generated_at=summary.period_end.strftime("%Y-%m-%d %H:%M UTC"),
        rows=rows,
        total_orders=summary.total_orders,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath
