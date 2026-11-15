"""Interfaz Streamlit. Solo usa funciones de core/ y componentes nativos. Todo el texto visible en inglés.

Ejecutar:   streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:          # streamlit agrega app/ al path, no la raíz del repo
    sys.path.insert(0, str(RAIZ))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import datos
from core import explicacion as X
from core import indicadores as I
from core import periodos as P
from core import pronostico as F
from core import rotaciones as R

APP_TITLE = "CropCompass"   # nombre del proyecto

# Paleta validada (skill dataviz, slots 1-4 en orden fijo; pasa CVD en claro y oscuro)
COLOR_CRITERIO = {"climate": "#2a78d6", "water": "#eb6834", "soil": "#1baf7a", "income": "#eda100"}
NOMBRE_CRITERIO = {"climate": "Climate fit", "water": "Water saving", "soil": "Soil health", "income": "Income"}
COLOR_LLUVIA, COLOR_NDVI, COLOR_GRIS, COLOR_TINTA = "#2a78d6", "#008300", "#9e9d98", "#52514e"
COLOR_ETAPAS = ["#2a78d6", "#eb6834", "#1baf7a"]
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
P_CORTAS = [f"P{p:02d}" for p in range(1, 18)]

st.set_page_config(page_title=APP_TITLE, page_icon="🌱", layout="wide")


# ---------------------------------------------------------------- datos (cacheados)

@st.cache_data(show_spinner="Loading NASA data…")
def cargar_base():
    return (P.cargar_serie_21d(), datos.cargar_clima_diario(), datos.cargar_zonas(),
            datos.cargar_cultivos(), datos.cargar_rotaciones())


@st.cache_data(show_spinner="Loading forecasts (first run trains the models, ~20 s)…")
def cargar_pronosticos():
    return F.cargar_resultados(regenerar_si_falta=True)


@st.cache_data(show_spinner=False)
def diagnostico(zona: str, umbral_ndvi: float) -> dict:
    serie, clima, *_ = cargar_base()
    return I.diagnostico(serie, clima, zona, umbral_ndvi=umbral_ndvi)


@st.cache_data(show_spinner="Scoring rotations…")
def ranking(zona: str, pesos: tuple, cultivo_actual: str | None, riego: bool | None, umbral_ndvi: float,
            cultivos: pd.DataFrame) -> list[dict]:
    serie, _, zonas, _, rotaciones = cargar_base()
    lluvia, anio = R.cargar_lluvia_outlook(zona)
    res = R.rankear(zona, dict(pesos), serie=serie, cultivos=cultivos, rotaciones=rotaciones, zonas=zonas,
                    cultivo_actual=cultivo_actual, riego=riego, umbral_ndvi=umbral_ndvi,
                    lluvia_outlook=lluvia, anio_outlook=anio)
    return X.explicar_ranking(res, diagnostico(zona, umbral_ndvi), zonas.set_index("id").loc[zona].to_dict())


try:
    SERIE, CLIMA, ZONAS, CULTIVOS_BASE, ROTACIONES = cargar_base()
except Exception as e:  # sin datos no hay app: mensaje claro y alto
    st.error(f"Could not load the project data: {e}. Run `python -m core.periodos` to rebuild it.")
    st.stop()

ZONA_INFO = ZONAS.set_index("id")
NOMBRE_CULTIVO = dict(zip(CULTIVOS_BASE["id"], CULTIVOS_BASE["nombre"]))
CULTIVOS_ACTUALES = sorted({c for r in ROTACIONES for c in r.get("actual_para", [])})


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
            fig.add_vrect(x0=a - 1.5, x1=b - 0.5, fillcolor=COLOR_GRIS, opacity=0.18, line_width=0,
                          layer="below", row=fila, col=1)
        if texto and i == 0:
            fig.add_annotation(x=(a + b) / 2 - 1, y=0.98, xref="x", yref="y domain", text="bare soil",
                               showarrow=False, font=dict(size=11, color=COLOR_TINTA), yanchor="top")


def figura_diagnostico(diag: dict) -> go.Figure:
    clim = diag["climatologia"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Rainfall per 21-day period (mm, 2020-2025 mean ± 1 SD)",
                                        "NDVI, vegetation greenness (2020-2025 mean ± 1 SD)"))
    fig.add_bar(x=P_CORTAS, y=clim["precip_media"], marker_color=COLOR_LLUVIA, name="Rainfall",
                error_y=dict(type="data", array=clim["precip_std"], color=COLOR_GRIS, thickness=1),
                customdata=clim["etiqueta"], hovertemplate="%{customdata}<br>%{y:.0f} mm<extra></extra>",
                row=1, col=1)
    sup, inf = clim["ndvi_media"] + clim["ndvi_std"], clim["ndvi_media"] - clim["ndvi_std"]
    fig.add_scatter(x=P_CORTAS, y=sup, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False,
                    row=2, col=1)
    fig.add_scatter(x=P_CORTAS, y=inf, mode="lines", line=dict(width=0), fill="tonexty",
                    fillcolor="rgba(0,131,0,0.15)", hoverinfo="skip", showlegend=False, row=2, col=1)
    fig.add_scatter(x=P_CORTAS, y=clim["ndvi_media"], mode="lines+markers", name="NDVI",
                    line=dict(color=COLOR_NDVI, width=2), marker=dict(size=8),
                    customdata=clim["etiqueta"], hovertemplate="%{customdata}<br>NDVI %{y:.2f}<extra></extra>",
                    row=2, col=1)
    fig.add_hline(y=diag["umbrales"]["ndvi_desnudo"], line=dict(color=COLOR_TINTA, width=1, dash="dot"),
                  annotation_text=f"bare-soil threshold {diag['umbrales']['ndvi_desnudo']:.2f}",
                  annotation_position="bottom", row=2, col=1)
    sombrear_desnudos(fig, diag["suelo_desnudo"], filas=(1, 2))
    fig.update_yaxes(title_text="mm", row=1, col=1)
    fig.update_yaxes(title_text="NDVI", row=2, col=1)
    fig.update_layout(height=560, showlegend=False, margin=dict(t=60, b=20, l=10, r=10), bargap=0.25)
    return fig


def figura_ndvi_anual(serie_zona: pd.DataFrame) -> go.Figure:
    tabla = serie_zona.pivot(index="anio", columns="periodo", values="ndvi")
    fig = go.Figure(go.Heatmap(z=tabla.to_numpy(), x=P_CORTAS, y=[str(a) for a in tabla.index],
                               colorscale="Greens", zmin=0.15, zmax=0.65, xgap=2, ygap=2,
                               colorbar=dict(title="NDVI"),
                               hovertemplate="%{y} %{x}<br>NDVI %{z:.2f}<extra></extra>"))
    fig.update_layout(height=260, margin=dict(t=10, b=10, l=10, r=10), yaxis=dict(autorange="reversed"))
    return fig


def figura_pronostico(zona: str, var: str, prono: pd.DataFrame, prueba: pd.DataFrame) -> go.Figure:
    hist = SERIE[SERIE["zona"] == zona].sort_values("fecha_inicio")
    fig = go.Figure()
    fig.add_scatter(x=hist["fecha_inicio"], y=hist[var], mode="lines", name="Observed (NASA data)",
                    line=dict(color=COLOR_TINTA, width=2))
    p_mejor = prueba[(prueba["zona"] == zona) & (prueba["variable"] == var)]
    g = prono[(prono["zona"] == zona) & (prono["variable"] == var)]
    mejor = g[g["es_mejor"]]
    nombre = NOMBRE_MODELO.get(mejor["modelo"].iloc[0], mejor["modelo"].iloc[0])
    pt = p_mejor[p_mejor["modelo"] == mejor["modelo"].iloc[0]]
    fig.add_scatter(x=pt["fecha_inicio"], y=pt["yhat"], mode="lines", name=f"{nombre}: test-period forecast",
                    line=dict(color=COLOR_LLUVIA, width=2, dash="dash"))
    if mejor["yhat_lower"].notna().any():
        fig.add_scatter(x=mejor["fecha_inicio"], y=mejor["yhat_upper"], mode="lines", line=dict(width=0),
                        hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=mejor["fecha_inicio"], y=mejor["yhat_lower"], mode="lines", line=dict(width=0),
                        fill="tonexty", fillcolor="rgba(42,120,214,0.18)", name="80% interval",
                        hoverinfo="skip")
    fig.add_scatter(x=mejor["fecha_inicio"], y=mejor["yhat"], mode="lines+markers",
                    name=f"{nombre}: {int(mejor['anio'].iloc[0])} forecast",
                    line=dict(color=COLOR_LLUVIA, width=2), marker=dict(size=8), customdata=mejor["etiqueta"],
                    hovertemplate="%{customdata}<br>%{y:.2f}<extra></extra>")
    base = g[g["modelo"] == F.BASELINE]
    if not mejor["modelo"].eq(F.BASELINE).all():
        fig.add_scatter(x=base["fecha_inicio"], y=base["yhat"], mode="lines", name="Seasonal naive baseline",
                        line=dict(color="#eb6834", width=2, dash="dot"))
    if len(pt):
        fig.add_vline(x=pt["fecha_inicio"].min(), line=dict(color=COLOR_GRIS, width=1, dash="dot"))
        fig.add_annotation(x=pt["fecha_inicio"].min(), y=1, yref="paper", text="test period →",
                           showarrow=False, xanchor="left", font=dict(size=11, color=COLOR_TINTA))
    fig.update_layout(height=430, hovermode="x unified", margin=dict(t=30, b=10, l=10, r=10),
                      yaxis_title=VARIABLES[var], legend=dict(orientation="h", y=-0.15, traceorder="normal"))
    return fig


def figura_desglose(res: list[dict]) -> go.Figure:
    nombres = [f"#{r['rango']} {r['nombre']}" + (" (current)" if r["es_actual"] else "") for r in res][::-1]
    fig = go.Figure()
    for c in ("climate", "water", "soil", "income"):
        fig.add_bar(y=nombres, x=[r["contribuciones"][c] for r in res][::-1], orientation="h",
                    name=NOMBRE_CRITERIO[c], marker=dict(color=COLOR_CRITERIO[c], line=dict(color="white", width=2)),
                    hovertemplate=f"{NOMBRE_CRITERIO[c]}: %{{x:.1f}} pts<extra></extra>")
    fig.update_layout(barmode="stack", height=90 + 42 * len(res), margin=dict(t=10, b=10, l=10, r=10),
                      xaxis=dict(title="Score (0-100) = sum of weighted criteria", range=[0, 100]),
                      legend=dict(orientation="h", y=1.08, traceorder="normal"))
    return fig


def figura_calendario(r: dict) -> go.Figure:
    fig = go.Figure()
    filas = []
    for i, e in enumerate(r["etapas"]):
        filas.append(e["cultivo"])
        fig.add_scatter(x=[P_CORTAS[p - 1] for p in e["periodos"]], y=[e["cultivo"]] * len(e["periodos"]),
                        mode="markers", marker=dict(symbol="square", size=16, color=COLOR_ETAPAS[i % 3]),
                        name=e["cultivo"], hovertemplate=f"{e['cultivo']}<br>%{{x}}<extra></extra>")
    if r["desnudos_zona"]:
        filas.append("Bare soil today (NDVI)")
        fig.add_scatter(x=[P_CORTAS[p - 1] for p in r["desnudos_zona"]], y=[filas[-1]] * len(r["desnudos_zona"]),
                        mode="markers", marker=dict(symbol="square", size=16, color=COLOR_GRIS),
                        name="Bare soil", hovertemplate="Bare soil today<br>%{x}<extra></extra>")
    fig.update_layout(height=50 + 32 * len(filas), showlegend=False, margin=dict(t=5, b=5, l=5, r=5),
                      xaxis=dict(categoryorder="array", categoryarray=P_CORTAS, range=[-0.5, 16.5],
                                 tickmode="array", tickvals=P_CORTAS[::4], tickangle=0, tickfont=dict(size=10)),
                      yaxis=dict(categoryorder="array", categoryarray=filas[::-1]))
    return fig


# ---------------------------------------------------------------- barra lateral

with st.sidebar:
    st.header("Your farm")
    with st.form("entrada"):
        zona = st.selectbox("Zone (Morelos, Mexico)", ZONAS["id"].tolist(),
                            format_func=lambda z: ZONA_INFO.loc[z, "nombre"])
        opcion_cultivo = st.selectbox(
            "Current crop", ["__zona__"] + CULTIVOS_ACTUALES,
            format_func=lambda c: "Typical crop for this zone" if c == "__zona__" else NOMBRE_CULTIVO.get(c, c))
        opcion_riego = st.radio("Irrigation", ["Zone default", "Irrigated", "Rainfed"], horizontal=True,
                                help="With irrigation, rainfall does not limit crop suitability.")
        st.markdown("**Your priorities** (relative weights)")
        w_agua = st.slider("Water saving", 0, 10, 5)
        w_suelo = st.slider("Soil health", 0, 10, 5)
        w_ingreso = st.slider("Income", 0, 10, 5)
        w_clima = st.slider("Climate fit", 0, 10, 5)
        with st.expander("Advanced"):
            umbral_ndvi = st.slider("Bare-soil NDVI threshold", 0.15, 0.45, I.UMBRAL_NDVI_DESNUDO, 0.01,
                                    help="A 21-day period counts as bare soil when its mean NDVI is below this.")
        st.form_submit_button("Analyze", type="primary", use_container_width=True)
    st.caption("Crop parameters are hypotheses pending validation. "
               "This tool supports, not replaces, farmer judgment.")

cultivo_actual = None if opcion_cultivo == "__zona__" else opcion_cultivo
riego = {"Zone default": None, "Irrigated": True, "Rainfed": False}[opcion_riego]
pesos = {"water": w_agua, "soil": w_suelo, "income": w_ingreso, "climate": w_clima}
info = ZONA_INFO.loc[zona]
riego_efectivo = bool(info["riego"]) if riego is None else riego
cultivo_efectivo = cultivo_actual or list(info["cultivos_actuales"])[0]

# ---------------------------------------------------------------- cabecera

st.title(f"🌱 {APP_TITLE}")
st.markdown("Decision support for crop rotations in **sugarcane areas of Morelos, Mexico**, built on NASA "
            "satellite data summarized in **21-day periods** (17 per year, 2020-2025).")
pesos_n = R.normalizar_pesos(pesos)
st.caption(f"**{info['nombre']}** · current crop: **{NOMBRE_CULTIVO.get(cultivo_efectivo, cultivo_efectivo)}** · "
           f"{'irrigated' if riego_efectivo else 'rainfed'} · priorities: "
           + ", ".join(f"{NOMBRE_CRITERIO[c].lower()} {pesos_n[c]:.0%}" for c in ("water", "soil", "income", "climate")))

tab_diag, tab_prono, tab_rot, tab_metodo = st.tabs(["Diagnosis", "Forecast", "Rotations", "Data & Method"])

# ---------------------------------------------------------------- Data & Method (primero: el editor alimenta el ranking)

with tab_metodo:
    cultivos_usados, hay_ediciones = CULTIVOS_BASE, False
    try:
        st.subheader("Crop parameters: hypotheses")
        st.info("These values are **hypotheses pending validation with local agronomists** (approximate ranges "
                "inspired by FAO EcoCrop). Edit any cell and the ranking in **Rotations** updates.", icon="🧪")
        columnas = ["nombre", "tipo", "ciclo_meses", "siembra_mes", "temp_abs_min", "temp_opt_min", "temp_opt_max",
                    "temp_abs_max", "lluvia_abs_min", "lluvia_opt_min", "lluvia_opt_max", "lluvia_abs_max",
                    "tolera_helada", "agua_relativa", "fija_nitrogeno", "cubre_suelo", "mercado_local", "notas"]
        base_editor = CULTIVOS_BASE.set_index("id")[columnas]
        num = lambda label, lo, hi, paso, fmt="%.0f", ayuda=None: st.column_config.NumberColumn(
            label, min_value=lo, max_value=hi, step=paso, format=fmt, help=ayuda)
        editado = st.data_editor(
            base_editor, key="editor_cultivos", num_rows="fixed", use_container_width=True,
            disabled=["nombre", "tipo", "notas"],
            column_config={
                "_index": st.column_config.TextColumn("id"),
                "nombre": "Crop", "tipo": "Type", "notas": "Notes",
                "ciclo_meses": num("Cycle (months)", 1, 24, 1),
                "siembra_mes": num("Sowing month", 1, 12, 1),
                "temp_abs_min": num("Temp abs min °C", -10, 50, 1), "temp_opt_min": num("Temp opt min °C", -10, 50, 1),
                "temp_opt_max": num("Temp opt max °C", -10, 50, 1), "temp_abs_max": num("Temp abs max °C", -10, 50, 1),
                "lluvia_abs_min": num("Rain abs min mm", 0, 6000, 50), "lluvia_opt_min": num("Rain opt min mm", 0, 6000, 50),
                "lluvia_opt_max": num("Rain opt max mm", 0, 6000, 50), "lluvia_abs_max": num("Rain abs max mm", 0, 6000, 50),
                "tolera_helada": st.column_config.CheckboxColumn("Frost tolerant"),
                "agua_relativa": num("Water demand 0-1", 0.0, 1.0, 0.05, "%.2f"),
                "fija_nitrogeno": st.column_config.CheckboxColumn("Fixes nitrogen"),
                "cubre_suelo": num("Soil cover 0-1", 0.0, 1.0, 0.05, "%.2f"),
                "mercado_local": num("Local market 0-1", 0.0, 1.0, 0.05, "%.2f"),
            })
        if st.button("Reset crop parameters to defaults"):
            st.session_state.pop("editor_cultivos", None)
            st.rerun()
        candidato = editado.reset_index().rename(columns={"index": "id"})
        candidato["nombre_es"] = CULTIVOS_BASE["nombre_es"].to_numpy()
        problemas = datos.validar_config(ZONAS, candidato, ROTACIONES)
        hay_ediciones = bool(st.session_state.get("editor_cultivos", {}).get("edited_rows"))
        if problemas:
            st.warning("Edited values are inconsistent, so the default parameters are used: " + "; ".join(problemas))
            hay_ediciones = False
        else:
            cultivos_usados = candidato

        st.subheader("Data sources")
        st.markdown(
            "- **Rainfall**: NASA GPM IMERG (`IMERG_PRECTOT`), daily, via the "
            "[NASA POWER API](https://power.larc.nasa.gov/) · [GPM IMERG](https://gpm.nasa.gov/data/imerg)\n"
            "- **Temperature**: NASA POWER daily max/min (MERRA-2 reanalysis, ~0.5° cells)\n"
            "- **Vegetation**: [MODIS MOD13Q1](https://lpdaac.usgs.gov/products/mod13q1v061/) NDVI, 16-day "
            "composites at 250 m, with pixel reliability, from the "
            "[ORNL DAAC MODIS web service](https://modis.ornl.gov/data/modis_webservice.html) (9×9 pixel window "
            "around each zone point)\n"
            "- **Crop ranges**: inspired by [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop); "
            "**forecasting**: [Prophet](https://facebook.github.io/prophet/) and scikit-learn")
        st.subheader("Method")
        st.markdown(
            "1. **21-day periods.** Each year is split into 17 fixed periods anchored to January 1 (period *k* starts "
            "on day 1 + 21·(k−1); P17 absorbs the remaining 29-30 days), so P08 of 2021 is comparable with P08 of 2024.\n"
            "2. **Integrated table.** Daily rain and temperature are summed / averaged per period; NDVI composites "
            "(every 16 days) are cleaned of cloudy pixels, linearly interpolated to daily values and averaged per period.\n"
            "3. **Diagnosis.** 2020-2025 averages per period: bare soil (NDVI below the threshold), rainy season "
            "(> 35 mm per 21 days), frost (Tmin ≤ 2 °C) and heat (≥ 3 days with Tmax ≥ 35 °C) risk, dry spells, and "
            "dry / normal / wet years by terciles of annual rain.\n"
            "4. **Forecast.** The last 20 % of periods are held out (temporal split, never random). Every model forecasts "
            "that block from the end of training and is compared by MAE with a seasonal naive baseline (same period last "
            "year). The best model is refit on all data to forecast the next 17 periods.\n"
            "5. **Crop suitability.** EcoCrop-style trapezoids for temperature and cycle rainfall plus a frost penalty; "
            "the weakest factor is the suitability (0-1). Irrigation removes the rainfall limit.\n"
            "6. **Rotation score.** Weighted sum of climate fit, water saving (time-weighted water demand), soil health "
            "(nitrogen fixation, year-round cover, crop diversity, bare periods covered) and income (local market). "
            "**Backtesting:** a year *worked* if every crop in the rotation reached suitability ≥ 0.6 with that year's weather.")
        st.subheader("Candidate rotations")
        st.dataframe(pd.DataFrame([{
            "Rotation": r["nombre"],
            "Crops (sowing month)": " → ".join(f"{NOMBRE_CULTIVO.get(e['cultivo'], e['cultivo'])} (m{e.get('siembra_mes', '?')})"
                                               for e in r["etapas"]),
            "Current practice for": ", ".join(NOMBRE_CULTIVO.get(c, c) for c in r.get("actual_para", [])) or "-",
        } for r in ROTACIONES]), hide_index=True, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render the data & method section: {e}")

# ---------------------------------------------------------------- Diagnosis

with tab_diag:
    try:
        diag = diagnostico(zona, umbral_ndvi)
        et = diag["etiquetas"]
        t = diag["temporal"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Rainy season", f"{et[t['inicio']][:3]} → {et[t['fin']][:3]}" if t else "No data",
                  help="First and last 21-day period with > 35 mm on average")
        c2.metric("Bare-soil periods", len(diag["suelo_desnudo"]), help="Periods with mean NDVI below the threshold")
        c3.metric("Heat-risk periods", len(diag["calor"]), help="≥ 3 days with Tmax ≥ 35 °C on average")
        c4.metric("Frost-risk periods", len(diag["helada"]), help="Any day with Tmin ≤ 2 °C on average")
        seco = min(diag["lluvia_anual"], key=diag["lluvia_anual"].get)
        c5.metric(f"Driest year ({diag['lluvia_anual'][seco]:.0f} mm)", str(seco),
                  help="Lowest annual rainfall (GPM IMERG) in 2020-2025")

        izq, der = st.columns([3, 1])
        with izq:
            st.plotly_chart(figura_diagnostico(diag), use_container_width=True, key="fig_diag")
        with der:
            puntos = ZONAS.assign(size=lambda d: d["id"].eq(zona).map({True: 2500, False: 1200}),
                                  color=lambda d: d["id"].eq(zona).map({True: COLOR_LLUVIA, False: COLOR_GRIS}))
            st.map(puntos, latitude="lat", longitude="lon", size="size", color="color", zoom=8)
            if isinstance(info.get("aviso"), str):
                st.warning(info["aviso"], icon="⚠️")

        sz = SERIE[SERIE["zona"] == zona]
        anios = list(diag["lluvia_anual"])
        anual = pd.DataFrame({
            "Year": [str(a) for a in anios],
            "Rain (mm)": [round(diag["lluvia_anual"][a]) for a in anios],
            "Type": [diag["tipo_anio"].get(a, "unknown") for a in anios],
            "Dry spell (days)": [diag["racha_seca_temporal"].get(a) for a in anios],
            "Heat days": [int(sz.loc[sz["anio"] == a, "dias_calor"].sum()) for a in anios],
        })
        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**Year by year**")
            st.dataframe(anual, hide_index=True, use_container_width=True, column_config={
                "Type": st.column_config.TextColumn("Type", help="dry / normal / wet by terciles of annual rain"),
                "Dry spell (days)": st.column_config.NumberColumn(
                    "Dry spell (days)", help="Longest run of days with < 1 mm inside the rainy season"),
                "Heat days": st.column_config.NumberColumn("Heat days", help="Days with Tmax ≥ 35 °C"),
            })
        with a2:
            st.markdown("**Free windows for a cover crop**")
            ventanas = diag["ventanas_libres"]
            if ventanas:
                st.dataframe(pd.DataFrame([{"Period": v["etiqueta"], "NDVI": v["ndvi"],
                                            "Rain (mm)": v["precip_mm"],
                                            "Needs": "irrigation" if v["requiere_riego"] else "rain is enough"}
                                           for v in ventanas]), hide_index=True, use_container_width=True)
            else:
                st.caption("No bare-soil periods detected, so no free windows.")
        st.markdown("**NDVI per year and 21-day period** (darker = greener)")
        st.plotly_chart(figura_ndvi_anual(sz), use_container_width=True, key="fig_ndvi_anual")
        if diag["periodos_sin_ndvi"]:
            st.warning(f"No data: {diag['periodos_sin_ndvi']} periods have no NDVI.")
    except Exception as e:
        st.warning(f"Could not build the diagnosis for this zone: {e}")

# ---------------------------------------------------------------- Forecast

with tab_prono:
    try:
        met, prono, prueba = cargar_pronosticos()
        var = st.radio("Variable", list(VARIABLES), format_func=VARIABLES.get, horizontal=True)
        g = met[(met["zona"] == zona) & (met["variable"] == var)]
        mejor = g[g["es_mejor"]].iloc[0]
        anio = int(prono["anio"].iloc[0])
        tipo_int = prono[(prono["zona"] == zona) & (prono["variable"] == var) & prono["es_mejor"]]["tipo_intervalo"].iloc[0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Best model (test MAE)", NOMBRE_MODELO.get(mejor["modelo"], mejor["modelo"]))
        m2.metric("Test MAE vs baseline", f"{mejor['mae']:.3g}", f"{-mejor['mejora_vs_baseline_pct']:.0f}% error",
                  delta_color="inverse", help="Mean absolute error on the held-out last 20 % of periods")
        m3.metric("Forecast horizon", f"17 periods ({anio})")
        st.plotly_chart(figura_pronostico(zona, var, prono, prueba), use_container_width=True, key="fig_prono")
        st.caption(f"Interval: {NOMBRE_INTERVALO.get(tipo_int, tipo_int)}. Train = first {int(mejor['n_train'])} periods, "
                   f"test = last {int(mejor['n_test'])} (temporal split). Future rain/temperature used as model inputs = "
                   "2020-2025 average for that period. R² for rainfall is unstable in the dry season: read it with MAE.")
        tabla = g.assign(
            Model=g["modelo"].map(lambda m: NOMBRE_MODELO.get(m, m)),
            cobertura_intervalo_80=g["cobertura_intervalo_80"].map(lambda v: "—" if pd.isna(v) else f"{v:.0%}"),
            parametros=g["parametros"].fillna("—"),
        )[["Model", "mae", "rmse", "r2", "sesgo", "mejora_vs_baseline_pct", "cobertura_intervalo_80",
           "supera_baseline", "es_mejor", "parametros"]].sort_values("mae")
        st.dataframe(tabla, hide_index=True, use_container_width=True, column_config={
            "mae": st.column_config.NumberColumn("MAE", format="%.3f"),
            "rmse": st.column_config.NumberColumn("RMSE", format="%.3f"),
            "r2": st.column_config.NumberColumn("R²", format="%.2f"),
            "sesgo": st.column_config.NumberColumn("Bias", format="%.3f", help="Mean (forecast − observed); < 0 = underestimates"),
            "mejora_vs_baseline_pct": st.column_config.NumberColumn("MAE vs baseline", format="%.0f%%",
                                                                    help="Error reduction vs seasonal naive"),
            "cobertura_intervalo_80": st.column_config.TextColumn(
                "80% interval coverage", help="Share of test values inside the model's own 80% band (ideal ≈ 80%)"),
            "supera_baseline": st.column_config.CheckboxColumn("Beats baseline"),
            "es_mejor": st.column_config.CheckboxColumn("Best"),
            "parametros": st.column_config.TextColumn("Params"),
        })
    except Exception as e:
        st.warning(f"Could not load the forecasts: {e}")

# ---------------------------------------------------------------- Rotations

with tab_rot:
    try:
        res = ranking(zona, tuple(sorted(pesos.items())), cultivo_actual, riego, umbral_ndvi, cultivos_usados)
        actual = next((r for r in res if r["es_actual"]), None)
        if hay_ediciones:
            st.info("Using your edited crop parameters (Data & Method tab).", icon="✏️")
        st.markdown(f"**{len(res)} candidate rotations** for {info['nombre']}, scored 0-100 with your priorities. "
                    "The current rotation is the reference.")
        st.plotly_chart(figura_desglose(res), use_container_width=True, key="fig_desglose")
        with st.expander("Score breakdown as a table"):
            st.dataframe(pd.DataFrame([{"Rank": r["rango"], "Rotation": r["nombre"], "Current": r["es_actual"],
                                        "Score": round(r["puntaje"], 1),
                                        **{NOMBRE_CRITERIO[c]: round(r["criterios"][c], 2) for c in NOMBRE_CRITERIO},
                                        "Worked (years)": f"{r['backtest']['anios_ok']}/{r['backtest']['anios_total']}"}
                                       for r in res]), hide_index=True, use_container_width=True)

        for r in res:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2.1, 1.9, 2.6])
                with c1:
                    etiqueta = " :blue-background[current]" if r["es_actual"] else ""
                    st.markdown(f"#### #{r['rango']} {r['nombre']}{etiqueta}")
                    delta = None if r["es_actual"] or actual is None else f"{r['puntaje'] - actual['puntaje']:+.0f} vs current"
                    st.metric("Score", f"{r['puntaje']:.0f}/100", delta)
                    bt = r["backtest"]
                    st.markdown(f"**Worked in {bt['anios_ok']} of {bt['anios_total']} years** (2020-2025)")
                    for d in bt["fallidos"]:
                        crop = next((e["cultivo"] for e in r["etapas"] if e["cultivo_id"] == d["cultivo_limitante"]),
                                    d["cultivo_limitante"])
                        st.caption(f"✗ {d['anio']} ({d['tipo_anio']} year): {crop}, limited by {d['factor_limitante']}")
                    if r.get("outlook"):
                        o = r["outlook"]
                        st.caption(f"{o['anio']} outlook (forecast rain): {'viable' if o['ok'] else 'at risk'} "
                                   f"(min suitability {o['aptitud_min']:.2f})")
                with c2:
                    for c in ("climate", "water", "soil", "income"):
                        v = r["criterios"][c]
                        st.progress(min(max(v, 0.0), 1.0),
                                    text=f"{NOMBRE_CRITERIO[c]}: {v:.2f} · weight {r['pesos'][c]:.0%}")
                with c3:
                    st.caption("Crop calendar (21-day periods)")
                    st.plotly_chart(figura_calendario(r), use_container_width=True, key=f"cal_{r['id']}",
                                    config={"displayModeBar": False})
                exp = r["explicacion"]
                with st.expander("Why this rotation? Evidence, benefits, risks and information gaps"):
                    st.markdown(f"**Why suggested.** {exp['why_suggested']}")
                    for titulo, clave in (("Evidence", "evidence"), ("Benefits", "benefits"), ("Risks", "risks"),
                                          ("Information gaps", "information_gaps")):
                        st.markdown(f"**{titulo}**\n" + "\n".join(f"- {x}" for x in exp[clave]))
                    st.caption(exp["disclaimer"])
    except Exception as e:
        st.warning(f"Could not score the rotations: {e}")

st.divider()
st.caption("NASA Space Apps Challenge 2026 · Field Shift: Adapting Farms with NASA Data · "
           "This tool supports, not replaces, farmer judgment.")
