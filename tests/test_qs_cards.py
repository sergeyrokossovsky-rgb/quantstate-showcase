import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qs_cards import card_context, render_html, render_text, vol_color  # noqa: E402

ROWS = [{"symbol": "ES", "vol": 92, "range_med": "1.48%", "range_lo": "0.86%", "range_hi": "2.70%", "p_strong": 0.31,
         "why": "implied vol elevated, wide overnight range"},
        {"symbol": "NQ", "vol": 40, "range_med": "1.20%", "range_lo": "0.70%", "range_hi": "2.10%", "p_strong": 0.12,
         "why": "<script>x</script>"}]


def test_html_and_text_render():
    ctx = card_context(ROWS, "Market state", "Mon 08:32 CT")
    html = render_html(ctx)
    assert "Market state" in html and "31%" in html and "width:92%" in html
    assert "<script>x</script>" not in html            # autoescaped
    txt = render_text(ctx)
    assert txt.splitlines()[1].startswith("ES: stress 92") and "P(strong day) 12%" in txt


def test_colors():
    assert vol_color(95) == "#ef4444" and vol_color(75) == "#f59e0b" and vol_color(10) == "#10b981"
