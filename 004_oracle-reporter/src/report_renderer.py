"""
Renders risk summary data as an HTML report using Jinja2.
"""
import logging
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_html(rows: list[dict[str, Any]], output_path: str) -> str:
    """Render rows as HTML report and write to output_path. Returns file path."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("report.html.j2")

    html = template.render(
        rows=rows,
        generated_at=date.today().isoformat(),
        total_portfolios=len({r["portfolio_id"] for r in rows}),
    )

    Path(output_path).write_text(html, encoding="utf-8")
    logger.info("Rendered HTML report", extra={"path": output_path, "rows": len(rows)})
    return output_path
