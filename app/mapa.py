"""Mapa héroe satelital (DESIGN.md §6.1). Función pura: datos de zonas -> pydeck.Deck, sin Streamlit.

Las zonas de zonas.json son puntos, no polígonos reales: cada una se dibuja como un cuadro
aproximado alrededor del punto (por defecto ±1 km, igual que la ventana de NDVI de MODIS).
"""
from __future__ import annotations

import math

import pandas as pd
import pydeck as pdk

ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ATRIBUCION = "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community"
# Mapa base satelital como estilo MapLibre con fuente raster. Un TileLayer de deck.gl no sirve aquí:
# pintar teselas de imagen exige una función JS (renderSubLayers) que pydeck no puede enviar. Y el visor
# de Streamlit solo acepta el estilo como URL (con un objeto falla en el navegador), así que el estilo vive
# en app/static/esri_satelite.json (servido en app/static/ con server.enableStaticServing). Ruta relativa:
# así también funciona si la app se publica bajo un subdirectorio.
URL_ESTILO = "app/static/esri_satelite.json"
ESTILO_SATELITE = {          # contenido de ese archivo; tests/test_mapa.py comprueba que coinciden
    "version": 8,
    "sources": {"esri": {"type": "raster", "tiles": [ESRI_IMAGERY], "tileSize": 256, "maxzoom": 19,
                         "attribution": ATRIBUCION}},
    "layers": [{"id": "esri", "type": "raster", "source": "esri"}],
}
AMBAR = [232, 181, 58]          # --field-amber
FORESTA = [28, 42, 30]          # --forest-900
CREMA = [250, 250, 246]
RELLENO_ALFA = 64               # 25 % de 255
KM_LAT, KM_LON = 110.574, 111.320


def cuadro(lat: float, lon: float, medio_lado_km: float = 1.0) -> list[list[float]]:
    """Anillo [lon, lat] (cerrado) de un cuadro de lado 2*medio_lado_km centrado en el punto."""
    dlat = medio_lado_km / KM_LAT
    dlon = medio_lado_km / (KM_LON * math.cos(math.radians(lat)))
    return [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]


def construir_mapa(zonas: pd.DataFrame, seleccionada: str, etiquetas: dict[str, str],
                   medio_lado_km: float = 1.0, zoom: float = 9.85, corrimiento_lon: float = -0.13,
                   corrimiento_lat: float = 0.02) -> pdk.Deck:
    """zonas: columnas id, nombre, lat, lon. etiquetas: id -> texto (puede tener '\\n'). Devuelve el Deck."""
    # La zona analizada se distingue en el contorno Y en la etiqueta: ámbar con texto bosque (≈8:1),
    # las demás en bosque translúcido con texto crema. Así se reconoce sin depender del grosor de 2 px vs 5 px.
    filas = [{
        "id": z.id, "poligono": cuadro(z.lat, z.lon, medio_lado_km), "lon": z.lon, "lat": z.lat,
        "ancho": 5 if z.id == seleccionada else 2, "etiqueta": etiquetas.get(z.id, z.nombre),
        "fondo": [*AMBAR, 255] if z.id == seleccionada else [*FORESTA, 215],
        "tinta": [*FORESTA, 255] if z.id == seleccionada else [*CREMA, 255],
        "tam": 15 if z.id == seleccionada else 13,
    } for z in zonas.itertuples()]
    datos = pd.DataFrame(filas)

    poligonos = pdk.Layer(
        "PolygonLayer", data=datos, id="zonas", get_polygon="poligono", stroked=True, filled=True,
        get_fill_color=[*AMBAR, RELLENO_ALFA], get_line_color=[*AMBAR, 255],
        get_line_width="ancho", line_width_units="'pixels'", line_width_min_pixels=2)
    textos = pdk.Layer(
        "TextLayer", data=datos, id="etiquetas", get_position=["lon", "lat"], get_text="etiqueta",
        # pydeck convierte el texto sin comillas en expresión JS: los literales van entre comillas simples
        get_size="tam", get_color="tinta", font_family="'Inter, system-ui, sans-serif'", font_weight=600,
        character_set="'auto'", background=True, get_background_color="fondo",
        background_padding=[8, 5], get_pixel_offset=[0, -46], get_text_anchor="'middle'",
        get_alignment_baseline="'bottom'")
    # Centro corrido al oeste: las zonas quedan a la derecha, fuera del panel flotante (izquierda, 344 px);
    # y un poco al norte para que la etiqueta de la zona más al norte no se salga por arriba.
    vista = pdk.ViewState(latitude=float(zonas["lat"].mean()) + corrimiento_lat,
                          longitude=float(zonas["lon"].mean()) + corrimiento_lon, zoom=zoom, pitch=0)
    return pdk.Deck(layers=[poligonos, textos], initial_view_state=vista, map_provider=None,
                    map_style=URL_ESTILO, tooltip=False)
