"""Explicaciones en inglés (plantillas f-string, sin LLM) de cada rotación del ranking.

explicar(r, actual, diag, zona_info) -> {why_suggested, evidence, benefits, risks, information_gaps, disclaimer}
Todo número que aparece sale de los resultados de core.rotaciones / core.indicadores: nada se inventa.
"""
from __future__ import annotations

import pandas as pd

from core import aptitud as A
from core import periodos as P

DISCLAIMER = "This tool supports, not replaces, farmer judgment."
GAP_HIPOTESIS = ("Crop parameters (temperature and rainfall ranges, water demand, local market) are "
                 "hypotheses pending validation with local agronomists.")
FUENTES = ("Data: rainfall from NASA GPM IMERG and temperature from NASA POWER (MERRA-2), both via the "
           "NASA POWER API; vegetation from MODIS MOD13Q1 NDVI (250 m, ORNL DAAC); 2020-2025, "
           "summarized in 17 fixed 21-day periods per year.")
NOMBRE_CRITERIO = {"climate": "climate fit", "water": "water saving", "soil": "soil health", "income": "income"}
# Frase natural cuando el criterio sube / baja respecto a la rotación actual
CAMBIO_CRITERIO = {
    "water": ("lower water use", "higher water use"),
    "soil": ("better soil health", "weaker soil health"),
    "income": ("higher income potential", "lower income potential"),
    "climate": ("better climate fit", "weaker climate fit"),
}
UMBRAL_NDVI_INTERPOLADO_PCT = 20.0   # % de periodos sin compuesto real a partir del cual se avisa
UMBRAL_CERCA_DEL_LIMITE = 0.8        # aptitud de una etapa por debajo de esto = riesgo


def _etiquetas(periodos: list[int]) -> str:
    """'P02 (Jan 22 – Feb 11), P05 (…)', o compacto 'P01-P07 (Jan 1 – May 27)' si son más de 3 seguidos."""
    if not periodos:
        return "none"
    ps = sorted(set(periodos))
    if len(ps) > 3 and ps == list(range(ps[0], ps[-1] + 1)):
        cal = P.calendario(P.ANIO_REFERENCIA).set_index("periodo")
        ini, fin = cal.loc[ps[0], "fecha_inicio"], cal.loc[ps[-1], "fecha_fin"]
        return (f"P{ps[0]:02d}-P{ps[-1]:02d} ({P.MESES_EN[ini.month - 1]} {ini.day} – "
                f"{P.MESES_EN[fin.month - 1]} {fin.day})")
    return ", ".join(P.etiquetas()[p - 1] for p in ps)


def _lista(nombres: list[str]) -> str:
    nombres = list(dict.fromkeys(nombres))
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " and " + nombres[-1]


def _nombre_cultivo(r: dict, cultivo_id: str | None) -> str:
    return next((e["cultivo"] for e in r["etapas"] if e["cultivo_id"] == cultivo_id), cultivo_id or "?")


# ---------------------------------------------------------------- secciones

def why_suggested(r: dict, actual: dict | None, n_total: int, promedios: dict | None = None) -> str:
    """promedios: criterio -> promedio entre todas las rotaciones del ranking (para decir en qué destaca)."""
    partes = [f"Ranked #{r['rango']} of {n_total} with {r['puntaje']:.0f}/100 under your priorities."]
    if promedios:
        # Destaca donde su aporte ponderado supera más al promedio de las opciones
        ventaja = {c: r["pesos"][c] * (r["criterios"][c] - promedios[c]) for c in promedios}
        c = max(ventaja, key=ventaja.get)
        if r["criterios"][c] - promedios[c] >= 0.05 and r["pesos"][c] > 0:
            partes.append(f"It stands out on {NOMBRE_CRITERIO[c]}: {r['criterios'][c]:.2f} vs "
                          f"{promedios[c]:.2f} on average among the options (0-1 scale).")
    if r["es_actual"]:
        partes.append("This is your current rotation, shown as the reference point.")
    elif actual is not None:
        dif = r["puntaje"] - actual["puntaje"]
        cambios = [CAMBIO_CRITERIO[c][0 if r["criterios"][c] > actual["criterios"][c] else 1]
                   for c in ("water", "soil", "income", "climate")
                   if abs(r["criterios"][c] - actual["criterios"][c]) >= 0.05]
        partes.append(f"Compared with your current rotation ({actual['nombre']}, {actual['puntaje']:.0f}/100) it scores "
                      f"{abs(dif):.0f} points {'higher' if dif >= 0 else 'lower'}"
                      + (f": {_lista(cambios)}." if cambios else ", with similar criteria."))
    return " ".join(partes)


def evidence(r: dict) -> list[str]:
    ev = []
    for e in r["etapas"]:
        f = e["factores"]
        lluvia_txt = "irrigated" if e["riego"] else f"rainfall {f['rainfall']:.2f}"
        ev.append(f"{e['cultivo']}: sown in {e['inicio']}, {len(e['periodos'])} periods "
                  f"(until {e['fin']}). Climate suitability {e['aptitud']:.2f} "
                  f"(temperature {f['temperature']:.2f}, {lluvia_txt}, frost {f['frost']:.2f}); "
                  f"2020-2025 average {e['temp_media_c']:.1f} °C and {e['lluvia_mm']:.0f} mm of rain in the cycle.")
    bt = r["backtest"]
    ev.append(f"Worked in {bt['anios_ok']} of {bt['anios_total']} years (2020-2025): every crop reached "
              f"climate suitability ≥ {bt['umbral']:.1f} in that year's real weather.")
    for d in bt["fallidos"]:
        ev.append(f"Failed in {d['anio']} ({d['tipo_anio']} year): {_nombre_cultivo(r, d['cultivo_limitante'])} "
                  f"limited by {d['factor_limitante']} (suitability {d['aptitud_min']:.2f}).")
    desnudos, cubiertos = r["desnudos_zona"], r["desnudos_cubiertos"]
    if desnudos:
        ev.append(f"Covers {len(cubiertos)} of the {len(desnudos)} bare-soil periods detected with MODIS NDVI "
                  f"in this zone ({_etiquetas(desnudos)})" + (f": {_etiquetas(cubiertos)}." if cubiertos else "."))
    else:
        ev.append("MODIS NDVI shows no bare-soil periods in this zone (average NDVI ≥ 0.30 all year).")
    o = r.get("outlook")
    if o:
        ev.append(f"{o['anio']} outlook with forecast rainfall (temperatures = 2020-2025 average): minimum "
                  f"suitability {o['aptitud_min']:.2f}, {'viable' if o['ok'] else 'at risk'}.")
    ev.append(FUENTES)
    return ev


def benefits(r: dict, actual: dict | None) -> list[str]:
    b = []
    fijadores = [e["cultivo"] for e in r["etapas"] if e.get("fija_nitrogeno")]
    if fijadores:
        que = "a nitrogen-fixing legume" if len(fijadores) == 1 else "nitrogen-fixing legumes"
        b.append(f"Includes {que} ({_lista(fijadores)}), which can lower fertilizer needs for the next crop.")
    n_cub = len(r["desnudos_cubiertos"])
    if n_cub:
        b.append(f"Keeps living cover in {n_cub} {'period that is' if n_cub == 1 else 'periods that are'} "
                 "usually bare, reducing erosion and weed pressure.")
    if r["suelo_detalle"]["crop_diversity"] >= 0.5:
        b.append("Alternates different crops, which helps break pest and disease cycles.")
    if actual is not None and not r["es_actual"] and r["criterios"]["water"] - actual["criterios"]["water"] >= 0.05:
        b.append(f"Lower water demand than your current rotation (uses {1 - r['criterios']['water']:.0%} of the "
                 f"year's maximum demand vs {1 - actual['criterios']['water']:.0%}).")
    if r["criterios"]["income"] >= 0.7:
        b.append("Built on crops with a strong local market.")
    bt = r["backtest"]
    if bt["anios_total"] and bt["anios_ok"] == bt["anios_total"]:
        b.append(f"Climatically viable in all {bt['anios_total']} years analyzed, including dry and wet years.")
    return b or ["No clear advantage over the alternatives under the current weights."]


def risks(r: dict, diag: dict | None) -> list[str]:
    rs = []
    bt = r["backtest"]
    if bt["fallidos"]:
        factores = pd.Series([d["factor_limitante"] for d in bt["fallidos"]]).value_counts()
        rs.append(f"Did not work in {len(bt['fallidos'])} of {bt['anios_total']} years; most often limited by "
                  f"{factores.index[0]}.")
    for e in r["etapas"]:
        if e["aptitud"] < UMBRAL_CERCA_DEL_LIMITE and e["limitante"]:
            rs.append(f"{e['cultivo']} is close to its {e['limitante']} limit (suitability {e['aptitud']:.2f}).")
        if e["riego"] and not pd.isna(e["factor_lluvia_temporal"]) and e["factor_lluvia_temporal"] < A.UMBRAL_OK:
            lo, hi = e["lluvia_opt_mm"]
            rs.append(f"{e['cultivo']} depends on irrigation: its cycle gets {e['lluvia_mm']:.0f} mm of rain on "
                      f"average vs an optimum of {lo:.0f}-{hi:.0f} mm.")
    if diag is not None:
        calor = set(diag.get("calor", []))
        for e in r["etapas"]:
            solape = sorted(calor & set(e["periodos"]))
            if solape:
                rs.append(f"{e['cultivo']} grows through periods with frequent heat ≥ 35 °C ({_etiquetas(solape)}).")
        racha = diag.get("racha_seca_temporal") or {}
        temporal = set((diag.get("temporal") or {}).get("periodos", []))
        if racha and any(not e["riego"] and temporal & set(e["periodos"]) for e in r["etapas"]):
            anio, dias = max(racha.items(), key=lambda kv: kv[1])
            rs.append(f"Rainfed crops in the rainy season faced dry spells of up to {dias} days ({anio}).")
    if r["criterios"]["water"] < 0.3:
        rs.append("High water demand for most of the year.")
    if r["criterios"]["income"] < 0.4:
        rs.append("Low direct market value: cover crops are not sold, their benefit is mainly for the soil.")
    return rs or ["No major climate risk found in 2020-2025 for this rotation."]


def information_gaps(r: dict, diag: dict | None, zona_info: dict | None) -> list[str]:
    g = [GAP_HIPOTESIS]
    if diag is not None and (diag.get("ndvi_interpolado_pct") or 0) > UMBRAL_NDVI_INTERPOLADO_PCT:
        g.append(f"NDVI partly interpolated: {diag['ndvi_interpolado_pct']:.0f}% of periods had no clear-sky "
                 "MODIS composite.")
    if zona_info and zona_info.get("aviso") and not pd.isna(zona_info.get("aviso")):
        g.append(str(zona_info["aviso"]))
    if r["riego"]:
        g.append("Irrigation availability is assumed for this zone; confirm it for your plot.")
    if any(d.get("usa_climatologia") for d in r["backtest"]["anios"]):
        g.append("Cycles that run into 2026 use the 2020-2025 average for those periods in the 2025 backtest.")
    g.append("Satellite data describe the area around the zone point (rain and temperature from NASA POWER grid "
             "cells about 10-50 km across; NDVI from a ~2 km window), not your exact plot. Soil type, prices and "
             "costs are not included.")
    return g


def explicar(r: dict, actual: dict | None = None, diag: dict | None = None, zona_info: dict | None = None,
             n_total: int | None = None, promedios: dict | None = None) -> dict:
    return {
        "why_suggested": why_suggested(r, actual, n_total or r["rango"], promedios),
        "evidence": evidence(r),
        "benefits": benefits(r, actual),
        "risks": risks(r, diag),
        "information_gaps": information_gaps(r, diag, zona_info),
        "disclaimer": DISCLAIMER,
    }


def explicar_ranking(resultados: list[dict], diag: dict | None = None,
                     zona_info: dict | None = None) -> list[dict]:
    """Agrega r['explicacion'] a cada rotación del ranking."""
    actual = next((r for r in resultados if r["es_actual"]), None)
    promedios = {c: float(pd.Series([r["criterios"][c] for r in resultados]).mean())
                 for c in ("climate", "water", "soil", "income")}
    for r in resultados:
        r["explicacion"] = explicar(r, actual, diag, zona_info, len(resultados), promedios)
    return resultados


def texto(exp: dict) -> str:
    """Versión de texto plano (consola / README)."""
    secciones = [("Why suggested", [exp["why_suggested"]]), ("Evidence", exp["evidence"]),
                 ("Benefits", exp["benefits"]), ("Risks", exp["risks"]),
                 ("Information gaps", exp["information_gaps"])]
    lineas = []
    for titulo, items in secciones:
        lineas.append(f"  {titulo}:")
        lineas += [f"    - {x}" for x in items]
    lineas.append(f"  {exp['disclaimer']}")
    return "\n".join(lineas)


if __name__ == "__main__":
    import sys
    from core import datos
    from core import indicadores as I
    from core import rotaciones as R

    sys.stdout.reconfigure(encoding="utf-8")
    zona = sys.argv[1] if len(sys.argv) > 1 else "axochiapan"
    zonas = datos.cargar_zonas()
    diag = I.diagnostico(P.cargar_serie_21d(), datos.cargar_clima_diario(), zona)
    lluvia, anio = R.cargar_lluvia_outlook(zona)
    res = explicar_ranking(R.rankear(zona, lluvia_outlook=lluvia, anio_outlook=anio), diag,
                           zonas.set_index("id").loc[zona].to_dict())
    for r in res[:2] + [x for x in res[2:] if x["es_actual"]]:
        print(f"\n#{r['rango']} {r['nombre']}{' [CURRENT]' if r['es_actual'] else ''}")
        print(texto(r["explicacion"]))
