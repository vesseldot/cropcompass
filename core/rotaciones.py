"""Motor de rotaciones: puntaje explicable (suma ponderada de 4 criterios 0-1) + backtesting por año.

Criterios (0-1, más alto = mejor):
- climate: aptitud climática promedio de las etapas (core.aptitud, climatología 2020-2025).
- water:   1 - demanda de agua del año = Σ agua_relativa × periodos ocupados / 17. Ponderar por tiempo hace
           que agregar un cultivo en secas cuente como MÁS agua (con un promedio simple contaría como menos).
- soil:    promedio de: fracción de etapas que fijan nitrógeno; cobertura del año (Σ cubre_suelo × periodos / 17);
           y fracción de los periodos de suelo desnudo de la zona (diagnóstico NDVI) que la rotación ocupa
           (si la zona no tiene periodos desnudos, esta parte no aplica y no se usa).
- income:  promedio de mercado_local de los cultivos de la rotación.
Puntaje (0-100) = Σ peso_normalizado × criterio × 100.

Backtesting: la aptitud se recalcula con el clima de CADA año; un año "funcionó" si TODOS los cultivos
de la rotación tuvieron aptitud >= 0.6. Los años fallidos se reportan con cultivo y factor limitante y
el tipo de año (dry / normal / wet).

Ver el ranking por zona:   python -m core.rotaciones
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import aptitud as A
from core import indicadores as I
from core import periodos as P

CRITERIOS = ("climate", "water", "soil", "income")
PESOS_DEFECTO = {"climate": 1.0, "water": 1.0, "soil": 1.0, "income": 1.0}


def normalizar_pesos(pesos: dict | None) -> dict:
    """Pesos >= 0 que suman 1. Si todos son 0 (o no hay), pesos iguales."""
    p = {c: max(0.0, float((pesos or {}).get(c, 0.0))) for c in CRITERIOS}
    total = sum(p.values())
    if total == 0:
        return {c: 1 / len(CRITERIOS) for c in CRITERIOS}
    return {c: v / total for c, v in p.items()}


def etapas_de_rotacion(rot: dict, cultivos: dict[str, dict]) -> list[dict]:
    etapas = []
    for e in rot["etapas"]:
        c = cultivos[e["cultivo"]]
        periodos = A.periodos_de_cultivo(c, e.get("siembra_mes"))
        etapas.append({"cultivo_id": e["cultivo"], "cultivo": c, "periodos": periodos,
                       "siembra_mes": int(e.get("siembra_mes", c["siembra_mes"]))})
    return etapas


def periodos_ocupados(etapas: list[dict]) -> set[int]:
    return {p for e in etapas for _, p in e["periodos"]}


# ---------------------------------------------------------------- criterios

def criterio_agua(etapas: list[dict]) -> float:
    demanda = sum(float(e["cultivo"]["agua_relativa"]) * len(e["periodos"]) for e in etapas) / P.N_PERIODOS
    return float(1 - min(1.0, demanda))


def criterio_ingreso(etapas: list[dict]) -> float:
    return float(np.mean([float(e["cultivo"]["mercado_local"]) for e in etapas]))


def criterio_suelo(etapas: list[dict], desnudos: list[int]) -> tuple[float, dict]:
    partes = {
        "nitrogen_fixing_share": float(np.mean([bool(e["cultivo"]["fija_nitrogeno"]) for e in etapas])),
        "year_round_cover": float(min(1.0, sum(float(e["cultivo"]["cubre_suelo"]) * len(e["periodos"])
                                               for e in etapas) / P.N_PERIODOS)),
    }
    if desnudos:
        partes["bare_periods_covered"] = len(set(desnudos) & periodos_ocupados(etapas)) / len(desnudos)
    return float(np.mean(list(partes.values()))), partes


def evaluar_clima(etapas: list[dict], ctx: dict, riego: bool, anio: int | None = None,
                  lluvia=None) -> list[dict]:
    """Aptitud de cada etapa (climatología si anio=None)."""
    return [A.aptitud(e["cultivo"], A.clima_de_etapa(ctx, e["periodos"], anio, lluvia), riego) for e in etapas]


def backtest(etapas: list[dict], ctx: dict, riego: bool, tipos_anio: dict[int, str],
             umbral: float = A.UMBRAL_OK) -> dict:
    anios = []
    for a in ctx["anios"]:
        res = evaluar_clima(etapas, ctx, riego, anio=a)
        apts = [r["aptitud"] for r in res]
        peor = int(np.nanargmin(apts)) if not all(pd.isna(apts)) else 0
        ok = all(not pd.isna(x) and x >= umbral for x in apts)
        anios.append({
            "anio": a, "tipo_anio": tipos_anio.get(a, "unknown"), "ok": ok,
            "aptitud_min": float(apts[peor]), "aptitud_media": float(np.nanmean(apts)),
            "cultivo_limitante": None if ok else etapas[peor]["cultivo_id"],
            "factor_limitante": None if ok else res[peor]["limitante"],
            "usa_climatologia": any(r["usa_climatologia"] for r in res),
        })
    return {"anios_ok": sum(d["ok"] for d in anios), "anios_total": len(anios), "umbral": umbral,
            "anios": anios, "fallidos": [d for d in anios if not d["ok"]]}


# ---------------------------------------------------------------- ranking

def _cargar_defectos(serie, cultivos, rotaciones, zonas):
    from core import datos
    if serie is None:
        serie = P.cargar_serie_21d()
    if cultivos is None:
        cultivos = datos.cargar_cultivos()
    if rotaciones is None:
        rotaciones = datos.cargar_rotaciones()
    if zonas is None:
        zonas = datos.cargar_zonas()
    return serie, cultivos, rotaciones, zonas


def rankear(zona: str, pesos: dict | None = None, serie: pd.DataFrame | None = None,
            cultivos: pd.DataFrame | None = None, rotaciones: list[dict] | None = None,
            zonas: pd.DataFrame | None = None, cultivo_actual: str | None = None, riego: bool | None = None,
            umbral_ndvi: float = I.UMBRAL_NDVI_DESNUDO, umbral_ok: float = A.UMBRAL_OK,
            lluvia_outlook: pd.Series | None = None, anio_outlook: int | None = None) -> list[dict]:
    """Rotaciones candidatas de una zona, ordenadas por puntaje, con desglose y backtesting.

    cultivo_actual / riego: si son None se toman de zonas.json. lluvia_outlook: lluvia pronosticada
    (mm reales por periodo, índice 1-17) para el escenario del próximo año (temperaturas = climatología).
    """
    serie, cultivos, rotaciones, zonas = _cargar_defectos(serie, cultivos, rotaciones, zonas)
    info = zonas.set_index("id").loc[zona]
    if cultivo_actual is None:
        cultivo_actual = list(info["cultivos_actuales"])[0]
    if riego is None:
        riego = bool(info["riego"])
    cultivos_d = {c["id"]: c for c in cultivos.to_dict("records")}
    pesos_n = normalizar_pesos(pesos if pesos is not None else PESOS_DEFECTO)

    ctx = A.contexto_clima(serie, zona)
    clim = I.climatologia(serie, zona)
    desnudos = I.periodos_suelo_desnudo(clim, umbral_ndvi)
    tipos = I.clasificar_anios(I.lluvia_anual(serie, zona))

    resultados = []
    for rot in rotaciones:
        requiere = rot.get("requiere_actual")
        if requiere and cultivo_actual not in requiere:
            continue
        etapas = etapas_de_rotacion(rot, cultivos_d)
        apt = evaluar_clima(etapas, ctx, riego)
        suelo, suelo_partes = criterio_suelo(etapas, desnudos)
        criterios = {"climate": float(np.nanmean([r["aptitud"] for r in apt])),
                     "water": criterio_agua(etapas), "soil": suelo, "income": criterio_ingreso(etapas)}
        contrib = {c: 100 * pesos_n[c] * (0.0 if pd.isna(v) else v) for c, v in criterios.items()}
        outlook = None
        if lluvia_outlook is not None:
            res_o = evaluar_clima(etapas, ctx, riego, lluvia=lluvia_outlook)
            apts_o = [r["aptitud"] for r in res_o]
            outlook = {"anio": anio_outlook, "aptitud_min": float(np.nanmin(apts_o)),
                       "ok": all(x >= umbral_ok for x in apts_o),
                       "etapas": [{"cultivo_id": e["cultivo_id"], **r} for e, r in zip(etapas, res_o)]}
        ocupados = periodos_ocupados(etapas)
        resultados.append({
            "id": rot["id"], "nombre": rot["nombre"], "zona": zona,
            "es_actual": cultivo_actual in rot.get("actual_para", []),
            "puntaje": float(sum(contrib.values())),
            "criterios": criterios, "contribuciones": contrib, "pesos": pesos_n,
            "suelo_detalle": suelo_partes, "riego": riego,
            "etapas": [{
                "cultivo_id": e["cultivo_id"], "cultivo": e["cultivo"].get("nombre", e["cultivo_id"]),
                "siembra_mes": e["siembra_mes"], "periodos": [p for _, p in e["periodos"]],
                "inicio": P.etiquetas()[e["periodos"][0][1] - 1], "fin": P.etiquetas()[e["periodos"][-1][1] - 1],
                **r} for e, r in zip(etapas, apt)],
            "periodos_ocupados": sorted(ocupados),
            "desnudos_zona": desnudos, "desnudos_cubiertos": sorted(set(desnudos) & ocupados),
            "backtest": backtest(etapas, ctx, riego, tipos, umbral_ok),
            "outlook": outlook,
        })
    resultados.sort(key=lambda r: (-r["puntaje"], not r["es_actual"]))
    for i, r in enumerate(resultados, 1):
        r["rango"] = i
    return resultados


def cargar_lluvia_outlook(zona: str) -> tuple[pd.Series | None, int | None]:
    """Lluvia pronosticada (mejor modelo) en mm reales por periodo para el escenario del próximo año.
    Devuelve (None, None) si aún no existen los pronósticos (no se regeneran aquí)."""
    from core import pronostico as F
    try:
        _, prono, _ = F.cargar_resultados(regenerar_si_falta=False)
    except FileNotFoundError:
        return None, None
    g = prono[(prono["zona"] == zona) & (prono["variable"] == "precip_mm_21d") & prono["es_mejor"]]
    if g.empty:
        return None, None
    anio = int(g["anio"].iloc[0])
    n_dias = P.calendario(anio).set_index("periodo")["n_dias"]
    mm = g.set_index("periodo")["yhat"] * n_dias / P.DIAS_PERIODO   # precip_mm_21d -> mm reales (P17)
    return mm, anio


def resumen_texto(resultados: list[dict]) -> str:
    lineas = []
    for r in resultados:
        bt = r["backtest"]
        fallos = ", ".join(f"{d['anio']} ({d['tipo_anio']}: {d['cultivo_limitante']}/{d['factor_limitante']})"
                           for d in bt["fallidos"]) or "-"
        c = r["criterios"]
        lineas.append(f"  {r['rango']}. {'[CURRENT] ' if r['es_actual'] else ''}{r['nombre']}: {r['puntaje']:.0f}/100"
                      f" | climate {c['climate']:.2f} water {c['water']:.2f} soil {c['soil']:.2f} income {c['income']:.2f}"
                      f" | worked {bt['anios_ok']}/{bt['anios_total']} yrs | failed: {fallos}")
    return "\n".join(lineas)


if __name__ == "__main__":
    from core import datos
    zonas = datos.cargar_zonas()
    for z in zonas["id"]:
        lluvia, anio = cargar_lluvia_outlook(z)
        res = rankear(z, lluvia_outlook=lluvia, anio_outlook=anio)
        print(f"== {z.upper()} (irrigated: {res[0]['riego']}, bare periods: {res[0]['desnudos_zona']}, equal weights)")
        print(resumen_texto(res))
        print(f"  -- same zone, NOT irrigated:")
        print(resumen_texto(rankear(z, riego=False)))
