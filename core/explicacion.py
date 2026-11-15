"""Explicaciones de cada rotación del ranking: plantillas fijas (sin LLM), en inglés o español.

explicar(r, actual, diag, zona_info, idioma="en")
    -> {why_suggested, evidence, benefits, risks, information_gaps, disclaimer}
Todo número que aparece sale de los resultados de core.rotaciones / core.indicadores: nada se inventa.
El inglés es el idioma base; el español sale de core.i18n (mismas plantillas, mismos números).
"""
from __future__ import annotations

import pandas as pd

from core import aptitud as A
from core import periodos as P
from core.i18n import fechas, tr

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


def _etiquetas(periodos: list[int], idioma: str = "en") -> str:
    """'P02 (Jan 22 – Feb 11), P05 (…)', o compacto 'P01-P07 (Jan 1 – May 27)' si son más de 3 seguidos."""
    if not periodos:
        return tr("none", idioma)
    ps = sorted(set(periodos))
    if len(ps) > 3 and ps == list(range(ps[0], ps[-1] + 1)):
        cal = P.calendario(P.ANIO_REFERENCIA).set_index("periodo")
        ini, fin = cal.loc[ps[0], "fecha_inicio"], cal.loc[ps[-1], "fecha_fin"]
        texto = (f"P{ps[0]:02d}-P{ps[-1]:02d} ({P.MESES_EN[ini.month - 1]} {ini.day} – "
                 f"{P.MESES_EN[fin.month - 1]} {fin.day})")
    else:
        texto = ", ".join(P.etiquetas()[p - 1] for p in ps)
    return fechas(texto, idioma)


def _lista(nombres: list[str], idioma: str = "en") -> str:
    nombres = list(dict.fromkeys(nombres))
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + tr(" and ", idioma) + nombres[-1]


def _nc(etapa: dict, idioma: str = "en") -> str:
    """Nombre del cultivo de una etapa en el idioma pedido."""
    return etapa.get("cultivo_es", etapa["cultivo"]) if idioma == "es" else etapa["cultivo"]


def _nr(r: dict, idioma: str = "en") -> str:
    return r.get("nombre_es", r["nombre"]) if idioma == "es" else r["nombre"]


def _nombre_cultivo(r: dict, cultivo_id: str | None, idioma: str = "en") -> str:
    return next((_nc(e, idioma) for e in r["etapas"] if e["cultivo_id"] == cultivo_id), cultivo_id or "?")


# ---------------------------------------------------------------- secciones

def why_suggested(r: dict, actual: dict | None, n_total: int, promedios: dict | None = None,
                  idioma: str = "en") -> str:
    """promedios: criterio -> promedio entre todas las rotaciones del ranking (para decir en qué destaca)."""
    T = lambda s: tr(s, idioma)
    partes = [T("Ranked #{rango} of {n} with {puntaje:.0f}/100 under your priorities.").format(
        rango=r["rango"], n=n_total, puntaje=r["puntaje"])]
    if promedios:
        # Destaca donde su aporte ponderado supera más al promedio de las opciones
        ventaja = {c: r["pesos"][c] * (r["criterios"][c] - promedios[c]) for c in promedios}
        c = max(ventaja, key=ventaja.get)
        if r["criterios"][c] - promedios[c] >= 0.05 and r["pesos"][c] > 0:
            partes.append(T("It stands out on {criterio}: {valor:.2f} vs {promedio:.2f} on average among the "
                            "options (0-1 scale).").format(criterio=T(NOMBRE_CRITERIO[c]), valor=r["criterios"][c],
                                                           promedio=promedios[c]))
    if r["es_actual"]:
        partes.append(T("This is your current rotation, shown as the reference point."))
    elif actual is not None:
        dif = r["puntaje"] - actual["puntaje"]
        cambios = [T(CAMBIO_CRITERIO[c][0 if r["criterios"][c] > actual["criterios"][c] else 1])
                   for c in ("water", "soil", "income", "climate")
                   if abs(r["criterios"][c] - actual["criterios"][c]) >= 0.05]
        datos = dict(nombre=_nr(actual, idioma), puntaje=actual["puntaje"], dif=abs(dif),
                     sentido=T("higher") if dif >= 0 else T("lower"))
        if cambios:
            partes.append(T("Compared with your current rotation ({nombre}, {puntaje:.0f}/100) it scores {dif:.0f} "
                            "points {sentido}: {cambios}.").format(cambios=_lista(cambios, idioma), **datos))
        else:
            partes.append(T("Compared with your current rotation ({nombre}, {puntaje:.0f}/100) it scores {dif:.0f} "
                            "points {sentido}, with similar criteria.").format(**datos))
    return " ".join(partes)


def evidence(r: dict, idioma: str = "en") -> list[str]:
    T = lambda s: tr(s, idioma)
    ev = []
    for e in r["etapas"]:
        f = e["factores"]
        lluvia_txt = T("irrigated") if e["riego"] else T("rainfall {valor:.2f}").format(valor=f["rainfall"])
        ev.append(T("{cultivo}: sown in {inicio}, {n} periods (until {fin}). Climate suitability {aptitud:.2f} "
                    "(temperature {temp:.2f}, {lluvia}, frost {helada:.2f}); "
                    "2020-2025 average {grados:.1f} °C and {mm:.0f} mm of rain in the cycle.").format(
            cultivo=_nc(e, idioma), inicio=fechas(e["inicio"], idioma), n=len(e["periodos"]),
            fin=fechas(e["fin"], idioma), aptitud=e["aptitud"], temp=f["temperature"], lluvia=lluvia_txt,
            helada=f["frost"], grados=e["temp_media_c"], mm=e["lluvia_mm"]))
    bt = r["backtest"]
    ev.append(T("Worked in {ok} of {total} years (2020-2025): every crop reached "
                "climate suitability ≥ {umbral:.1f} in that year's real weather.").format(
        ok=bt["anios_ok"], total=bt["anios_total"], umbral=bt["umbral"]))
    for d in bt["fallidos"]:
        ev.append(T("Failed in {anio} ({tipo} year): {cultivo} limited by {factor} (suitability {aptitud:.2f}).").format(
            anio=d["anio"], tipo=T(d["tipo_anio"]), cultivo=_nombre_cultivo(r, d["cultivo_limitante"], idioma),
            factor=T(str(d["factor_limitante"])), aptitud=d["aptitud_min"]))
    desnudos, cubiertos = r["desnudos_zona"], r["desnudos_cubiertos"]
    if desnudos and cubiertos:
        ev.append(T("Covers {n} of the {total} bare-soil periods detected with MODIS NDVI in this zone "
                    "({periodos}): {cubiertos}.").format(n=len(cubiertos), total=len(desnudos),
                                                         periodos=_etiquetas(desnudos, idioma),
                                                         cubiertos=_etiquetas(cubiertos, idioma)))
    elif desnudos:
        ev.append(T("Covers {n} of the {total} bare-soil periods detected with MODIS NDVI in this zone "
                    "({periodos}).").format(n=0, total=len(desnudos), periodos=_etiquetas(desnudos, idioma)))
    else:
        ev.append(T("MODIS NDVI shows no bare-soil periods in this zone (average NDVI ≥ 0.30 all year)."))
    o = r.get("outlook")
    if o:
        ev.append(T("{anio} outlook with forecast rainfall (temperatures = 2020-2025 average): minimum "
                    "suitability {aptitud:.2f}, {estado}.").format(
            anio=o["anio"], aptitud=o["aptitud_min"], estado=T("viable") if o["ok"] else T("at risk")))
    ev.append(T(FUENTES))
    return ev


def benefits(r: dict, actual: dict | None, idioma: str = "en") -> list[str]:
    T = lambda s: tr(s, idioma)
    b = []
    fijadores = [_nc(e, idioma) for e in r["etapas"] if e.get("fija_nitrogeno")]
    if len(fijadores) == 1:
        b.append(T("Includes a nitrogen-fixing legume ({cultivos}), which can lower fertilizer needs for the "
                   "next crop.").format(cultivos=_lista(fijadores, idioma)))
    elif fijadores:
        b.append(T("Includes nitrogen-fixing legumes ({cultivos}), which can lower fertilizer needs for the "
                   "next crop.").format(cultivos=_lista(fijadores, idioma)))
    n_cub = len(r["desnudos_cubiertos"])
    if n_cub == 1:
        b.append(T("Keeps living cover in {n} period that is usually bare, reducing erosion and weed "
                   "pressure.").format(n=n_cub))
    elif n_cub:
        b.append(T("Keeps living cover in {n} periods that are usually bare, reducing erosion and weed "
                   "pressure.").format(n=n_cub))
    if r["suelo_detalle"]["crop_diversity"] >= 0.5:
        b.append(T("Alternates different crops, which helps break pest and disease cycles."))
    if actual is not None and not r["es_actual"] and r["criterios"]["water"] - actual["criterios"]["water"] >= 0.05:
        b.append(T("Lower water demand than your current rotation (uses {esta:.0%} of the "
                   "year's maximum demand vs {actual:.0%}).").format(
            esta=1 - r["criterios"]["water"], actual=1 - actual["criterios"]["water"]))
    if r["criterios"]["income"] >= 0.7:
        b.append(T("Built on crops with a strong local market."))
    bt = r["backtest"]
    if bt["anios_total"] and bt["anios_ok"] == bt["anios_total"]:
        b.append(T("Climatically viable in all {n} years analyzed, including dry and wet years.").format(
            n=bt["anios_total"]))
    return b or [T("No clear advantage over the alternatives under the current weights.")]


def risks(r: dict, diag: dict | None, idioma: str = "en") -> list[str]:
    T = lambda s: tr(s, idioma)
    rs = []
    bt = r["backtest"]
    if bt["fallidos"]:
        factores = pd.Series([d["factor_limitante"] for d in bt["fallidos"]]).value_counts()
        rs.append(T("Did not work in {n} of {total} years; most often limited by {factor}.").format(
            n=len(bt["fallidos"]), total=bt["anios_total"], factor=T(str(factores.index[0]))))
    for e in r["etapas"]:
        if e["aptitud"] < UMBRAL_CERCA_DEL_LIMITE and e["limitante"]:
            rs.append(T("{cultivo} is close to its {factor} limit (suitability {aptitud:.2f}).").format(
                cultivo=_nc(e, idioma), factor=T(e["limitante"]), aptitud=e["aptitud"]))
        if e["riego"] and not pd.isna(e["factor_lluvia_temporal"]) and e["factor_lluvia_temporal"] < A.UMBRAL_OK:
            lo, hi = e["lluvia_opt_mm"]
            rs.append(T("{cultivo} depends on irrigation: its cycle gets {mm:.0f} mm of rain on "
                        "average vs an optimum of {lo:.0f}-{hi:.0f} mm.").format(
                cultivo=_nc(e, idioma), mm=e["lluvia_mm"], lo=lo, hi=hi))
    if diag is not None:
        calor = set(diag.get("calor", []))
        for e in r["etapas"]:
            solape = sorted(calor & set(e["periodos"]))
            if solape:
                rs.append(T("{cultivo} grows through periods with frequent heat ≥ 35 °C ({periodos}).").format(
                    cultivo=_nc(e, idioma), periodos=_etiquetas(solape, idioma)))
        racha = diag.get("racha_seca_temporal") or {}
        temporal = set((diag.get("temporal") or {}).get("periodos", []))
        if racha and any(not e["riego"] and temporal & set(e["periodos"]) for e in r["etapas"]):
            anio, dias = max(racha.items(), key=lambda kv: kv[1])
            rs.append(T("Rainfed crops in the rainy season faced dry spells of up to {dias} days ({anio}).").format(
                dias=dias, anio=anio))
    if r["criterios"]["water"] < 0.3:
        rs.append(T("High water demand for most of the year."))
    if r["criterios"]["income"] < 0.4:
        rs.append(T("Low direct market value: cover crops are not sold, their benefit is mainly for the soil."))
    return rs or [T("No major climate risk found in 2020-2025 for this rotation.")]


def information_gaps(r: dict, diag: dict | None, zona_info: dict | None, idioma: str = "en") -> list[str]:
    T = lambda s: tr(s, idioma)
    g = [T(GAP_HIPOTESIS)]
    if diag is not None and (diag.get("ndvi_interpolado_pct") or 0) > UMBRAL_NDVI_INTERPOLADO_PCT:
        g.append(T("NDVI partly interpolated: {pct:.0f}% of periods had no clear-sky MODIS composite.").format(
            pct=diag["ndvi_interpolado_pct"]))
    if zona_info:
        aviso = zona_info.get("aviso_es") if idioma == "es" else None
        aviso = aviso if isinstance(aviso, str) else zona_info.get("aviso")
        if isinstance(aviso, str) and aviso:
            g.append(aviso)
    if r["riego"]:
        g.append(T("Irrigation availability is assumed for this zone; confirm it for your plot."))
    if any(d.get("usa_climatologia") for d in r["backtest"]["anios"]):
        g.append(T("Cycles that run into 2026 use the 2020-2025 average for those periods in the 2025 backtest."))
    g.append(T("Satellite data describe the area around the zone point (rain and temperature from NASA POWER grid "
               "cells about 10-50 km across; NDVI from a ~2 km window), not your exact plot. Soil type, prices and "
               "costs are not included."))
    return g


def explicar(r: dict, actual: dict | None = None, diag: dict | None = None, zona_info: dict | None = None,
             n_total: int | None = None, promedios: dict | None = None, idioma: str = "en") -> dict:
    return {
        "why_suggested": why_suggested(r, actual, n_total or r["rango"], promedios, idioma),
        "evidence": evidence(r, idioma),
        "benefits": benefits(r, actual, idioma),
        "risks": risks(r, diag, idioma),
        "information_gaps": information_gaps(r, diag, zona_info, idioma),
        "disclaimer": tr(DISCLAIMER, idioma),
    }


def explicar_ranking(resultados: list[dict], diag: dict | None = None, zona_info: dict | None = None,
                     idioma: str = "en") -> list[dict]:
    """Agrega r['explicacion'] a cada rotación del ranking."""
    actual = next((r for r in resultados if r["es_actual"]), None)
    promedios = {c: float(pd.Series([r["criterios"][c] for r in resultados]).mean())
                 for c in ("climate", "water", "soil", "income")}
    for r in resultados:
        r["explicacion"] = explicar(r, actual, diag, zona_info, len(resultados), promedios, idioma)
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
    idioma = sys.argv[2] if len(sys.argv) > 2 else "en"
    zonas = datos.cargar_zonas()
    diag = I.diagnostico(P.cargar_serie_21d(), datos.cargar_clima_diario(), zona)
    lluvia, anio = R.cargar_lluvia_outlook(zona)
    res = explicar_ranking(R.rankear(zona, lluvia_outlook=lluvia, anio_outlook=anio), diag,
                           zonas.set_index("id").loc[zona].to_dict(), idioma)
    for r in res[:2] + [x for x in res[2:] if x["es_actual"]]:
        print(f"\n#{r['rango']} {_nr(r, idioma)}{' [CURRENT]' if r['es_actual'] else ''}")
        print(texto(r["explicacion"]))
