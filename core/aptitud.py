"""Aptitud climática difusa tipo EcoCrop de un cultivo en sus periodos de 21 días.

Para un cultivo sembrado en el periodo que contiene el día 1 de su mes de siembra y que dura
meses_a_periodos(ciclo_meses) periodos, se califican tres factores (0-1):
- temperature: promedio, sobre los periodos del ciclo, del trapecio temp_abs/temp_opt aplicado a la
  temperatura media del periodo ((tmax_media + tmin_media) / 2);
- rainfall: trapecio lluvia_abs/lluvia_opt aplicado a la lluvia acumulada del ciclo (con riego = 1);
- frost: 1 si el cultivo tolera helada o no hay heladas; cada día de helada en el ciclo resta 1/5.
Aptitud = el factor más bajo (ley del mínimo, como EcoCrop) y ese factor es el limitante.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import periodos as P

UMBRAL_OK = 0.6          # aptitud mínima para considerar que el cultivo "funcionó"
DIAS_HELADA_FALLA = 5    # días de helada en el ciclo que llevan el factor frost a 0
FACTORES = ("temperature", "rainfall", "frost")


def trapecio(x: float, abs_min: float, opt_min: float, opt_max: float, abs_max: float) -> float:
    """1 dentro del óptimo, 0 fuera del absoluto, lineal entre ambos."""
    if x is None or pd.isna(x):
        return np.nan
    if opt_min <= x <= opt_max:
        return 1.0
    if x <= abs_min or x >= abs_max:
        return 0.0
    if x < opt_min:
        return float((x - abs_min) / (opt_min - abs_min))
    return float((abs_max - x) / (abs_max - opt_max))


def periodos_etapa(periodo_siembra: int, n: int) -> list[tuple[int, int]]:
    """[(desfase_de_año, periodo), ...]; un ciclo que cruza el fin de año continúa en P01 (desfase 1)."""
    return [((periodo_siembra - 1 + i) // P.N_PERIODOS, (periodo_siembra - 1 + i) % P.N_PERIODOS + 1)
            for i in range(n)]


def periodos_de_cultivo(cultivo: dict, siembra_mes: int | None = None) -> list[tuple[int, int]]:
    mes = int(siembra_mes if siembra_mes is not None else cultivo["siembra_mes"])
    return periodos_etapa(P.mes_a_periodo(mes), P.meses_a_periodos(float(cultivo["ciclo_meses"])))


def contexto_clima(serie: pd.DataFrame, zona: str) -> dict:
    """Clima por (año, periodo) de una zona y su climatología, listos para consultar rápido."""
    s = serie[serie["zona"] == zona]
    if s.empty:
        raise ValueError(f"No data for zone '{zona}'")
    df = pd.DataFrame({"anio": s["anio"].astype(int), "periodo": s["periodo"].astype(int),
                       "tmedia": (s["tmax_media"] + s["tmin_media"]) / 2,
                       "precip_mm": s["precip_mm"], "dias_helada": s["dias_helada"]})
    clim = df.groupby("periodo")[["tmedia", "precip_mm", "dias_helada"]].mean()
    return {
        "zona": zona,
        "anios": sorted(df["anio"].unique().tolist()),
        "tabla": {(r.anio, r.periodo): (r.tmedia, r.precip_mm, r.dias_helada) for r in df.itertuples()},
        "clim": {int(p): tuple(v) for p, v in clim.iterrows()},
    }


def clima_de_etapa(ctx: dict, periodos: list[tuple[int, int]], anio: int | None = None,
                   lluvia: dict | pd.Series | None = None) -> pd.DataFrame:
    """Clima de los periodos de una etapa. anio=None -> climatología 2020-2025; anio=Y -> valores de
    ese año (y del siguiente si el ciclo cruza el fin de año; si no existen, climatología y se marca).
    lluvia: reemplazo opcional de la lluvia por periodo (escenario con pronóstico)."""
    filas = []
    for desfase, p in periodos:
        valores, de_clim = ctx["clim"][p], True
        if anio is not None:
            v = ctx["tabla"].get((anio + desfase, p))
            if v is not None and not any(pd.isna(x) for x in v):
                valores, de_clim = v, False
        tmedia, precip, helada = valores
        if lluvia is not None and p in lluvia:
            precip = float(lluvia[p])
        filas.append({"periodo": p, "anio": None if anio is None else anio + desfase, "tmedia": tmedia,
                      "precip_mm": precip, "dias_helada": helada, "climatologia": de_clim})
    return pd.DataFrame(filas)


def aptitud(cultivo: dict, clima_ciclo: pd.DataFrame, riego: bool) -> dict:
    """Aptitud 0-1 de un cultivo dado el clima de su ciclo, con el factor que más limitó."""
    puntos_temp = [trapecio(t, cultivo["temp_abs_min"], cultivo["temp_opt_min"],
                            cultivo["temp_opt_max"], cultivo["temp_abs_max"]) for t in clima_ciclo["tmedia"]]
    validos = [x for x in puntos_temp if not np.isnan(x)]
    f_temp = float(np.mean(validos)) if validos else np.nan
    lluvia_total = float(clima_ciclo["precip_mm"].sum(min_count=1))
    # Factor de lluvia "de temporal" (sin riego): se guarda siempre para explicar la dependencia del riego
    f_lluvia_temporal = trapecio(lluvia_total, cultivo["lluvia_abs_min"], cultivo["lluvia_opt_min"],
                                 cultivo["lluvia_opt_max"], cultivo["lluvia_abs_max"])
    f_lluvia = 1.0 if riego else f_lluvia_temporal
    heladas = float(clima_ciclo["dias_helada"].sum())
    f_helada = 1.0 if bool(cultivo["tolera_helada"]) else max(0.0, 1.0 - heladas / DIAS_HELADA_FALLA)

    factores = {"temperature": f_temp, "rainfall": f_lluvia, "frost": f_helada}
    definidos = {k: v for k, v in factores.items() if not pd.isna(v)}
    valor = min(definidos.values()) if definidos else np.nan
    limitante = min(definidos, key=definidos.get) if definidos and valor < 1 else None
    peor = int(np.nanargmin(puntos_temp)) if validos else None
    return {
        "aptitud": valor,
        "factores": factores,
        "limitante": limitante,
        "temp_media_c": float(clima_ciclo["tmedia"].mean()),
        "lluvia_mm": lluvia_total,
        "lluvia_opt_mm": (float(cultivo["lluvia_opt_min"]), float(cultivo["lluvia_opt_max"])),
        "temp_opt_c": (float(cultivo["temp_opt_min"]), float(cultivo["temp_opt_max"])),
        "factor_lluvia_temporal": f_lluvia_temporal,
        "dias_helada": heladas,
        "riego": bool(riego),
        "periodo_temp_mas_limitante": int(clima_ciclo["periodo"].iloc[peor]) if peor is not None else None,
        "usa_climatologia": bool(clima_ciclo["climatologia"].any()),
    }


def aptitud_cultivo(cultivo: dict, ctx: dict, riego: bool, siembra_mes: int | None = None,
                    anio: int | None = None, lluvia=None) -> dict:
    """Atajo: aptitud de un cultivo en una zona (climatología si anio=None, o un año concreto)."""
    periodos = periodos_de_cultivo(cultivo, siembra_mes)
    return aptitud(cultivo, clima_de_etapa(ctx, periodos, anio, lluvia), riego)
