"""Stage 4 — HTML and Markdown reports generated from the validated textX model."""

from resumelens.visualization.renderer import (
    TEMPLATE_PATH,
    render_html,
    render_markdown_report,
    write_visualization,
)

__all__ = ["TEMPLATE_PATH", "render_html", "render_markdown_report", "write_visualization"]
