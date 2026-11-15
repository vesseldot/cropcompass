"""Pruebas de app/mapa.py: geometría de las zonas y capas del mapa héroe."""
import json
import math
from pathlib import Path

import pandas as pd

from app import mapa as M

ZONAS = pd.DataFrame([
    {"id": "a", "nombre": "A", "lat": 18.655, "lon": -99.19},
    {"id": "b", "nombre": "B", "lat": 18.81, "lon": -98.95},
])


def test_cuadro_cerrado_y_de_lado_correcto():
    anillo = M.cuadro(18.655, -99.19, 1.0)
    assert anillo[0] == anillo[-1] and len(anillo) == 5
    alto_km = (anillo[2][1] - anillo[0][1]) * M.KM_LAT
    ancho_km = (anillo[1][0] - anillo[0][0]) * M.KM_LON * math.cos(math.radians(18.655))
    assert abs(alto_km - 2.0) < 1e-6 and abs(ancho_km - 2.0) < 1e-6


def test_mapa_tiene_teselas_poligonos_y_etiquetas():
    deck = M.construir_mapa(ZONAS, "a", {"a": "A\nSugarcane · worked 5/6 yrs"})
    assert [c.type for c in deck.layers] == ["PolygonLayer", "TextLayer"]
    assert deck.map_style == M.URL_ESTILO
    fuente = M.ESTILO_SATELITE["sources"]["esri"]
    assert "World_Imagery" in fuente["tiles"][0] and "Esri" in fuente["attribution"]


def test_archivo_de_estilo_coincide_con_el_codigo():
    archivo = Path(__file__).resolve().parents[1] / M.URL_ESTILO
    assert json.loads(archivo.read_text(encoding="utf-8")) == M.ESTILO_SATELITE


def test_props_de_texto_no_se_vuelven_expresiones():
    """pydeck convierte el texto sin comillas en expresión JS ('@@=...'); en props que no son accessors
    eso rompe el mapa (contorno gigante que tapa todo, etiquetas que no se dibujan)."""
    deck = M.construir_mapa(ZONAS, "a", {})
    poligonos, textos = (vars(c) for c in deck.layers)
    assert poligonos["line_width_units"] == "pixels"
    assert textos["character_set"] == "auto" and not textos["font_family"].startswith("@@=")


def test_zona_seleccionada_tiene_contorno_mas_grueso():
    deck = M.construir_mapa(ZONAS, "b", {})
    datos = pd.DataFrame(deck.layers[0].data).set_index("id")   # pydeck lo guarda como DataFrame o lista según versión
    assert datos.loc["b", "ancho"] > datos.loc["a", "ancho"]
    assert datos.loc["b", "fondo"][:3] == M.AMBAR and datos.loc["a", "fondo"][:3] == M.FORESTA
    assert datos.loc["a", "etiqueta"] == "A"      # sin etiqueta dada, usa el nombre
