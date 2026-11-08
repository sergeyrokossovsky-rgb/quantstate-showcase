"""qs_cards — render a market-state card (HTML → PNG) for Telegram, with a plain-text fallback.

Production pattern from a live system: the PNG is rendered by a headless browser from a Jinja2 template;
if rendering or delivery fails, the same context is sent as text so the user always gets the information.

Author: Sergei Rokossovskii (QuantState LLC). Sample data only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATES = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined,
                   autoescape=select_autoescape(["html"]))


def vol_color(v: float) -> str:
    return "#ef4444" if v >= 90 else "#f59e0b" if v >= 70 else "#8a8f9e" if v >= 25 else "#10b981"


def card_context(rows, title: str, stamp: str) -> Dict[str, Any]:
    """rows: [{"symbol", "vol" (0..100), "range_med", "range_lo", "range_hi", "p_strong" (0..1), "why"}]"""
    out = []
    for r in rows:
        v = float(r["vol"])
        out.append({**r, "vol_w": f"{max(0.0, min(100.0, v)):.0f}", "color": vol_color(v),
                    "p_txt": f"{100 * float(r['p_strong']):.0f}%"})
    return {"title": title, "stamp": stamp, "rows": out, "card_w": 600}


def render_html(ctx: Dict[str, Any], template: str = "market_card.html") -> str:
    return _env.get_template(template).render(**ctx)


def render_text(ctx: Dict[str, Any]) -> str:
    lines = [f"{ctx['title']} · {ctx['stamp']}"]
    for r in ctx["rows"]:
        lines.append(f"{r['symbol']}: stress {r['vol']:.0f} · range {r['range_med']} ({r['range_lo']}–{r['range_hi']}) "
                     f"· P(strong day) {r['p_txt']}")
    return "\n".join(lines)


def render_png(html: str, width: int = 640) -> Optional[bytes]:
    """Headless Chromium screenshot of the card element; returns None if Playwright is unavailable."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": width, "height": 400}, device_scale_factor=2)
            page.set_content(html, wait_until="networkidle")
            png = page.locator(".card").screenshot(type="png")
            b.close()
            return png
    except Exception:
        return None
