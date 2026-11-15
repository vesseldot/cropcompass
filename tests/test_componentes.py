"""Pruebas de app/componentes.py: HTML escapado, de una sola línea y con estado accesible."""
from app import componentes as C


def test_html_en_una_linea_y_escapado():
    html = C.chip_metrica("calor", "<b>3</b>", "Heat & risk", 'tip "x"', "risk")
    assert "\n" not in html
    assert "<b>3</b>" not in html and "&lt;b&gt;3&lt;/b&gt;" in html
    assert "Heat &amp; risk" in html


def test_barra_apilada_anchos_y_leyenda_con_texto():
    html = C.barra_apilada([("Climate fit", 20.0, "#111", "a"), ("Water saving", 15.5, "#222", "b")])
    assert "width:20.0%" in html and "width:15.5%" in html
    assert "Climate fit <b>20</b>" in html          # la leyenda nombra cada tramo: no solo color


def test_tono_funciono_umbrales():
    assert C.tono_funciono(6, 6) == "ok" and C.tono_funciono(5, 6) == "ok"
    assert C.tono_funciono(3, 6) == "warn" and C.tono_funciono(2, 6) == "risk"
    assert C.tono_funciono(0, 0) == "warn"


def test_chip_estado_lleva_icono_y_texto():
    html = C.chip_estado("Worked in 5 of 6 years", "ok")
    assert "<svg" in html and "Worked in 5 of 6 years" in html
