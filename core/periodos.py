"""Calendario de 17 periodos fijos de 21 días por año y tabla integrada serie_21d.

Periodo k empieza el día 1 + 21*(k-1) del año; el periodo 17 absorbe el resto (29-30 días).
Así el periodo 8 de 2021 es comparable con el periodo 8 de 2024.

Generar data/processed/serie_21d.csv (regenera antes data/clean/):   python -m core.periodos
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

N_PERIODOS = 17
DIAS_PERIODO = 21
DIAS_POR_MES = 30.44
ANIO_REFERENCIA = 2023          # año no bisiesto para etiquetas genéricas (climatología)
UMBRAL_LLUVIA_MM = 1.0          # día con lluvia: >= 1 mm; día seco: < 1 mm
UMBRAL_HELADA_C = 2.0           # tmin <= 2 °C
UMBRAL_CALOR_C = 35.0           # tmax >= 35 °C
MAX_HUECO_NDVI_DIAS = 32        # no interpolar NDVI entre compuestos separados por más de esto

RAIZ = Path(__file__).resolve().parents[1]
RUTA_SERIE = RAIZ / "data" / "processed" / "serie_21d.csv"
MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

COLUMNAS_SERIE = [
    "zona", "anio", "periodo", "etiqueta", "fecha_inicio", "fecha_fin", "n_dias",
    "precip_mm", "precip_mm_21d", "dias_lluvia", "racha_seca_max",
    "tmax_media", "tmin_media", "tmin_min", "dias_helada", "dias_calor", "dias_con_clima",
    "ndvi", "ndvi_obs", "ndvi_interpolado",
]


# ---------------------------------------------------------------- calendario

def periodo_de_fecha(fecha):
    """Periodo (1-17) de una fecha (int) o de una Serie / índice de fechas (mismo tipo)."""
    f = pd.to_datetime(fecha)
    if isinstance(f, pd.Timestamp):
        return int(min((f.dayofyear - 1) // DIAS_PERIODO + 1, N_PERIODOS))
    doy = f.dt.dayofyear if isinstance(f, pd.Series) else f.dayofyear
    return np.minimum((doy - 1) // DIAS_PERIODO + 1, N_PERIODOS)


def _etiqueta(k: int, inicio: pd.Timestamp, fin: pd.Timestamp) -> str:
    return f"P{k:02d} ({MESES_EN[inicio.month - 1]} {inicio.day} – {MESES_EN[fin.month - 1]} {fin.day})"


def calendario(anio: int) -> pd.DataFrame:
    """Los 17 periodos de un año: periodo, fecha_inicio, fecha_fin, n_dias, etiqueta."""
    primero, ultimo = pd.Timestamp(anio, 1, 1), pd.Timestamp(anio, 12, 31)
    filas = []
    for k in range(1, N_PERIODOS + 1):
        inicio = primero + pd.Timedelta(days=DIAS_PERIODO * (k - 1))
        fin = ultimo if k == N_PERIODOS else inicio + pd.Timedelta(days=DIAS_PERIODO - 1)
        filas.append({"anio": anio, "periodo": k, "fecha_inicio": inicio, "fecha_fin": fin,
                      "n_dias": (fin - inicio).days + 1, "etiqueta": _etiqueta(k, inicio, fin)})
    return pd.DataFrame(filas)


def etiquetas(anio: int = ANIO_REFERENCIA) -> list[str]:
    """Etiquetas P01…P17 (año no bisiesto por defecto) para ejes y tablas."""
    return calendario(anio)["etiqueta"].tolist()


def mes_a_periodo(mes: int) -> int:
    """Periodo que contiene el día 1 del mes (igual en años bisiestos y no bisiestos)."""
    return periodo_de_fecha(pd.Timestamp(ANIO_REFERENCIA, mes, 1))


def meses_a_periodos(n_meses: float) -> int:
    """Duración en periodos de 21 días: round(n * 30.44 / 21), redondeo escolar, mínimo 1."""
    return max(1, int(np.floor(n_meses * DIAS_POR_MES / DIAS_PERIODO + 0.5)))


# ---------------------------------------------------------------- indicadores diarios -> periodo

def racha_seca_max(precip, umbral: float = UMBRAL_LLUVIA_MM) -> int:
    """Máximo de días consecutivos con lluvia < umbral (un día sin dato corta la racha)."""
    mejor = actual = 0
    for seco in (pd.Series(precip, dtype=float) < umbral):
        actual = actual + 1 if seco else 0
        mejor = max(mejor, actual)
    return mejor


def ndvi_diario(ndvi: pd.DataFrame, max_hueco: int = MAX_HUECO_NDVI_DIAS) -> pd.DataFrame:
    """NDVI diario por zona: quita calidad==3, interpola linealmente entre compuestos.

    No extrapola antes del primer ni después del último compuesto, y deja NaN en huecos de más de
    `max_hueco` días entre compuestos. Columnas: zona, fecha, ndvi, es_obs.
    """
    df = ndvi.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    if "calidad" in df:
        df = df[df["calidad"] != 3]
    df = df.dropna(subset=["ndvi"])
    partes = []
    for zona, d in df.groupby("zona"):
        obs = d.groupby("fecha")["ndvi"].mean().sort_index()
        dias = pd.date_range(obs.index.min(), obs.index.max(), freq="D")
        diario = obs.reindex(dias).interpolate(method="time", limit_area="inside")
        fecha_obs = pd.Series(obs.index, index=obs.index).reindex(dias)
        hueco = (fecha_obs.bfill() - fecha_obs.ffill()).dt.days
        diario[hueco > max_hueco] = np.nan
        partes.append(pd.DataFrame({"zona": zona, "fecha": dias, "ndvi": diario.to_numpy(),
                                    "es_obs": dias.isin(obs.index)}))
    if not partes:
        return pd.DataFrame({"zona": pd.Series(dtype=object), "fecha": pd.Series(dtype="datetime64[ns]"),
                             "ndvi": pd.Series(dtype=float), "es_obs": pd.Series(dtype=bool)})
    return pd.concat(partes, ignore_index=True)


def construir_serie_21d(clima: pd.DataFrame, ndvi: pd.DataFrame) -> pd.DataFrame:
    """Tabla integrada: una fila por zona x año x periodo (todas las combinaciones, aunque falten datos).

    precip_mm_21d = precip_mm normalizada a 21 días (solo cambia el periodo 17) para comparar periodos.
    ndvi = media del NDVI diario interpolado; ndvi_obs = compuestos reales (no nubosos) en el periodo.
    """
    c = clima.copy()
    c["fecha"] = pd.to_datetime(c["fecha"])
    c = c.sort_values(["zona", "fecha"])
    c["anio"] = c["fecha"].dt.year
    c["periodo"] = periodo_de_fecha(c["fecha"])
    c = c.merge(ndvi_diario(ndvi)[["zona", "fecha", "ndvi"]], on=["zona", "fecha"], how="left")
    c["lluvia"] = c["precip_mm"] >= UMBRAL_LLUVIA_MM
    c["helada"] = c["tmin_c"] <= UMBRAL_HELADA_C
    c["calor"] = c["tmax_c"] >= UMBRAL_CALOR_C

    claves = ["zona", "anio", "periodo"]
    agg = c.groupby(claves).agg(
        precip_mm=("precip_mm", lambda s: s.sum(min_count=1)),
        dias_lluvia=("lluvia", "sum"),
        racha_seca_max=("precip_mm", racha_seca_max),
        tmax_media=("tmax_c", "mean"),
        tmin_media=("tmin_c", "mean"),
        tmin_min=("tmin_c", "min"),
        dias_helada=("helada", "sum"),
        dias_calor=("calor", "sum"),
        dias_con_clima=("precip_mm", "count"),
        ndvi=("ndvi", "mean"),
    ).reset_index()

    # Compuestos reales de NDVI por periodo (mismo filtro que ndvi_diario)
    comp = ndvi.copy()
    comp["fecha"] = pd.to_datetime(comp["fecha"])
    if "calidad" in comp:
        comp = comp[comp["calidad"] != 3]
    comp = comp.dropna(subset=["ndvi"])
    comp["anio"] = comp["fecha"].dt.year
    comp["periodo"] = periodo_de_fecha(comp["fecha"])
    obs = comp.groupby(claves).size().rename("ndvi_obs").reset_index()
    obs = obs.astype({"zona": object, "anio": "int64", "periodo": "int64"})  # también si está vacío

    # Rejilla completa zona x año x periodo, para que los faltantes queden explícitos (NaN)
    anios = sorted(c["anio"].unique())
    cal = pd.concat([calendario(a) for a in anios], ignore_index=True)
    rejilla = pd.DataFrame({"zona": sorted(c["zona"].unique())}).merge(cal, how="cross")
    serie = rejilla.merge(agg, on=claves, how="left").merge(obs, on=claves, how="left")
    serie["ndvi_obs"] = serie["ndvi_obs"].fillna(0).astype(int)
    serie["ndvi_interpolado"] = serie["ndvi_obs"] == 0
    serie["precip_mm_21d"] = serie["precip_mm"] * DIAS_PERIODO / serie["n_dias"]
    for col in ("dias_lluvia", "racha_seca_max", "dias_helada", "dias_calor", "dias_con_clima"):
        serie[col] = serie[col].fillna(0).astype(int)
    return serie[COLUMNAS_SERIE].sort_values(claves).reset_index(drop=True)


# ---------------------------------------------------------------- archivo data/processed/

def generar_serie_21d(ruta: Path = RUTA_SERIE) -> pd.DataFrame:
    from core import datos  # import local: periodos no depende de datos para sus funciones puras
    serie = construir_serie_21d(datos.cargar_clima_diario(), datos.cargar_ndvi())
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    serie.to_csv(ruta, index=False, date_format="%Y-%m-%d", float_format="%.4f")
    return serie


def cargar_serie_21d(ruta: Path = RUTA_SERIE, regenerar_si_falta: bool = True) -> pd.DataFrame:
    if not Path(ruta).exists():
        if not regenerar_si_falta:
            raise FileNotFoundError(f"Falta {ruta}. Ejecuta: python -m core.periodos")
        return generar_serie_21d(ruta)
    return pd.read_csv(ruta, parse_dates=["fecha_inicio", "fecha_fin"])


if __name__ == "__main__":
    from core import datos
    print(datos.resumen_texto(datos.preparar_datos_limpios()))
    s = generar_serie_21d()
    con_ndvi = s["ndvi"].notna()
    print(f"\n== SERIE_21D: {len(s)} filas = {s['zona'].nunique()} zonas x {s['anio'].nunique()} anios x "
          f"{s['periodo'].nunique()} periodos -> {RUTA_SERIE.relative_to(RAIZ)}")
    print(f"   NDVI con dato: {con_ndvi.sum()}/{len(s)} periodos | de esos, sin compuesto real "
          f"(100% interpolado): {(con_ndvi & s['ndvi_interpolado']).sum()}")
    sin_ndvi = s[~con_ndvi].groupby("zona")["fecha_inicio"].min()
    for zona, desde in sin_ndvi.items():
        print(f"   {zona}: sin NDVI desde {desde.date()} (No data)")
