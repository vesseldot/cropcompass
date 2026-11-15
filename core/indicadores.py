"""Indicadores agroclimáticos y de NDVI por zona (diagnóstico), a partir de serie_21d.

Funciones puras: reciben DataFrames y devuelven DataFrames / dicts. Umbrales configurables.
Generar data/processed/diagnostico.json e imprimir el diagnóstico:   python -m core.indicadores
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core import periodos as P

UMBRAL_NDVI_DESNUDO = 0.30   # NDVI promedio del periodo < umbral -> suelo desnudo
UMBRAL_TEMPORAL_MM = 35.0    # lluvia promedio > umbral (mm por 21 días) -> periodo del temporal
UMBRAL_CALOR_DIAS = 3.0      # días con tmax >= 35 °C promedio por periodo >= umbral -> riesgo de calor
TIPOS_ANIO = ["dry", "normal", "wet"]  # terciles de lluvia anual (texto visible en la app: inglés)
RUTA_DIAGNOSTICO = P.RAIZ / "data" / "processed" / "diagnostico.json"


def climatologia(serie: pd.DataFrame, zona: str) -> pd.DataFrame:
    """Promedio y desviación estándar 2020-2025 por periodo (17 filas, aunque falten datos)."""
    g = serie[serie["zona"] == zona].groupby("periodo")
    clim = pd.DataFrame({
        "precip_media": g["precip_mm_21d"].mean(),
        "precip_std": g["precip_mm_21d"].std(),
        "tmax_media": g["tmax_media"].mean(),
        "tmax_std": g["tmax_media"].std(),
        "tmin_media": g["tmin_media"].mean(),
        "tmin_std": g["tmin_media"].std(),
        "ndvi_media": g["ndvi"].mean(),
        "ndvi_std": g["ndvi"].std(),
        "dias_helada_media": g["dias_helada"].mean(),
        "dias_calor_media": g["dias_calor"].mean(),
        "ndvi_obs_total": g["ndvi_obs"].sum(),
        "anios_con_ndvi": g["ndvi"].count(),
    }).reindex(range(1, P.N_PERIODOS + 1)).rename_axis("periodo").reset_index()
    clim.insert(1, "etiqueta", P.etiquetas())
    return clim


def periodos_suelo_desnudo(clim: pd.DataFrame, umbral: float = UMBRAL_NDVI_DESNUDO) -> list[int]:
    return clim.loc[clim["ndvi_media"] < umbral, "periodo"].tolist()


def temporal(clim: pd.DataFrame, umbral: float = UMBRAL_TEMPORAL_MM) -> dict | None:
    """Temporal (temporada de lluvias): del primer al último periodo con lluvia promedio > umbral."""
    lluviosos = clim.loc[clim["precip_media"] > umbral, "periodo"].tolist()
    if not lluviosos:
        return None
    return {"inicio": lluviosos[0], "fin": lluviosos[-1],
            "periodos": list(range(lluviosos[0], lluviosos[-1] + 1))}


def periodos_helada(clim: pd.DataFrame) -> list[int]:
    return clim.loc[clim["dias_helada_media"] > 0, "periodo"].tolist()


def periodos_calor(clim: pd.DataFrame, umbral: float = UMBRAL_CALOR_DIAS) -> list[int]:
    return clim.loc[clim["dias_calor_media"] >= umbral, "periodo"].tolist()


def lluvia_anual(serie: pd.DataFrame, zona: str) -> pd.Series:
    s = serie[serie["zona"] == zona]
    return s.groupby("anio")["precip_mm"].sum(min_count=1)


def clasificar_anios(lluvia: pd.Series) -> dict[int, str]:
    """Cada año -> dry / normal / wet por terciles de su lluvia anual (empates: por orden)."""
    lluvia = lluvia.dropna()
    if len(lluvia) < 3:
        return {int(a): "unknown" for a in lluvia.index}
    tipos = pd.qcut(lluvia.rank(method="first"), 3, labels=TIPOS_ANIO)
    return {int(a): str(t) for a, t in tipos.items()}


def racha_seca_temporal(clima_diario: pd.DataFrame, zona: str, inicio: int, fin: int) -> dict[int, int]:
    """Máximo de días seguidos con < 1 mm dentro del temporal de cada año (con datos diarios,
    para no partir la racha en los bordes de los periodos)."""
    d = clima_diario[clima_diario["zona"] == zona].copy()
    d["fecha"] = pd.to_datetime(d["fecha"])
    d = d.sort_values("fecha")
    per = P.periodo_de_fecha(d["fecha"])
    d = d[(per >= inicio) & (per <= fin)]
    return {int(a): P.racha_seca_max(g["precip_mm"]) for a, g in d.groupby(d["fecha"].dt.year)}


def ventanas_libres(clim: pd.DataFrame, desnudos: list[int], helada: list[int],
                    umbral_lluvia: float = UMBRAL_TEMPORAL_MM) -> list[dict]:
    """Periodos con suelo desnudo que tienen lluvia o no tienen helada: candidatos a cultivo de cobertura.
    Si no hay lluvia suficiente, la ventana requiere riego."""
    c = clim.set_index("periodo")
    out = []
    for p in desnudos:
        con_lluvia = bool(c.at[p, "precip_media"] > umbral_lluvia)
        sin_helada = p not in helada
        if con_lluvia or sin_helada:
            out.append({"periodo": int(p), "etiqueta": c.at[p, "etiqueta"],
                        "ndvi": round(float(c.at[p, "ndvi_media"]), 3),
                        "precip_mm": round(float(c.at[p, "precip_media"]), 1),
                        "con_lluvia": con_lluvia, "sin_helada": sin_helada, "requiere_riego": not con_lluvia})
    return out


def diagnostico(serie: pd.DataFrame, clima_diario: pd.DataFrame, zona: str,
                umbral_ndvi: float = UMBRAL_NDVI_DESNUDO, umbral_temporal: float = UMBRAL_TEMPORAL_MM,
                umbral_calor: float = UMBRAL_CALOR_DIAS) -> dict:
    """Diagnóstico completo de una zona. Las listas son números de periodo (1-17); 'etiquetas' los nombra."""
    clim = climatologia(serie, zona)
    desnudos = periodos_suelo_desnudo(clim, umbral_ndvi)
    temp = temporal(clim, umbral_temporal)
    helada = periodos_helada(clim)
    anual = lluvia_anual(serie, zona)
    s = serie[serie["zona"] == zona]
    con_ndvi = s["ndvi"].notna()
    return {
        "zona": zona,
        "umbrales": {"ndvi_desnudo": umbral_ndvi, "temporal_mm_21d": umbral_temporal, "calor_dias": umbral_calor},
        "etiquetas": {int(p): e for p, e in zip(clim["periodo"], clim["etiqueta"])},
        "climatologia": clim,
        "suelo_desnudo": desnudos,
        "temporal": temp,
        "helada": helada,
        "calor": periodos_calor(clim, umbral_calor),
        "racha_seca_temporal": racha_seca_temporal(clima_diario, zona, temp["inicio"], temp["fin"]) if temp else {},
        "lluvia_anual": {int(a): round(float(v), 1) for a, v in anual.items()},
        "tipo_anio": clasificar_anios(anual),
        "ventanas_libres": ventanas_libres(clim, desnudos, helada, umbral_temporal),
        "ndvi_interpolado_pct": round(100 * float(s.loc[con_ndvi, "ndvi_interpolado"].mean()), 1) if con_ndvi.any() else None,
        "periodos_sin_ndvi": int((~con_ndvi).sum()),
    }


def diagnostico_todas(serie: pd.DataFrame, clima_diario: pd.DataFrame, **umbrales) -> dict[str, dict]:
    return {z: diagnostico(serie, clima_diario, z, **umbrales) for z in sorted(serie["zona"].unique())}


# ---------------------------------------------------------------- salida

def a_json(diags: dict[str, dict]) -> dict:
    """Versión serializable (la climatología pasa a lista de registros, redondeada)."""
    out = {}
    for zona, d in diags.items():
        d = dict(d)
        d["climatologia"] = d["climatologia"].round(3).astype(object).where(d["climatologia"].notna(), None).to_dict("records")
        d["etiquetas"] = {str(k): v for k, v in d["etiquetas"].items()}
        d["racha_seca_temporal"] = {str(k): v for k, v in d["racha_seca_temporal"].items()}
        d["lluvia_anual"] = {str(k): v for k, v in d["lluvia_anual"].items()}
        d["tipo_anio"] = {str(k): v for k, v in d["tipo_anio"].items()}
        out[zona] = d
    return out


def resumen_texto(diags: dict[str, dict]) -> str:
    def nombres(d, ps):
        return ", ".join(d["etiquetas"][p] for p in ps) if ps else "none"

    lineas = []
    for zona, d in diags.items():
        t = d["temporal"]
        lineas += [
            f"== {zona.upper()}",
            f"   rainy season : {d['etiquetas'][t['inicio']] + ' to ' + d['etiquetas'][t['fin']] if t else 'none'}",
            f"   bare soil    : {len(d['suelo_desnudo'])} periods (NDVI < {d['umbrales']['ndvi_desnudo']}): {nombres(d, d['suelo_desnudo'])}",
            f"   frost risk   : {nombres(d, d['helada'])}",
            f"   heat risk    : {nombres(d, d['calor'])}",
            f"   dry spell in rainy season (days): {d['racha_seca_temporal']}",
            f"   year type    : " + ", ".join(f"{a} {t_} ({d['lluvia_anual'][a]:.0f} mm)" for a, t_ in d["tipo_anio"].items()),
            f"   free windows : " + (", ".join(f"P{v['periodo']:02d}{' (needs irrigation)' if v['requiere_riego'] else ' (rain)'}"
                                           for v in d["ventanas_libres"]) or "none"),
            f"   NDVI: {d['ndvi_interpolado_pct']}% of periods fully interpolated | periods without NDVI: {d['periodos_sin_ndvi']}",
        ]
    return "\n".join(lineas)


def generar_diagnostico(ruta: Path = RUTA_DIAGNOSTICO, **umbrales) -> dict[str, dict]:
    from core import datos
    diags = diagnostico_todas(P.cargar_serie_21d(), datos.cargar_clima_diario(), **umbrales)
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(a_json(diags), indent=2, ensure_ascii=False), encoding="utf-8")
    return diags


if __name__ == "__main__":
    print(resumen_texto(generar_diagnostico()))
