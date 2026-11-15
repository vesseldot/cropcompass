"""Traducción inglés -> español de la interfaz y de las explicaciones (sin servicios externos).

El inglés es el idioma base (requisito del concurso): las claves del diccionario ES son los textos en
inglés tal como aparecen en el código. tr(texto, "es") devuelve la traducción, o el mismo texto si no
existe (nunca falla). Las plantillas conservan sus {marcadores} para .format().
tests/test_i18n.py revisa que todo texto envuelto en T("...") tenga traducción.
"""
from __future__ import annotations

import re

IDIOMAS = {"English": "en", "Español": "es"}

MESES_ES = {"Jan": "ene", "Feb": "feb", "Mar": "mar", "Apr": "abr", "May": "may", "Jun": "jun",
            "Jul": "jul", "Aug": "ago", "Sep": "sep", "Oct": "oct", "Nov": "nov", "Dec": "dic"}
_RE_FECHA = re.compile(r"\b(" + "|".join(MESES_ES) + r") (\d{1,2})\b")


def tr(texto: str, idioma: str = "en") -> str:
    return ES.get(texto, texto) if idioma == "es" else texto


def fechas(texto: str, idioma: str = "en") -> str:
    """'P08 (May 28 – Jun 17)' -> 'P08 (28 may – 17 jun)' en español."""
    if idioma != "es" or not isinstance(texto, str):
        return texto
    return _RE_FECHA.sub(lambda m: f"{m.group(2)} {MESES_ES[m.group(1)]}", texto)


def bloque(nombre: str, idioma: str = "en") -> str:
    """Textos largos (markdown) por idioma: fuentes, método y guía."""
    return BLOQUES[nombre].get(idioma, BLOQUES[nombre]["en"])


ES = {
    # ------------------------------------------------------------ vocabulario
    "dry": "seco", "normal": "normal", "wet": "húmedo", "unknown": "desconocido",
    "temperature": "temperatura", "rainfall": "lluvia", "frost": "helada", "none": "ninguno",
    "climate fit": "ajuste al clima", "water saving": "ahorro de agua", "soil health": "salud del suelo",
    "income": "ingreso",
    "Climate fit": "Ajuste al clima", "Water saving": "Ahorro de agua", "Soil health": "Salud del suelo",
    "Income": "Ingreso",
    "higher": "más", "lower": "menos", "viable": "viable", "at risk": "en riesgo",
    "irrigated": "con riego", "rainfed": "de temporal", " and ": " y ",
    "lower water use": "menor uso de agua", "higher water use": "mayor uso de agua",
    "better soil health": "mejor salud del suelo", "weaker soil health": "menor salud del suelo",
    "higher income potential": "mayor potencial de ingreso", "lower income potential": "menor potencial de ingreso",
    "better climate fit": "mejor ajuste al clima", "weaker climate fit": "menor ajuste al clima",
    "cash": "comercial", "grain": "grano", "legume": "leguminosa", "cover": "cobertura",

    # ------------------------------------------------------------ explicaciones (core/explicacion.py)
    "This tool supports, not replaces, farmer judgment.":
        "Esta herramienta apoya, no sustituye, el criterio del agricultor.",
    "Crop parameters (temperature and rainfall ranges, water demand, local market) are "
    "hypotheses pending validation with local agronomists.":
        "Los parámetros de cultivo (rangos de temperatura y lluvia, demanda de agua, mercado local) son "
        "hipótesis pendientes de validar con agrónomos locales.",
    "Data: rainfall from NASA GPM IMERG and temperature from NASA POWER (MERRA-2), both via the "
    "NASA POWER API; vegetation from MODIS MOD13Q1 NDVI (250 m, ORNL DAAC); 2020-2025, "
    "summarized in 17 fixed 21-day periods per year.":
        "Datos: lluvia de NASA GPM IMERG y temperatura de NASA POWER (MERRA-2), ambas vía la API de "
        "NASA POWER; vegetación de MODIS MOD13Q1 NDVI (250 m, ORNL DAAC); 2020-2025, "
        "resumidos en 17 periodos fijos de 21 días por año.",
    "Ranked #{rango} of {n} with {puntaje:.0f}/100 under your priorities.":
        "Lugar #{rango} de {n} con {puntaje:.0f}/100 según tus prioridades.",
    "It stands out on {criterio}: {valor:.2f} vs {promedio:.2f} on average among the options (0-1 scale).":
        "Destaca en {criterio}: {valor:.2f} frente a {promedio:.2f} en promedio entre las opciones (escala 0-1).",
    "This is your current rotation, shown as the reference point.":
        "Esta es tu rotación actual; se muestra como punto de referencia.",
    "Compared with your current rotation ({nombre}, {puntaje:.0f}/100) it scores {dif:.0f} points {sentido}: {cambios}.":
        "Frente a tu rotación actual ({nombre}, {puntaje:.0f}/100) obtiene {dif:.0f} puntos {sentido}: {cambios}.",
    "Compared with your current rotation ({nombre}, {puntaje:.0f}/100) it scores {dif:.0f} points {sentido}, "
    "with similar criteria.":
        "Frente a tu rotación actual ({nombre}, {puntaje:.0f}/100) obtiene {dif:.0f} puntos {sentido}, "
        "con criterios parecidos.",
    "rainfall {valor:.2f}": "lluvia {valor:.2f}",
    "{cultivo}: sown in {inicio}, {n} periods (until {fin}). Climate suitability {aptitud:.2f} "
    "(temperature {temp:.2f}, {lluvia}, frost {helada:.2f}); "
    "2020-2025 average {grados:.1f} °C and {mm:.0f} mm of rain in the cycle.":
        "{cultivo}: siembra en {inicio}, {n} periodos (hasta {fin}). Aptitud climática {aptitud:.2f} "
        "(temperatura {temp:.2f}, {lluvia}, helada {helada:.2f}); "
        "promedio 2020-2025 de {grados:.1f} °C y {mm:.0f} mm de lluvia en el ciclo.",
    "Worked in {ok} of {total} years (2020-2025): every crop reached "
    "climate suitability ≥ {umbral:.1f} in that year's real weather.":
        "Funcionó en {ok} de {total} años (2020-2025): todos los cultivos alcanzaron "
        "aptitud climática ≥ {umbral:.1f} con el clima real de ese año.",
    "Failed in {anio} ({tipo} year): {cultivo} limited by {factor} (suitability {aptitud:.2f}).":
        "Falló en {anio} (año {tipo}): {cultivo} limitado por {factor} (aptitud {aptitud:.2f}).",
    "Covers {n} of the {total} bare-soil periods detected with MODIS NDVI in this zone ({periodos}): {cubiertos}.":
        "Cubre {n} de los {total} periodos de suelo desnudo detectados con NDVI de MODIS en esta zona "
        "({periodos}): {cubiertos}.",
    "Covers {n} of the {total} bare-soil periods detected with MODIS NDVI in this zone ({periodos}).":
        "Cubre {n} de los {total} periodos de suelo desnudo detectados con NDVI de MODIS en esta zona ({periodos}).",
    "MODIS NDVI shows no bare-soil periods in this zone (average NDVI ≥ 0.30 all year).":
        "El NDVI de MODIS no muestra periodos de suelo desnudo en esta zona (NDVI promedio ≥ 0.30 todo el año).",
    "{anio} outlook with forecast rainfall (temperatures = 2020-2025 average): minimum "
    "suitability {aptitud:.2f}, {estado}.":
        "Perspectiva {anio} con la lluvia pronosticada (temperaturas = promedio 2020-2025): aptitud "
        "mínima {aptitud:.2f}, {estado}.",
    "Includes a nitrogen-fixing legume ({cultivos}), which can lower fertilizer needs for the next crop.":
        "Incluye una leguminosa que fija nitrógeno ({cultivos}), lo que puede reducir el fertilizante "
        "que necesita el siguiente cultivo.",
    "Includes nitrogen-fixing legumes ({cultivos}), which can lower fertilizer needs for the next crop.":
        "Incluye leguminosas que fijan nitrógeno ({cultivos}), lo que puede reducir el fertilizante "
        "que necesita el siguiente cultivo.",
    "Keeps living cover in {n} period that is usually bare, reducing erosion and weed pressure.":
        "Mantiene cobertura viva en {n} periodo que suele estar desnudo, lo que reduce la erosión y las malezas.",
    "Keeps living cover in {n} periods that are usually bare, reducing erosion and weed pressure.":
        "Mantiene cobertura viva en {n} periodos que suelen estar desnudos, lo que reduce la erosión y las malezas.",
    "Alternates different crops, which helps break pest and disease cycles.":
        "Alterna cultivos distintos, lo que ayuda a romper los ciclos de plagas y enfermedades.",
    "Lower water demand than your current rotation (uses {esta:.0%} of the "
    "year's maximum demand vs {actual:.0%}).":
        "Menor demanda de agua que tu rotación actual (usa {esta:.0%} de la demanda máxima del año "
        "frente a {actual:.0%}).",
    "Built on crops with a strong local market.": "Se basa en cultivos con buen mercado local.",
    "Climatically viable in all {n} years analyzed, including dry and wet years.":
        "Viable por clima en los {n} años analizados, incluidos años secos y húmedos.",
    "No clear advantage over the alternatives under the current weights.":
        "Sin ventaja clara sobre las alternativas con los pesos actuales.",
    "Did not work in {n} of {total} years; most often limited by {factor}.":
        "No funcionó en {n} de {total} años; el límite más frecuente fue {factor}.",
    "{cultivo} is close to its {factor} limit (suitability {aptitud:.2f}).":
        "{cultivo} está cerca de su límite de {factor} (aptitud {aptitud:.2f}).",
    "{cultivo} depends on irrigation: its cycle gets {mm:.0f} mm of rain on "
    "average vs an optimum of {lo:.0f}-{hi:.0f} mm.":
        "{cultivo} depende del riego: su ciclo recibe {mm:.0f} mm de lluvia en promedio frente a un "
        "óptimo de {lo:.0f}-{hi:.0f} mm.",
    "{cultivo} grows through periods with frequent heat ≥ 35 °C ({periodos}).":
        "{cultivo} crece en periodos con calor frecuente ≥ 35 °C ({periodos}).",
    "Rainfed crops in the rainy season faced dry spells of up to {dias} days ({anio}).":
        "Los cultivos de temporal enfrentaron rachas secas de hasta {dias} días dentro de las lluvias ({anio}).",
    "High water demand for most of the year.": "Alta demanda de agua durante casi todo el año.",
    "Low direct market value: cover crops are not sold, their benefit is mainly for the soil.":
        "Bajo valor directo de mercado: los cultivos de cobertura no se venden; su beneficio es sobre todo para el suelo.",
    "No major climate risk found in 2020-2025 for this rotation.":
        "No se encontró un riesgo climático importante en 2020-2025 para esta rotación.",
    "NDVI partly interpolated: {pct:.0f}% of periods had no clear-sky MODIS composite.":
        "NDVI parcialmente interpolado: {pct:.0f}% de los periodos no tuvo un compuesto MODIS sin nubes.",
    "Irrigation availability is assumed for this zone; confirm it for your plot.":
        "Se supone que hay riego disponible en esta zona; confírmalo para tu parcela.",
    "Cycles that run into 2026 use the 2020-2025 average for those periods in the 2025 backtest.":
        "Los ciclos que entran en 2026 usan el promedio 2020-2025 para esos periodos en la prueba de 2025.",
    "Satellite data describe the area around the zone point (rain and temperature from NASA POWER grid "
    "cells about 10-50 km across; NDVI from a ~2 km window), not your exact plot. Soil type, prices and "
    "costs are not included.":
        "Los datos satelitales describen el área alrededor del punto de la zona (lluvia y temperatura de "
        "celdas de NASA POWER de unos 10-50 km; NDVI de una ventana de ~2 km), no tu parcela exacta. "
        "No se incluyen tipo de suelo, precios ni costos.",

    # ------------------------------------------------------------ interfaz (app/streamlit_app.py)
    "Dark mode": "Modo oscuro", "Guide mode": "Modo guía",
    "Your farm": "Tu parcela", "Zone (Morelos, Mexico)": "Zona (Morelos, México)",
    "Current crop": "Cultivo actual", "Typical crop for this zone": "Cultivo típico de la zona",
    "Irrigation": "Riego", "Zone default": "Según la zona", "Irrigated": "Con riego", "Rainfed": "Temporal",
    "With irrigation, rainfall does not limit crop suitability.":
        "Con riego, la lluvia no limita la aptitud del cultivo.",
    "**Your priorities** (relative weights)": "**Tus prioridades** (pesos relativos)",
    "Advanced": "Avanzado", "Bare-soil NDVI threshold": "Umbral de NDVI para suelo desnudo",
    "A 21-day period counts as bare soil when its mean NDVI is below this.":
        "Un periodo de 21 días cuenta como suelo desnudo cuando su NDVI promedio está por debajo de este valor.",
    "Analyze": "Analizar",
    "Crop parameters are hypotheses pending validation. This tool supports, not replaces, farmer judgment.":
        "Los parámetros de cultivo son hipótesis por validar. Esta herramienta apoya, no sustituye, el "
        "criterio del agricultor.",
    "Could not load the project data: {e}. Run `python -m core.periodos` to rebuild it.":
        "No se pudieron cargar los datos del proyecto: {e}. Ejecuta `python -m core.periodos` para regenerarlos.",
    "Decision support for crop rotations in **sugarcane areas of Morelos, Mexico**, built on NASA "
    "satellite data summarized in **21-day periods** (17 per year, 2020-2025).":
        "Apoyo a la decisión sobre rotaciones de cultivos en **zonas cañeras de Morelos, México**, con datos "
        "satelitales de la NASA resumidos en **periodos de 21 días** (17 por año, 2020-2025).",
    "current crop": "cultivo actual", "priorities": "prioridades",
    "Diagnosis": "Diagnóstico", "Forecast": "Pronóstico", "Rotations": "Rotaciones",
    "Data & Method": "Datos y método",

    # Datos y método
    "Crop parameters: hypotheses": "Parámetros de cultivo: hipótesis",
    "These values are **hypotheses pending validation with local agronomists** (approximate ranges "
    "inspired by FAO EcoCrop). Edit any cell and the ranking in **Rotations** updates.":
        "Estos valores son **hipótesis pendientes de validar con agrónomos locales** (rangos aproximados "
        "inspirados en FAO EcoCrop). Edita cualquier celda y el ranking en **Rotaciones** se actualiza.",
    "Crop": "Cultivo", "Type": "Tipo", "Notes": "Notas", "Cycle (months)": "Ciclo (meses)",
    "Sowing month": "Mes de siembra",
    "Temp abs min °C": "Temp mín abs °C", "Temp opt min °C": "Temp mín ópt °C",
    "Temp opt max °C": "Temp máx ópt °C", "Temp abs max °C": "Temp máx abs °C",
    "Rain abs min mm": "Lluvia mín abs mm", "Rain opt min mm": "Lluvia mín ópt mm",
    "Rain opt max mm": "Lluvia máx ópt mm", "Rain abs max mm": "Lluvia máx abs mm",
    "Frost tolerant": "Tolera helada", "Water demand 0-1": "Demanda de agua 0-1",
    "Fixes nitrogen": "Fija nitrógeno", "Soil cover 0-1": "Cobertura del suelo 0-1",
    "Local market 0-1": "Mercado local 0-1",
    "Reset crop parameters to defaults": "Restablecer parámetros de cultivo",
    "Edited values are inconsistent, so the default parameters are used: ":
        "Los valores editados son inconsistentes, así que se usan los parámetros por defecto: ",
    "Data sources": "Fuentes de datos", "Method": "Método", "Candidate rotations": "Rotaciones candidatas",
    "Rotation": "Rotación", "Crops (sowing month)": "Cultivos (mes de siembra)",
    "Current practice for": "Práctica actual para",
    "Could not render the data & method section: {e}": "No se pudo mostrar la sección de datos y método: {e}",

    # Diagnóstico
    "Rainy season": "Temporada de lluvias", "No data": "Sin datos",
    "First and last 21-day period with > 35 mm on average":
        "Primer y último periodo de 21 días con más de 35 mm en promedio",
    "Bare-soil periods": "Periodos desnudos",
    "Periods with mean NDVI below the threshold": "Periodos con NDVI promedio por debajo del umbral",
    "Heat-risk periods": "Periodos de calor",
    "≥ 3 days with Tmax ≥ 35 °C on average": "≥ 3 días con Tmáx ≥ 35 °C en promedio",
    "Frost-risk periods": "Periodos de helada",
    "Any day with Tmin ≤ 2 °C on average": "Algún día con Tmín ≤ 2 °C en promedio",
    "Driest year ({mm:.0f} mm)": "Año más seco ({mm:.0f} mm)",
    "Lowest annual rainfall (GPM IMERG) in 2020-2025": "Menor lluvia anual (GPM IMERG) en 2020-2025",
    "Rainfall per 21-day period (mm, 2020-2025 mean ± 1 SD)":
        "Lluvia por periodo de 21 días (mm, media 2020-2025 ± 1 DE)",
    "NDVI, vegetation greenness (2020-2025 mean ± 1 SD)": "NDVI, verdor de la vegetación (media 2020-2025 ± 1 DE)",
    "Rainfall": "Lluvia", "bare soil": "suelo desnudo",
    "bare-soil threshold {umbral:.2f}": "umbral de suelo desnudo {umbral:.2f}",
    "Year": "Año", "Rain (mm)": "Lluvia (mm)", "Dry spell (days)": "Racha seca (días)", "Heat days": "Días de calor",
    "**Year by year**": "**Año por año**",
    "dry / normal / wet by terciles of annual rain": "seco / normal / húmedo por terciles de la lluvia anual",
    "Longest run of days with < 1 mm inside the rainy season":
        "Racha más larga de días con menos de 1 mm dentro de la temporada de lluvias",
    "Days with Tmax ≥ 35 °C": "Días con Tmáx ≥ 35 °C",
    "**Free windows for a cover crop**": "**Ventanas libres para un cultivo de cobertura**",
    "Period": "Periodo", "Needs": "Necesita", "irrigation": "riego", "rain is enough": "basta la lluvia",
    "No bare-soil periods detected, so no free windows.":
        "No se detectaron periodos de suelo desnudo, así que no hay ventanas libres.",
    "**NDVI per year and 21-day period** (darker = greener)":
        "**NDVI por año y periodo de 21 días** (más oscuro = más verde)",
    "**NDVI per year and 21-day period** (brighter = greener)":
        "**NDVI por año y periodo de 21 días** (más brillante = más verde)",
    "No data: {n} periods have no NDVI.": "Sin datos: {n} periodos no tienen NDVI.",
    "Could not build the diagnosis for this zone: {e}": "No se pudo generar el diagnóstico de esta zona: {e}",

    # Pronóstico
    "Rainfall (mm per 21 days)": "Lluvia (mm por 21 días)", "NDVI (vegetation greenness)": "NDVI (verdor de la vegetación)",
    "Seasonal naive (baseline)": "Estacional ingenuo (referencia)", "Prophet + rain lags": "Prophet + lluvia rezagada",
    "Linear regression (sliding window)": "Regresión lineal (ventana deslizante)",
    "Linear regression, log1p": "Regresión lineal, log1p",
    "Random forest (sliding window)": "Random forest (ventana deslizante)",
    "Prophet 80% interval": "intervalo de 80% de Prophet",
    "random-forest trees p10-p90": "árboles del random forest p10-p90",
    "± 80th percentile of the model's test error": "± percentil 80 del error de prueba del modelo",
    "no interval": "sin intervalo",
    "Variable": "Variable", "Best model (test MAE)": "Mejor modelo (MAE de prueba)",
    "Test MAE vs baseline": "MAE de prueba vs referencia", "{pct:.0f}% error": "{pct:.0f}% de error",
    "Mean absolute error on the held-out last 20 % of periods":
        "Error absoluto medio en el último 20 % de los periodos, reservado para prueba",
    "Forecast horizon": "Horizonte del pronóstico", "17 periods ({anio})": "17 periodos ({anio})",
    "Observed (NASA data)": "Observado (datos NASA)",
    "{modelo}: test-period forecast": "{modelo}: pronóstico del periodo de prueba",
    "80% interval": "Intervalo de 80%", "{modelo}: {anio} forecast": "{modelo}: pronóstico {anio}",
    "Seasonal naive baseline": "Referencia estacional ingenua", "test period →": "periodo de prueba →",
    "Interval: {intervalo}. Train = first {n_train} periods, test = last {n_test} (temporal split). "
    "Future rain/temperature used as model inputs = 2020-2025 average for that period. "
    "R² for rainfall is unstable in the dry season: read it with MAE.":
        "Intervalo: {intervalo}. Entrenamiento = primeros {n_train} periodos, prueba = últimos {n_test} "
        "(división temporal). La lluvia y temperatura futuras que usan los modelos = promedio 2020-2025 de ese "
        "periodo. El R² de la lluvia es inestable en secas: léelo junto con el MAE.",
    "Model": "Modelo", "Bias": "Sesgo",
    "Mean (forecast − observed); < 0 = underestimates": "Media (pronóstico − observado); < 0 = subestima",
    "MAE vs baseline": "MAE vs referencia", "Error reduction vs seasonal naive":
        "Reducción del error frente al estacional ingenuo",
    "80% interval coverage": "Cobertura del intervalo de 80%",
    "Share of test values inside the model's own 80% band (ideal ≈ 80%)":
        "Parte de los valores de prueba dentro de la banda de 80% del modelo (ideal ≈ 80%)",
    "Beats baseline": "Supera la referencia", "Best": "Mejor", "Params": "Parámetros",
    "Could not load the forecasts: {e}": "No se pudieron cargar los pronósticos: {e}",

    # Rotaciones
    "Using your edited crop parameters (Data & Method tab).":
        "Se usan tus parámetros de cultivo editados (pestaña Datos y método).",
    "**{n} candidate rotations** for {zona}, scored 0-100 with your priorities. "
    "The current rotation is the reference.":
        "**{n} rotaciones candidatas** para {zona}, calificadas de 0 a 100 con tus prioridades. "
        "La rotación actual es la referencia.",
    " (current)": " (actual)", "current": "actual",
    "{criterio}: %{{x:.1f}} pts": "{criterio}: %{{x:.1f}} pts",
    "Score (0-100) = sum of weighted criteria": "Puntaje (0-100) = suma de criterios ponderados",
    "Score breakdown as a table": "Desglose del puntaje en tabla",
    "Rank": "Lugar", "Current": "Actual", "Score": "Puntaje", "Worked (years)": "Funcionó (años)",
    "{dif:+.0f} vs current": "{dif:+.0f} vs actual",
    "**Worked in {ok} of {total} years** (2020-2025)": "**Funcionó en {ok} de {total} años** (2020-2025)",
    "✗ {anio} ({tipo} year): {cultivo}, limited by {factor}": "✗ {anio} (año {tipo}): {cultivo}, limitado por {factor}",
    "{anio} outlook (forecast rain): {estado} (min suitability {aptitud:.2f})":
        "Perspectiva {anio} (lluvia pronosticada): {estado} (aptitud mínima {aptitud:.2f})",
    "{criterio}: {valor:.2f} · weight {peso:.0%}": "{criterio}: {valor:.2f} · peso {peso:.0%}",
    "Crop calendar (21-day periods)": "Calendario de cultivos (periodos de 21 días)",
    "Bare soil today (NDVI)": "Suelo desnudo hoy (NDVI)", "Bare soil today": "Suelo desnudo hoy",
    "Why this rotation? Evidence, benefits, risks and information gaps":
        "¿Por qué esta rotación? Evidencia, beneficios, riesgos y vacíos de información",
    "**Why suggested.** {texto}": "**Por qué se sugiere.** {texto}",
    "Evidence": "Evidencia", "Benefits": "Beneficios", "Risks": "Riesgos",
    "Information gaps": "Vacíos de información",
    "Could not score the rotations: {e}": "No se pudieron calificar las rotaciones: {e}",
    "NASA Space Apps Challenge 2026 · Field Shift: Adapting Farms with NASA Data · "
    "This tool supports, not replaces, farmer judgment.":
        "NASA Space Apps Challenge 2026 · Field Shift: Adapting Farms with NASA Data · "
        "Esta herramienta apoya, no sustituye, el criterio del agricultor.",
}


BLOQUES = {
    "fuentes": {
        "en": (
            "- **Rainfall**: NASA GPM IMERG (`IMERG_PRECTOT`), daily, via the "
            "[NASA POWER API](https://power.larc.nasa.gov/) · [GPM IMERG](https://gpm.nasa.gov/data/imerg)\n"
            "- **Temperature**: NASA POWER daily max/min (MERRA-2 reanalysis, ~0.5° cells)\n"
            "- **Vegetation**: [MODIS MOD13Q1](https://lpdaac.usgs.gov/products/mod13q1v061/) NDVI, 16-day "
            "composites at 250 m, with pixel reliability, from the "
            "[ORNL DAAC MODIS web service](https://modis.ornl.gov/data/modis_webservice.html) (9×9 pixel window "
            "around each zone point)\n"
            "- **Crop ranges**: inspired by [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop); "
            "**forecasting**: [Prophet](https://facebook.github.io/prophet/) and scikit-learn"),
        "es": (
            "- **Lluvia**: NASA GPM IMERG (`IMERG_PRECTOT`), diaria, vía la "
            "[API de NASA POWER](https://power.larc.nasa.gov/) · [GPM IMERG](https://gpm.nasa.gov/data/imerg)\n"
            "- **Temperatura**: máxima y mínima diaria de NASA POWER (reanálisis MERRA-2, celdas de ~0.5°)\n"
            "- **Vegetación**: NDVI de [MODIS MOD13Q1](https://lpdaac.usgs.gov/products/mod13q1v061/), compuestos "
            "de 16 días a 250 m, con confiabilidad de píxel, del "
            "[servicio web MODIS de ORNL DAAC](https://modis.ornl.gov/data/modis_webservice.html) (ventana de 9×9 "
            "píxeles alrededor del punto de cada zona)\n"
            "- **Rangos de cultivo**: inspirados en [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop); "
            "**pronóstico**: [Prophet](https://facebook.github.io/prophet/) y scikit-learn"),
    },
    "metodo": {
        "en": (
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
            "**Backtesting:** a year *worked* if every crop in the rotation reached suitability ≥ 0.6 with that year's weather."),
        "es": (
            "1. **Periodos de 21 días.** Cada año se divide en 17 periodos fijos anclados al 1 de enero (el periodo *k* "
            "empieza el día 1 + 21·(k−1); P17 absorbe los 29-30 días restantes), así que P08 de 2021 es comparable con P08 de 2024.\n"
            "2. **Tabla integrada.** La lluvia y la temperatura diarias se suman o promedian por periodo; los compuestos "
            "de NDVI (cada 16 días) se limpian de píxeles nubosos, se interpolan linealmente a valores diarios y se promedian por periodo.\n"
            "3. **Diagnóstico.** Promedios 2020-2025 por periodo: suelo desnudo (NDVI bajo el umbral), temporada de lluvias "
            "(> 35 mm por 21 días), riesgo de helada (Tmín ≤ 2 °C) y de calor (≥ 3 días con Tmáx ≥ 35 °C), rachas secas, y "
            "años secos / normales / húmedos por terciles de la lluvia anual.\n"
            "4. **Pronóstico.** El último 20 % de los periodos se reserva para prueba (división temporal, nunca aleatoria). "
            "Cada modelo pronostica ese bloque desde el final del entrenamiento y se compara por MAE con una referencia "
            "estacional ingenua (el mismo periodo del año anterior). El mejor modelo se reentrena con todos los datos para "
            "pronosticar los siguientes 17 periodos.\n"
            "5. **Aptitud del cultivo.** Trapecios tipo EcoCrop para temperatura y lluvia del ciclo, más una penalización "
            "por helada; el factor más débil es la aptitud (0-1). El riego elimina el límite de lluvia.\n"
            "6. **Puntaje de la rotación.** Suma ponderada de ajuste al clima, ahorro de agua (demanda de agua ponderada "
            "por tiempo), salud del suelo (fijación de nitrógeno, cobertura todo el año, diversidad de cultivos, periodos "
            "desnudos cubiertos) e ingreso (mercado local). **Prueba histórica:** un año *funcionó* si todos los cultivos "
            "de la rotación alcanzaron aptitud ≥ 0.6 con el clima de ese año."),
    },
    "guia_inicio": {
        "en": (
            "**Guide: how to use CropCompass**\n"
            "1. In the left panel choose your **zone**, **current crop** and **irrigation**, move the four **priority** "
            "sliders, and press **Analyze**.\n"
            "2. **Diagnosis** shows what the satellites saw in your zone from 2020 to 2025.\n"
            "3. **Forecast** shows the expected rain and vegetation for the next year, and how reliable the model was.\n"
            "4. **Rotations** compares your current rotation with the alternatives. Open *Why this rotation?* on any card.\n"
            "5. **Data & Method** lets you correct the crop values if you know better ones.\n\n"
            "Each tab starts with a note like this one. Turn off *Guide mode* to hide them."),
        "es": (
            "**Guía: cómo usar CropCompass**\n"
            "1. En el panel izquierdo elige tu **zona**, tu **cultivo actual** y el **riego**, mueve los cuatro "
            "controles de **prioridades** y presiona **Analizar**.\n"
            "2. **Diagnóstico** muestra lo que vieron los satélites en tu zona de 2020 a 2025.\n"
            "3. **Pronóstico** muestra la lluvia y la vegetación esperadas para el próximo año, y qué tan confiable fue el modelo.\n"
            "4. **Rotaciones** compara tu rotación actual con las alternativas. Abre *¿Por qué esta rotación?* en cualquier tarjeta.\n"
            "5. **Datos y método** te deja corregir los valores de los cultivos si conoces mejores.\n\n"
            "Cada pestaña empieza con una nota como esta. Apaga el *Modo guía* para ocultarlas."),
    },
    "guia_prioridades": {
        "en": "Guide: a higher slider gives that criterion more weight in the score. Only the proportions matter: "
              "all at 5 is the same as all at 10.",
        "es": "Guía: un control más alto le da más peso a ese criterio en el puntaje. Solo importan las "
              "proporciones: todos en 5 equivale a todos en 10.",
    },
    "guia_diagnosis": {
        "en": (
            "**How to read this tab**\n"
            "- The year is split into **17 periods of 21 days** (P01 starts January 1, P17 ends December 31).\n"
            "- **Blue bars** are the average rain in each period; the thin lines show how much it varied between years.\n"
            "- The **green line** is NDVI, a satellite measure of how green the land is: about 0.2-0.3 is bare soil, "
            "above 0.5 is dense vegetation.\n"
            "- **Gray bands** mark periods when the soil is usually bare. Those are the windows where a cover crop could fit.\n"
            "- The tables below show each year: whether it was dry or wet, its longest dry spell, and its hot days."),
        "es": (
            "**Cómo leer esta pestaña**\n"
            "- El año se divide en **17 periodos de 21 días** (P01 empieza el 1 de enero, P17 termina el 31 de diciembre).\n"
            "- Las **barras azules** son la lluvia promedio de cada periodo; las líneas delgadas muestran cuánto varió entre años.\n"
            "- La **línea verde** es el NDVI, una medida satelital de qué tan verde está el terreno: alrededor de 0.2-0.3 "
            "es suelo desnudo, arriba de 0.5 es vegetación densa.\n"
            "- Las **bandas grises** marcan los periodos en que el suelo suele estar desnudo. Son las ventanas donde "
            "cabría un cultivo de cobertura.\n"
            "- Las tablas de abajo muestran cada año: si fue seco o húmedo, su racha seca más larga y sus días de calor."),
    },
    "guia_forecast": {
        "en": (
            "**How to read this tab**\n"
            "- The **gray line** is what NASA data observed. The **solid blue line** is the forecast for next year, "
            "and the shaded band is where the value should fall about 8 times out of 10.\n"
            "- The **dashed blue line** is a test: the model forecast a period it had not seen, so you can compare it with what really happened.\n"
            "- The **dotted orange line** is the simple reference: \"same as the same period last year\". A model is only "
            "useful if its error (MAE) is lower than that reference.\n"
            "- The table lists every model tried. A forecast is a guide, not a guarantee."),
        "es": (
            "**Cómo leer esta pestaña**\n"
            "- La **línea gris** es lo que observaron los datos de la NASA. La **línea azul continua** es el pronóstico "
            "del próximo año, y la banda sombreada es donde debería caer el valor unas 8 de cada 10 veces.\n"
            "- La **línea azul punteada larga** es una prueba: el modelo pronosticó un periodo que no había visto, para "
            "compararlo con lo que pasó de verdad.\n"
            "- La **línea naranja de puntos** es la referencia simple: \"igual que el mismo periodo del año pasado\". Un "
            "modelo solo sirve si su error (MAE) es menor que esa referencia.\n"
            "- La tabla lista todos los modelos probados. Un pronóstico es una guía, no una garantía."),
    },
    "guia_rotations": {
        "en": (
            "**How to read this tab**\n"
            "- Each rotation gets a **score from 0 to 100**: the sum of four criteria weighted by your priorities. "
            "The colored chart shows how much each criterion adds.\n"
            "- **\"+10 vs current\"** means it scores 10 points more than what you grow today.\n"
            "- **\"Worked in X of 6 years\"** replays 2020-2025: a year counts only if every crop in the rotation had suitable weather.\n"
            "- The **calendar** shows which 21-day periods each crop occupies, next to the periods when your soil is bare today.\n"
            "- Open **Why this rotation?** for the evidence, benefits, risks and what is still unknown."),
        "es": (
            "**Cómo leer esta pestaña**\n"
            "- Cada rotación recibe un **puntaje de 0 a 100**: la suma de cuatro criterios ponderados por tus prioridades. "
            "La gráfica de colores muestra cuánto aporta cada criterio.\n"
            "- **\"+10 vs actual\"** significa que obtiene 10 puntos más que lo que siembras hoy.\n"
            "- **\"Funcionó en X de 6 años\"** repite 2020-2025: un año cuenta solo si todos los cultivos de la rotación tuvieron clima apto.\n"
            "- El **calendario** muestra qué periodos de 21 días ocupa cada cultivo, junto a los periodos en que tu suelo está desnudo hoy.\n"
            "- Abre **¿Por qué esta rotación?** para ver la evidencia, los beneficios, los riesgos y lo que aún no se sabe."),
    },
    "guia_method": {
        "en": (
            "**How to use this tab**\n"
            "- The crop table holds the values the scores are built on. They are **hypotheses**: if you or an agronomist "
            "know better values for your area, edit the cell and the ranking updates.\n"
            "- Below are the NASA data sources and the method, step by step."),
        "es": (
            "**Cómo usar esta pestaña**\n"
            "- La tabla de cultivos tiene los valores con los que se calculan los puntajes. Son **hipótesis**: si tú o un "
            "agrónomo conocen mejores valores para tu zona, edita la celda y el ranking se actualiza.\n"
            "- Abajo están las fuentes de datos de la NASA y el método, paso a paso."),
    },
}
