"""Interfaz Streamlit. Solo usa funciones de core/ y componentes nativos.

Idioma base inglés (requisito del concurso), con español opcional, modo oscuro y modo guía.
Ejecutar:   streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:          # streamlit agrega app/ al path, no la raíz del repo
    sys.path.insert(0, str(RAIZ))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit import config as st_config

from core import datos
from core import explicacion as X
from core import i18n
from core import indicadores as I
from core import periodos as P
from core import pronostico as F
from core import rotaciones as R
from app import componentes as CP
from app import mapa as M

APP_TITLE = "CropCompass"   # nombre del proyecto

# Paleta validada (skill dataviz, slots 1-4 en orden fijo; pasa CVD en claro y en oscuro).
# Cada modo usa sus propios pasos de los mismos tonos.
PALETAS = {
    False: dict(criterio={"climate": "#2a78d6", "water": "#eb6834", "soil": "#1baf7a", "income": "#eda100"},
                lluvia="#2a78d6", ndvi="#008300", gris="#9e9d98", tinta="#52514e", hueco="#ffffff",
                banda_ndvi="rgba(0,131,0,0.15)", banda_prono="rgba(42,120,214,0.18)",
                etapas=["#2a78d6", "#eb6834", "#1baf7a"], escala_ndvi="Greens"),
    True: dict(criterio={"climate": "#3987e5", "water": "#d95926", "soil": "#199e70", "income": "#c98500"},
               lluvia="#3987e5", ndvi="#0ca30c", gris="#8a8983", tinta="#c3c2b7", hueco="#0e1117",
               banda_ndvi="rgba(12,163,12,0.22)", banda_prono="rgba(57,135,229,0.25)",
               etapas=["#3987e5", "#d95926", "#199e70"],
               escala_ndvi=[[0, "#15301a"], [0.5, "#1f7a2a"], [1, "#7be585"]]),
}
NOMBRE_CRITERIO = {"climate": "Climate fit", "water": "Water saving", "soil": "Soil health", "income": "Income"}
NOMBRE_MODELO = {
    "seasonal_naive": "Seasonal naive (baseline)", "prophet": "Prophet", "prophet_log1p": "Prophet (log1p)",
    "prophet_rain_lags": "Prophet + rain lags", "linear": "Linear regression (sliding window)",
    "linear_log1p": "Linear regression, log1p", "random_forest": "Random forest (sliding window)",
    "random_forest_log1p": "Random forest, log1p",
}
NOMBRE_INTERVALO = {"prophet_80": "Prophet 80% interval", "rf_trees_p10_p90": "random-forest trees p10-p90",
                    "empirical_abs_test_error_p80": "± 80th percentile of the model's test error",
                    "none": "no interval"}
VARIABLES = {"precip_mm_21d": "Rainfall (mm per 21 days)", "ndvi": "NDVI (vegetation greenness)"}
OPCIONES_RIEGO = {"default": "Zone default", "irrigated": "Irrigated", "rainfed": "Rainfed"}
P_CORTAS = [f"P{p:02d}" for p in range(1, 18)]

st.set_page_config(page_title=APP_TITLE, page_icon="🌱", layout="wide", initial_sidebar_state="collapsed")

# Base visual (DESIGN.md §3-5): un solo bloque CSS, cargado una vez por ejecución. Se rellena más abajo,
# cuando ya se sabe si el modo oscuro está activo (cambia los tokens de panel y hoja).
slot_css = st.empty()
CSS_BASE = Path(__file__).with_name("estilos.css").read_text(encoding="utf-8")
CSS_OSCURO = (":root{--panel:rgba(18,24,19,0.94);--panel-solid:#151b16;--sheet:#0e1117;--accent:#8FC79A;"
              "--ink-2:#c9d3c4;--muted-strong:#b4bcae;--forest-700:#8FC79A;--card:#161b22;--line:rgba(255,255,255,0.14);"
              "--muted:#9aa395;--line-hover:rgba(143,199,154,0.45);--shadow-panel:0 8px 32px rgba(0,0,0,0.5);}")

# Esqueleto de la página (DESIGN.md §6): cabecera, mapa héroe con el panel flotante encima, hoja de resultados.
# Se declaran aquí, en orden visual, y se rellenan donde estén sus datos.
cabecera = st.container()
hero = st.container(key="hero")
with hero:
    slot_mapa = st.container(key="mapa_heroe")
    panel = st.container(key="panel_analisis")
hoja = st.container(key="hoja")


# ---------------------------------------------------------------- datos (cacheados)

@st.cache_data(show_spinner=False)
def cargar_base():
    return (P.cargar_serie_21d(), datos.cargar_clima_diario(), datos.cargar_zonas(),
            datos.cargar_cultivos(), datos.cargar_rotaciones())


@st.cache_data(show_spinner=False)
def cargar_pronosticos():
    return F.cargar_resultados(regenerar_si_falta=True)


@st.cache_data(show_spinner=False)
def diagnostico(zona: str, umbral_ndvi: float) -> dict:
    serie, clima, *_ = cargar_base()
    return I.diagnostico(serie, clima, zona, umbral_ndvi=umbral_ndvi)


@st.cache_data(show_spinner=False)
def ranking(zona: str, pesos: tuple, cultivo_actual: str | None, riego: bool | None, umbral_ndvi: float,
            cultivos: pd.DataFrame, idioma: str) -> list[dict]:
    serie, _, zonas, _, rotaciones = cargar_base()
    lluvia, anio = R.cargar_lluvia_outlook(zona)
    res = R.rankear(zona, dict(pesos), serie=serie, cultivos=cultivos, rotaciones=rotaciones, zonas=zonas,
                    cultivo_actual=cultivo_actual, riego=riego, umbral_ndvi=umbral_ndvi,
                    lluvia_outlook=lluvia, anio_outlook=anio)
    return X.explicar_ranking(res, diagnostico(zona, umbral_ndvi), zonas.set_index("id").loc[zona].to_dict(), idioma)


try:
    SERIE, CLIMA, ZONAS, CULTIVOS_BASE, ROTACIONES = cargar_base()
except Exception as e:  # sin datos no hay app: mensaje claro y alto
    st.error(f"Could not load the project data: {e}. Run `python -m core.periodos` to rebuild it.")
    st.stop()

ZONA_INFO = ZONAS.set_index("id")
ZONAS_IDS = ZONAS["id"].tolist()
CULTIVOS_ACTUALES = sorted({c for r in ROTACIONES for c in r.get("actual_para", [])})


# ---------------------------------------------------------------- preferencias: idioma, tema, guía

# 'sel' guarda las elecciones en forma canónica (no dependen del idioma). Al cambiar de idioma los
# widgets se recrean con otra etiqueta, así que toman su valor inicial de una copia de 'sel' ('defs')
# que solo se renueva en ese momento: dentro de un mismo idioma los valores iniciales no cambian.
sel = st.session_state.setdefault("sel", {
    "idioma": "en", "oscuro": False, "guia": False, "zona": ZONAS_IDS[0], "cultivo": "__zona__",
    "riego": "default", "agua": 5, "suelo": 5, "ingreso": 5, "clima": 5, "umbral": I.UMBRAL_NDVI_DESNUDO,
    "variable": "precip_mm_21d"})

with panel:
    ajustes = st.popover("Settings / Ajustes", use_container_width=True)
with ajustes:
    nombres_idioma = list(i18n.IDIOMAS)
    idioma = i18n.IDIOMAS[st.selectbox("Language / Idioma", nombres_idioma, key="idioma")]

if st.session_state.get("defs_idioma") != idioma:
    st.session_state["defs"], st.session_state["defs_idioma"] = dict(sel), idioma
defs = st.session_state["defs"]
sel["idioma"] = idioma


def T(texto: str) -> str:
    return i18n.tr(texto, idioma)


def etq(texto):
    """Etiqueta de periodo en el idioma activo: 'P08 (May 28 – Jun 17)' -> 'P08 (28 may – 17 jun)'."""
    return i18n.fechas(texto, idioma)


def nombre_cultivo(cultivo_id: str) -> str:
    fila = CULTIVOS_BASE[CULTIVOS_BASE["id"] == cultivo_id]
    if fila.empty:
        return cultivo_id
    es = fila["nombre_es"].iloc[0] if "nombre_es" in fila else None
    return es if idioma == "es" and isinstance(es, str) else fila["nombre"].iloc[0]


def nr(r: dict) -> str:
    return r.get("nombre_es", r["nombre"]) if idioma == "es" else r["nombre"]


def nc(e: dict) -> str:
    return e.get("cultivo_es", e["cultivo"]) if idioma == "es" else e["cultivo"]


with ajustes:
    oscuro = st.toggle(T("Dark mode"), value=defs["oscuro"], key=f"oscuro_{idioma}")
    guia = st.toggle(T("Guide mode"), value=defs["guia"], key=f"guia_{idioma}")
sel.update(oscuro=oscuro, guia=guia)

# Tema: Streamlit envía el tema al navegador al inicio de cada ejecución, así que se cambia la opción y
# se vuelve a ejecutar. La opción es del servidor: cada sesión la corrige si otra la cambió.
# La re-ejecución se hace AL FINAL del script: si se interrumpe antes de dibujar el formulario,
# Streamlit descarta el estado de los controles no dibujados y se pierde la zona elegida.
_base = "dark" if oscuro else "light"
# Color de selección (sliders, radios, pestaña activa): verde bosque, NO naranja. El naranja queda solo para
# Analyze (DESIGN.md §3, lo pinta estilos.css). En oscuro, un verde claro para mantener contraste AA.
_primario = "#8FC79A" if oscuro else "#2F4A32"
try:
    _cambiar_tema = (st_config.get_option("theme.base") != _base
                     or st_config.get_option("theme.primaryColor") != _primario)
    if _cambiar_tema:
        st_config.set_option("theme.base", _base)
        st_config.set_option("theme.primaryColor", _primario)
except Exception:
    _cambiar_tema = False

PAL = PALETAS[oscuro]
slot_css.markdown(f"<style>{CSS_BASE}{CSS_OSCURO if oscuro else ''}</style>", unsafe_allow_html=True)


def nota_guia(nombre: str) -> None:
    if guia:
        st.info(i18n.bloque(nombre, idioma), icon="🧭")


# ---------------------------------------------------------------- utilidades de gráficas

def rangos_consecutivos(periodos: list[int]) -> list[tuple[int, int]]:
    out = []
    for p in sorted(periodos):
        if out and p == out[-1][1] + 1:
            out[-1] = (out[-1][0], p)
        else:
            out.append((p, p))
    return out


def sombrear_desnudos(fig, desnudos, filas=(1,), texto=True):
    for i, (a, b) in enumerate(rangos_consecutivos(desnudos)):
        for fila in filas:
            fig.add_vrect(x0=a - 1.5, x1=b - 0.5, fillcolor=PAL["gris"], opacity=0.18, line_width=0,
                          layer="below", row=fila, col=1)
        if texto and i == 0:
            fig.add_annotation(x=(a + b) / 2 - 1, y=0.98, xref="x", yref="y domain", text=T("bare soil"),
                               showarrow=False, font=dict(size=11, color=PAL["tinta"]), yanchor="top")


def figura_diagnostico(diag: dict) -> go.Figure:
    clim = diag["climatologia"]
    etiquetas = clim["etiqueta"].map(etq)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=(T("Rainfall per 21-day period (mm, 2020-2025 mean ± 1 SD)"),
                                        T("NDVI, vegetation greenness (2020-2025 mean ± 1 SD)")))
    fig.add_bar(x=P_CORTAS, y=clim["precip_media"], marker_color=PAL["lluvia"], name=T("Rainfall"),
                error_y=dict(type="data", array=clim["precip_std"], color=PAL["gris"], thickness=1),
                customdata=etiquetas, hovertemplate="%{customdata}<br>%{y:.0f} mm<extra></extra>",
                row=1, col=1)
    sup, inf = clim["ndvi_media"] + clim["ndvi_std"], clim["ndvi_media"] - clim["ndvi_std"]
    fig.add_scatter(x=P_CORTAS, y=sup, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False,
                    row=2, col=1)
    fig.add_scatter(x=P_CORTAS, y=inf, mode="lines", line=dict(width=0), fill="tonexty",
                    fillcolor=PAL["banda_ndvi"], hoverinfo="skip", showlegend=False, row=2, col=1)
    fig.add_scatter(x=P_CORTAS, y=clim["ndvi_media"], mode="lines+markers", name="NDVI",
                    line=dict(color=PAL["ndvi"], width=2), marker=dict(size=8),
                    customdata=etiquetas, hovertemplate="%{customdata}<br>NDVI %{y:.2f}<extra></extra>",
                    row=2, col=1)
    fig.add_hline(y=diag["umbrales"]["ndvi_desnudo"], line=dict(color=PAL["tinta"], width=1, dash="dot"),
                  annotation_text=T("bare-soil threshold {umbral:.2f}").format(umbral=diag["umbrales"]["ndvi_desnudo"]),
                  annotation_position="bottom", row=2, col=1)
    sombrear_desnudos(fig, diag["suelo_desnudo"], filas=(1, 2))
    fig.update_yaxes(title_text="mm", row=1, col=1)
    fig.update_yaxes(title_text="NDVI", row=2, col=1)
    fig.update_layout(height=560, showlegend=False, margin=dict(t=60, b=20, l=10, r=10), bargap=0.25)
    return fig


def figura_ndvi_anual(serie_zona: pd.DataFrame) -> go.Figure:
    tabla = serie_zona.pivot(index="anio", columns="periodo", values="ndvi")
    fig = go.Figure(go.Heatmap(z=tabla.to_numpy(), x=P_CORTAS, y=[str(a) for a in tabla.index],
                               colorscale=PAL["escala_ndvi"], zmin=0.15, zmax=0.65, xgap=2, ygap=2,
                               colorbar=dict(title="NDVI"),
                               hovertemplate="%{y} %{x}<br>NDVI %{z:.2f}<extra></extra>"))
    fig.update_layout(height=260, margin=dict(t=10, b=10, l=10, r=10), yaxis=dict(autorange="reversed"))
    return fig


def figura_pronostico(zona: str, var: str, prono: pd.DataFrame, prueba: pd.DataFrame) -> go.Figure:
    hist = SERIE[SERIE["zona"] == zona].sort_values("fecha_inicio")
    fig = go.Figure()
    fig.add_scatter(x=hist["fecha_inicio"], y=hist[var], mode="lines", name=T("Observed (NASA data)"),
                    line=dict(color=PAL["tinta"], width=2))
    p_mejor = prueba[(prueba["zona"] == zona) & (prueba["variable"] == var)]
    g = prono[(prono["zona"] == zona) & (prono["variable"] == var)]
    mejor = g[g["es_mejor"]]
    nombre = T(NOMBRE_MODELO.get(mejor["modelo"].iloc[0], mejor["modelo"].iloc[0]))
    pt = p_mejor[p_mejor["modelo"] == mejor["modelo"].iloc[0]]
    fig.add_scatter(x=pt["fecha_inicio"], y=pt["yhat"], mode="lines",
                    name=T("{modelo}: test-period forecast").format(modelo=nombre),
                    line=dict(color=PAL["lluvia"], width=2, dash="dash"))
    if mejor["yhat_lower"].notna().any():
        fig.add_scatter(x=mejor["fecha_inicio"], y=mejor["yhat_upper"], mode="lines", line=dict(width=0),
                        hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=mejor["fecha_inicio"], y=mejor["yhat_lower"], mode="lines", line=dict(width=0),
                        fill="tonexty", fillcolor=PAL["banda_prono"], name=T("80% interval"),
                        hoverinfo="skip")
    fig.add_scatter(x=mejor["fecha_inicio"], y=mejor["yhat"], mode="lines+markers",
                    name=T("{modelo}: {anio} forecast").format(modelo=nombre, anio=int(mejor["anio"].iloc[0])),
                    line=dict(color=PAL["lluvia"], width=2), marker=dict(size=8),
                    customdata=mejor["etiqueta"].map(etq),
                    hovertemplate="%{customdata}<br>%{y:.2f}<extra></extra>")
    base = g[g["modelo"] == F.BASELINE]
    if not mejor["modelo"].eq(F.BASELINE).all():
        fig.add_scatter(x=base["fecha_inicio"], y=base["yhat"], mode="lines", name=T("Seasonal naive baseline"),
                        line=dict(color=PAL["criterio"]["water"], width=2, dash="dot"))
    if len(pt):
        fig.add_vline(x=pt["fecha_inicio"].min(), line=dict(color=PAL["gris"], width=1, dash="dot"))
        fig.add_annotation(x=pt["fecha_inicio"].min(), y=1, yref="paper", text=T("test period →"),
                           showarrow=False, xanchor="left", font=dict(size=11, color=PAL["tinta"]))
    fig.update_layout(height=430, hovermode="x unified", margin=dict(t=30, b=10, l=10, r=10),
                      yaxis_title=T(VARIABLES[var]), legend=dict(orientation="h", y=-0.15, traceorder="normal"))
    return fig


def figura_desglose(res: list[dict]) -> go.Figure:
    nombres = [f"#{r['rango']} {nr(r)}" + (T(" (current)") if r["es_actual"] else "") for r in res][::-1]
    fig = go.Figure()
    for c in ("climate", "water", "soil", "income"):
        criterio = T(NOMBRE_CRITERIO[c])
        fig.add_bar(y=nombres, x=[r["contribuciones"][c] for r in res][::-1], orientation="h", name=criterio,
                    marker=dict(color=PAL["criterio"][c], line=dict(color=PAL["hueco"], width=2)),
                    hovertemplate=T("{criterio}: %{{x:.1f}} pts").format(criterio=criterio) + "<extra></extra>")
    fig.update_layout(barmode="stack", height=90 + 42 * len(res), margin=dict(t=10, b=10, l=10, r=10),
                      xaxis=dict(title=T("Score (0-100) = sum of weighted criteria"), range=[0, 100]),
                      legend=dict(orientation="h", y=1.08, traceorder="normal"))
    return fig


def figura_calendario(r: dict) -> go.Figure:
    fig = go.Figure()
    filas = []
    for i, e in enumerate(r["etapas"]):
        filas.append(nc(e))
        fig.add_scatter(x=[P_CORTAS[p - 1] for p in e["periodos"]], y=[nc(e)] * len(e["periodos"]),
                        mode="markers", marker=dict(symbol="square", size=16, color=PAL["etapas"][i % 3]),
                        name=nc(e), hovertemplate=f"{nc(e)}<br>%{{x}}<extra></extra>")
    if r["desnudos_zona"]:
        filas.append(T("Bare soil today (NDVI)"))
        fig.add_scatter(x=[P_CORTAS[p - 1] for p in r["desnudos_zona"]], y=[filas[-1]] * len(r["desnudos_zona"]),
                        mode="markers", marker=dict(symbol="square", size=16, color=PAL["gris"]),
                        name=T("Bare soil today"), hovertemplate=T("Bare soil today") + "<br>%{x}<extra></extra>")
    # fondo transparente: el calendario vive dentro de la tarjeta y no debe verse como otra caja (modo oscuro)
    fig.update_layout(height=50 + 32 * len(filas), showlegend=False, margin=dict(t=5, b=5, l=5, r=5),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(categoryorder="array", categoryarray=P_CORTAS, range=[-0.5, 16.5],
                                 tickmode="array", tickvals=P_CORTAS[::4], tickangle=0, tickfont=dict(size=10)),
                      yaxis=dict(categoryorder="array", categoryarray=filas[::-1]))
    return fig


# ---------------------------------------------------------------- barra lateral: formulario

with panel:
    st.markdown(f'<div class="panel-titulo">{T("Your farm")}</div>', unsafe_allow_html=True)
    with st.form("entrada", border=False):
        zona = st.selectbox(T("Zone (Morelos, Mexico)"), ZONAS_IDS, index=ZONAS_IDS.index(defs["zona"]),
                            format_func=lambda z: ZONA_INFO.loc[z, "nombre"], key=f"zona_{idioma}")
        opciones_cultivo = ["__zona__"] + CULTIVOS_ACTUALES
        opcion_cultivo = st.selectbox(
            T("Current crop"), opciones_cultivo, index=opciones_cultivo.index(defs["cultivo"]),
            format_func=lambda c: T("Typical crop for this zone") if c == "__zona__" else nombre_cultivo(c),
            key=f"cultivo_{idioma}")
        opcion_riego = st.radio(T("Irrigation"), list(OPCIONES_RIEGO), index=list(OPCIONES_RIEGO).index(defs["riego"]),
                                format_func=lambda o: T(OPCIONES_RIEGO[o]), horizontal=True, key=f"riego_{idioma}",
                                help=T("With irrigation, rainfall does not limit crop suitability."))
        st.markdown(T("**Your priorities** (relative weights)"))
        if guia:
            st.caption(i18n.bloque("guia_prioridades", idioma))
        col_a, col_b = st.columns(2)
        with col_a:
            w_agua = st.slider(T("Water saving"), 0, 10, defs["agua"], key=f"w_agua_{idioma}")
            w_ingreso = st.slider(T("Income"), 0, 10, defs["ingreso"], key=f"w_ingreso_{idioma}")
        with col_b:
            w_suelo = st.slider(T("Soil health"), 0, 10, defs["suelo"], key=f"w_suelo_{idioma}")
            w_clima = st.slider(T("Climate fit"), 0, 10, defs["clima"], key=f"w_clima_{idioma}")
        with st.expander(T("Advanced")):
            umbral_ndvi = st.slider(
                T("Bare-soil NDVI threshold"), 0.15, 0.45, defs["umbral"], 0.01, key=f"umbral_{idioma}",
                help=T("A 21-day period counts as bare soil when its mean NDVI is below this."))
        st.form_submit_button(T("Analyze"), type="primary", use_container_width=True)
    st.caption(T("Crop parameters are hypotheses pending validation. "
                 "This tool supports, not replaces, farmer judgment."))

sel.update(zona=zona, cultivo=opcion_cultivo, riego=opcion_riego, agua=w_agua, suelo=w_suelo,
           ingreso=w_ingreso, clima=w_clima, umbral=umbral_ndvi)
cultivo_actual = None if opcion_cultivo == "__zona__" else opcion_cultivo
riego = {"default": None, "irrigated": True, "rainfed": False}[opcion_riego]
pesos = {"water": w_agua, "soil": w_suelo, "income": w_ingreso, "climate": w_clima}
info = ZONA_INFO.loc[zona]
riego_efectivo = bool(info["riego"]) if riego is None else riego
cultivo_efectivo = cultivo_actual or list(info["cultivos_actuales"])[0]
aviso_zona = info.get("aviso_es") if idioma == "es" and isinstance(info.get("aviso_es"), str) else info.get("aviso")

# ---------------------------------------------------------------- cabecera

with cabecera:
    st.title(APP_TITLE)       # el 🌱 queda en la pestaña del navegador (page_icon), no como logo
    st.markdown(T("Decision support for crop rotations in **sugarcane areas of Morelos, Mexico**, built on NASA "
                  "satellite data summarized in **21-day periods** (17 per year, 2020-2025)."))
    pesos_n = R.normalizar_pesos(pesos)
    st.caption(f"**{info['nombre']}** · {T('current crop')}: **{nombre_cultivo(cultivo_efectivo)}** · "
               f"{T('irrigated') if riego_efectivo else T('rainfed')} · {T('priorities')}: "
               + ", ".join(f"{T(NOMBRE_CRITERIO[c]).lower()} {pesos_n[c]:.0%}"
                           for c in ("water", "soil", "income", "climate")))
    nota_guia("guia_inicio")

# ---------------------------------------------------------------- hoja de resultados: insight, chips y pestañas

with hoja:
    try:
        d0 = diagnostico(zona, umbral_ndvi)
        et0, t0 = d0["etiquetas"], d0["temporal"]
        seco0 = min(d0["lluvia_anual"], key=d0["lluvia_anual"].get)
        st.markdown(CP.tarjeta_insight(
            T("In {zona}, {n_bare} of 17 periods usually leave bare soil, {n_heat} carry heat risk and "
              "{n_frost} frost risk. The driest year was {anio} ({mm:.0f} mm of rain).").format(
                zona=info["nombre"], n_bare=len(d0["suelo_desnudo"]), n_heat=len(d0["calor"]),
                n_frost=len(d0["helada"]), anio=seco0, mm=d0["lluvia_anual"][seco0])), unsafe_allow_html=True)
        st.markdown(CP.fila_chips([
            CP.chip_metrica("lluvia", f"{et0[t0['inicio']][:3]} → {et0[t0['fin']][:3]}" if t0 else T("No data"),
                            T("Rainy season"), T("First and last 21-day period with > 35 mm on average"), "info"),
            CP.chip_metrica("suelo", len(d0["suelo_desnudo"]), T("Bare-soil periods"),
                            T("Periods with mean NDVI below the threshold"), "warn"),
            CP.chip_metrica("calor", len(d0["calor"]), T("Heat-risk periods"),
                            T("≥ 3 days with Tmax ≥ 35 °C on average"), "risk"),
            CP.chip_metrica("helada", len(d0["helada"]), T("Frost-risk periods"),
                            T("Any day with Tmin ≤ 2 °C on average"), "info"),
            CP.chip_metrica("calendario", seco0, T("Driest year ({mm:.0f} mm)").format(mm=d0["lluvia_anual"][seco0]),
                            T("Lowest annual rainfall (GPM IMERG) in 2020-2025"), "warn"),
        ]), unsafe_allow_html=True)
    except Exception as e:
        st.warning(T("Could not build the diagnosis for this zone: {e}").format(e=e))

    tab_diag, tab_prono, tab_rot, tab_metodo = st.tabs(
        [T("Diagnosis"), T("Forecast"), T("Rotations"), T("Data & Method")])

# ---------------------------------------------------------------- Data & Method (primero: el editor alimenta el ranking)

with tab_metodo:
    cultivos_usados, hay_ediciones = CULTIVOS_BASE, False
    try:
        nota_guia("guia_method")
        st.subheader(T("Crop parameters: hypotheses"))
        st.info(T("These values are **hypotheses pending validation with local agronomists** (approximate ranges "
                  "inspired by FAO EcoCrop). Edit any cell and the ranking in **Rotations** updates."), icon="🧪")
        columnas = ["nombre", "tipo", "ciclo_meses", "siembra_mes", "temp_abs_min", "temp_opt_min", "temp_opt_max",
                    "temp_abs_max", "lluvia_abs_min", "lluvia_opt_min", "lluvia_opt_max", "lluvia_abs_max",
                    "tolera_helada", "agua_relativa", "fija_nitrogeno", "cubre_suelo", "mercado_local", "notas"]
        base = CULTIVOS_BASE.set_index("id")
        solo_texto = ["nombre", "tipo", "notas"]            # columnas no editables, se muestran traducidas
        vista = base.assign(tipo=base["tipo"].map(T))
        if idioma == "es":
            for col in ("nombre", "notas"):
                if f"{col}_es" in base:
                    vista[col] = base[f"{col}_es"].where(base[f"{col}_es"].notna(), base[col])
        num = lambda label, lo, hi, paso, fmt="%.0f": st.column_config.NumberColumn(
            T(label), min_value=lo, max_value=hi, step=paso, format=fmt)
        clave_editor = f"editor_cultivos_{idioma}"
        editado = st.data_editor(
            vista[columnas], key=clave_editor, num_rows="fixed", use_container_width=True, disabled=solo_texto,
            column_config={
                "_index": st.column_config.TextColumn("id"),
                "nombre": T("Crop"), "tipo": T("Type"), "notas": T("Notes"),
                "ciclo_meses": num("Cycle (months)", 1, 24, 1),
                "siembra_mes": num("Sowing month", 1, 12, 1),
                "temp_abs_min": num("Temp abs min °C", -10, 50, 1), "temp_opt_min": num("Temp opt min °C", -10, 50, 1),
                "temp_opt_max": num("Temp opt max °C", -10, 50, 1), "temp_abs_max": num("Temp abs max °C", -10, 50, 1),
                "lluvia_abs_min": num("Rain abs min mm", 0, 6000, 50), "lluvia_opt_min": num("Rain opt min mm", 0, 6000, 50),
                "lluvia_opt_max": num("Rain opt max mm", 0, 6000, 50), "lluvia_abs_max": num("Rain abs max mm", 0, 6000, 50),
                "tolera_helada": st.column_config.CheckboxColumn(T("Frost tolerant")),
                "agua_relativa": num("Water demand 0-1", 0.0, 1.0, 0.05, "%.2f"),
                "fija_nitrogeno": st.column_config.CheckboxColumn(T("Fixes nitrogen")),
                "cubre_suelo": num("Soil cover 0-1", 0.0, 1.0, 0.05, "%.2f"),
                "mercado_local": num("Local market 0-1", 0.0, 1.0, 0.05, "%.2f"),
            })
        if st.button(T("Reset crop parameters to defaults")):
            st.session_state.pop(clave_editor, None)
            st.rerun()
        candidato = editado.reset_index().rename(columns={"index": "id"})
        for col in solo_texto + ["nombre_es"]:               # el motor usa siempre los textos originales
            if col in CULTIVOS_BASE:
                candidato[col] = CULTIVOS_BASE[col].to_numpy()
        problemas = datos.validar_config(ZONAS, candidato, ROTACIONES)
        hay_ediciones = bool(st.session_state.get(clave_editor, {}).get("edited_rows"))
        if problemas:
            st.warning(T("Edited values are inconsistent, so the default parameters are used: ") + "; ".join(problemas))
            hay_ediciones = False
        else:
            cultivos_usados = candidato

        st.subheader(T("Data sources"))
        st.markdown(i18n.bloque("fuentes", idioma))
        st.subheader(T("Method"))
        st.markdown(i18n.bloque("metodo", idioma))
        st.subheader(T("Candidate rotations"))
        st.dataframe(pd.DataFrame([{
            T("Rotation"): nr(r),
            T("Crops (sowing month)"): " → ".join(f"{nombre_cultivo(e['cultivo'])} (m{e.get('siembra_mes', '?')})"
                                                  for e in r["etapas"]),
            T("Current practice for"): ", ".join(nombre_cultivo(c) for c in r.get("actual_para", [])) or "-",
        } for r in ROTACIONES]), hide_index=True, use_container_width=True)
    except Exception as e:
        st.warning(T("Could not render the data & method section: {e}").format(e=e))

# ---------------------------------------------------------------- Diagnosis

with tab_diag:
    try:
        nota_guia("guia_diagnosis")
        diag = diagnostico(zona, umbral_ndvi)      # los chips de métricas están arriba, en la cabecera de la hoja
        izq, der = st.columns([3, 1])
        with izq:
            st.plotly_chart(figura_diagnostico(diag), use_container_width=True, key="fig_diag")
        with der:
            if isinstance(aviso_zona, str):
                st.warning(aviso_zona, icon="⚠️")

        sz = SERIE[SERIE["zona"] == zona]
        anios = list(diag["lluvia_anual"])
        col_tipo, col_racha, col_calor = T("Type"), T("Dry spell (days)"), T("Heat days")
        anual = pd.DataFrame({
            T("Year"): [str(a) for a in anios],
            T("Rain (mm)"): [round(diag["lluvia_anual"][a]) for a in anios],
            col_tipo: [T(diag["tipo_anio"].get(a, "unknown")) for a in anios],
            col_racha: [diag["racha_seca_temporal"].get(a) for a in anios],
            col_calor: [int(sz.loc[sz["anio"] == a, "dias_calor"].sum()) for a in anios],
        })
        a1, a2 = st.columns(2)
        with a1:
            st.markdown(T("**Year by year**"))
            st.dataframe(anual, hide_index=True, use_container_width=True, column_config={
                col_tipo: st.column_config.TextColumn(col_tipo, help=T("dry / normal / wet by terciles of annual rain")),
                col_racha: st.column_config.NumberColumn(
                    col_racha, help=T("Longest run of days with < 1 mm inside the rainy season")),
                col_calor: st.column_config.NumberColumn(col_calor, help=T("Days with Tmax ≥ 35 °C")),
            })
        with a2:
            st.markdown(T("**Free windows for a cover crop**"))
            ventanas = diag["ventanas_libres"]
            if ventanas:
                st.dataframe(pd.DataFrame([{T("Period"): etq(v["etiqueta"]), "NDVI": v["ndvi"],
                                            T("Rain (mm)"): v["precip_mm"],
                                            T("Needs"): T("irrigation") if v["requiere_riego"] else T("rain is enough")}
                                           for v in ventanas]), hide_index=True, use_container_width=True)
            else:
                st.caption(T("No bare-soil periods detected, so no free windows."))
        st.markdown(T("**NDVI per year and 21-day period** (brighter = greener)") if oscuro
                    else T("**NDVI per year and 21-day period** (darker = greener)"))
        st.plotly_chart(figura_ndvi_anual(sz), use_container_width=True, key="fig_ndvi_anual")
        if diag["periodos_sin_ndvi"]:
            st.warning(T("No data: {n} periods have no NDVI.").format(n=diag["periodos_sin_ndvi"]))
    except Exception as e:
        st.warning(T("Could not build the diagnosis for this zone: {e}").format(e=e))

# ---------------------------------------------------------------- Forecast

with tab_prono:
    try:
        nota_guia("guia_forecast")
        met, prono, prueba = cargar_pronosticos()
        var = st.radio(T("Variable"), list(VARIABLES), index=list(VARIABLES).index(defs["variable"]),
                       format_func=lambda v: T(VARIABLES[v]), horizontal=True, key=f"variable_{idioma}")
        sel["variable"] = var
        g = met[(met["zona"] == zona) & (met["variable"] == var)]
        mejor = g[g["es_mejor"]].iloc[0]
        anio = int(prono["anio"].iloc[0])
        tipo_int = prono[(prono["zona"] == zona) & (prono["variable"] == var) & prono["es_mejor"]]["tipo_intervalo"].iloc[0]
        m1, m2, m3 = st.columns(3)
        m1.metric(T("Best model (test MAE)"), T(NOMBRE_MODELO.get(mejor["modelo"], mejor["modelo"])))
        m2.metric(T("Test MAE vs baseline"), f"{mejor['mae']:.3g}",
                  T("{pct:.0f}% error").format(pct=-mejor["mejora_vs_baseline_pct"]), delta_color="inverse",
                  help=T("Mean absolute error on the held-out last 20 % of periods"))
        m3.metric(T("Forecast horizon"), T("17 periods ({anio})").format(anio=anio))
        st.plotly_chart(figura_pronostico(zona, var, prono, prueba), use_container_width=True, key="fig_prono")
        st.caption(T("Interval: {intervalo}. Train = first {n_train} periods, test = last {n_test} (temporal split). "
                     "Future rain/temperature used as model inputs = 2020-2025 average for that period. "
                     "R² for rainfall is unstable in the dry season: read it with MAE.").format(
            intervalo=T(NOMBRE_INTERVALO.get(tipo_int, tipo_int)), n_train=int(mejor["n_train"]),
            n_test=int(mejor["n_test"])))
        col_modelo = T("Model")
        tabla = g.assign(**{
            col_modelo: g["modelo"].map(lambda m: T(NOMBRE_MODELO.get(m, m))),
            "cobertura_intervalo_80": g["cobertura_intervalo_80"].map(lambda v: "—" if pd.isna(v) else f"{v:.0%}"),
            "parametros": g["parametros"].fillna("—"),
        })[[col_modelo, "mae", "rmse", "r2", "sesgo", "mejora_vs_baseline_pct", "cobertura_intervalo_80",
            "supera_baseline", "es_mejor", "parametros"]].sort_values("mae")
        st.dataframe(tabla, hide_index=True, use_container_width=True, column_config={
            "mae": st.column_config.NumberColumn("MAE", format="%.3f"),
            "rmse": st.column_config.NumberColumn("RMSE", format="%.3f"),
            "r2": st.column_config.NumberColumn("R²", format="%.2f"),
            "sesgo": st.column_config.NumberColumn(T("Bias"), format="%.3f",
                                                   help=T("Mean (forecast − observed); < 0 = underestimates")),
            "mejora_vs_baseline_pct": st.column_config.NumberColumn(T("MAE vs baseline"), format="%.0f%%",
                                                                    help=T("Error reduction vs seasonal naive")),
            "cobertura_intervalo_80": st.column_config.TextColumn(
                T("80% interval coverage"),
                help=T("Share of test values inside the model's own 80% band (ideal ≈ 80%)")),
            "supera_baseline": st.column_config.CheckboxColumn(T("Beats baseline")),
            "es_mejor": st.column_config.CheckboxColumn(T("Best")),
            "parametros": st.column_config.TextColumn(T("Params")),
        })
    except Exception as e:
        st.warning(T("Could not load the forecasts: {e}").format(e=e))

# ---------------------------------------------------------------- Rotations

with tab_rot:
    try:
        nota_guia("guia_rotations")
        res = ranking(zona, tuple(sorted(pesos.items())), cultivo_actual, riego, umbral_ndvi, cultivos_usados, idioma)
        actual = next((r for r in res if r["es_actual"]), None)
        if hay_ediciones:
            st.info(T("Using your edited crop parameters (Data & Method tab)."), icon="✏️")
        st.markdown(T("**{n} candidate rotations** for {zona}, scored 0-100 with your priorities. "
                      "The current rotation is the reference.").format(n=len(res), zona=info["nombre"]))
        st.plotly_chart(figura_desglose(res), use_container_width=True, key="fig_desglose")
        with st.expander(T("Score breakdown as a table")):
            st.dataframe(pd.DataFrame([{T("Rank"): r["rango"], T("Rotation"): nr(r), T("Current"): r["es_actual"],
                                        T("Score"): round(r["puntaje"], 1),
                                        **{T(NOMBRE_CRITERIO[c]): round(r["criterios"][c], 2) for c in NOMBRE_CRITERIO},
                                        T("Worked (years)"): f"{r['backtest']['anios_ok']}/{r['backtest']['anios_total']}"}
                                       for r in res]), hide_index=True, use_container_width=True)

        for r in res:
            with st.container(border=True, key=f"rot_{r['id']}"):
                c1, c2, c3 = st.columns([2.0, 2.2, 2.6])
                with c1:
                    marca = f'<span class="chip-actual">{escape(T("current"))}</span>' if r["es_actual"] else ""
                    st.markdown(f'<div class="rot-titulo"><span class="rot-rango">#{r["rango"]}</span> '
                                f'{escape(nr(r))} {marca}</div>', unsafe_allow_html=True)
                    delta = None if r["es_actual"] or actual is None else \
                        T("{dif:+.0f} vs current").format(dif=r["puntaje"] - actual["puntaje"])
                    st.markdown(CP.puntaje_grande(r["puntaje"], delta), unsafe_allow_html=True)
                    bt = r["backtest"]
                    st.markdown(CP.chip_estado(
                        T("Worked in {ok} of {total} years (2020-2025)").format(ok=bt["anios_ok"], total=bt["anios_total"]),
                        CP.tono_funciono(bt["anios_ok"], bt["anios_total"])), unsafe_allow_html=True)
                    for d in bt["fallidos"]:
                        cultivo = next((nc(e) for e in r["etapas"] if e["cultivo_id"] == d["cultivo_limitante"]),
                                       d["cultivo_limitante"])
                        st.caption(T("✗ {anio} ({tipo} year): {cultivo}, limited by {factor}").format(
                            anio=d["anio"], tipo=T(d["tipo_anio"]), cultivo=cultivo,
                            factor=T(str(d["factor_limitante"]))))
                    if r.get("outlook"):
                        o = r["outlook"]
                        st.caption(T("{anio} outlook (forecast rain): {estado} (min suitability {aptitud:.2f})").format(
                            anio=o["anio"], estado=T("viable") if o["ok"] else T("at risk"), aptitud=o["aptitud_min"]))
                with c2:
                    st.caption(T("Score (0-100) = sum of weighted criteria"))
                    st.markdown(CP.barra_apilada([
                        (T(NOMBRE_CRITERIO[c]), r["contribuciones"][c], PAL["criterio"][c],
                         T("{criterio}: {valor:.2f} · weight {peso:.0%}").format(
                             criterio=T(NOMBRE_CRITERIO[c]), valor=r["criterios"][c], peso=r["pesos"][c]))
                        for c in ("climate", "water", "soil", "income")]), unsafe_allow_html=True)
                with c3:
                    st.caption(T("Crop calendar (21-day periods)"))
                    st.plotly_chart(figura_calendario(r), use_container_width=True, key=f"cal_{r['id']}",
                                    config={"displayModeBar": False})
                exp = r["explicacion"]
                with st.expander(T("Why this rotation? Evidence, benefits, risks and information gaps")):
                    st.markdown(T("**Why suggested.** {texto}").format(texto=exp["why_suggested"]))
                    for titulo, clave in (("Evidence", "evidence"), ("Benefits", "benefits"), ("Risks", "risks"),
                                          ("Information gaps", "information_gaps")):
                        st.markdown(f"**{T(titulo)}**\n" + "\n".join(f"- {x}" for x in exp[clave]))
                    st.caption(exp["disclaimer"])
    except Exception as e:
        st.warning(T("Could not score the rotations: {e}").format(e=e))

# ---------------------------------------------------------------- mapa héroe (arriba, rellenado al final)

def etiqueta_mapa(z: str) -> str:
    """'Zacatepec\\nSugarcane · worked 5/6 yrs'. Zona elegida: sus ajustes; las demás: sus valores por defecto."""
    nombre_z = ZONA_INFO.loc[z, "nombre"]
    cultivo = cultivo_efectivo if z == zona else list(ZONA_INFO.loc[z, "cultivos_actuales"])[0]
    try:
        if z == zona and "res" in globals():
            filas = res
        else:
            filas = ranking(z, tuple(sorted(pesos.items())), None, riego if z == zona else None,
                            umbral_ndvi, cultivos_usados, idioma)
        bt = next(r for r in filas if r["es_actual"])["backtest"]
        dato = T("worked {ok}/{total} yrs").format(ok=bt["anios_ok"], total=bt["anios_total"])
    except Exception:
        dato = T("no result yet")
    return f"{nombre_z}\n{nombre_cultivo(cultivo)} · {dato}"


with slot_mapa:
    try:
        etiquetas = {z: etiqueta_mapa(z) for z in ZONAS_IDS}
        st.pydeck_chart(M.construir_mapa(ZONAS, zona, etiquetas), use_container_width=True, height=620)
        # La atribución de Esri la pinta el propio mapa base (control de MapLibre, abajo a la derecha)
        st.caption(T("Zones are drawn as approximate ~2 km analysis squares around each point, not real field "
                     "boundaries."))
    except Exception as e:
        st.warning(T("Could not draw the map: {e}").format(e=e))

st.divider()
st.caption(T("NASA Space Apps Challenge 2026 · Field Shift: Adapting Farms with NASA Data · "
             "This tool supports, not replaces, farmer judgment."))

if _cambiar_tema:      # ya se dibujaron todos los controles: ahora sí, aplicar el tema nuevo
    st.rerun()
