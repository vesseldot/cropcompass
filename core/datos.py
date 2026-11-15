"""Carga y validación de los datos del proyecto (contrato de datos de CLAUDE.md).

Flujo:
    data/raw/  --construir_*()-->  DataFrame con el contrato  --validar()-->  data/clean/*.csv
    data/config/*.json  --cargar_*()-->  zonas / cultivos / rotaciones  --validar_config()

Regenerar data/clean/ e imprimir el reporte:   python -m core.datos
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DIR_DATA = RAIZ / "data"
DIR_RAW = DIR_DATA / "raw"
DIR_CLEAN = DIR_DATA / "clean"
DIR_CONFIG = DIR_DATA / "config"
DIR_NDVI_ORNL = DIR_RAW / "ndvi_modis_ornl"

# Valores "sin dato": -999 (NASA POWER), -3000 (MODIS NDVI), -9999 (otros productos)
SENTINELAS = [-999, -9999, -3000]

COLS_REQUERIDAS = {
    "clima": ["zona", "fecha", "precip_mm", "tmax_c", "tmin_c"],
    "ndvi": ["zona", "fecha", "ndvi"],
}
# Rangos físicos aceptados (None = sin límite). Fuera de rango -> NaN y se reporta.
RANGOS = {
    "precip_mm": (0, None),
    "tmax_c": (-10, 50),
    "tmin_c": (-20, 40),
    "ndvi": (0, 1),
}

BANDA_NDVI = "250m_16_days_NDVI"
BANDA_CALIDAD = "250m_16_days_pixel_reliability"  # -1 sin dato, 0 bueno, 1 marginal, 2 nieve, 3 nube
CALIDAD_EXCLUIDA = [-1, 2, 3]
PASO_NDVI_DIAS = 16
PARES_CULTIVO = ("temp_abs", "temp_opt", "lluvia_abs", "lluvia_opt")


# ---------------------------------------------------------------- configuración (JSON)

def leer_json(ruta: Path | str) -> dict:
    """Lee JSON en UTF-8 y, si falla, en cp1252 (resumen.json del equipo viene así)."""
    crudo = Path(ruta).read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return json.loads(crudo.decode(codificacion))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo decodificar {ruta} como UTF-8 ni cp1252")


def cargar_zonas(ruta: Path | str = DIR_CONFIG / "zonas.json") -> pd.DataFrame:
    zonas = pd.DataFrame(leer_json(ruta)["zonas"])
    faltan = {"id", "nombre", "lat", "lon", "riego"} - set(zonas.columns)
    if faltan:
        raise ValueError(f"zonas.json: faltan campos {sorted(faltan)}")
    return zonas


def cargar_cultivos(ruta: Path | str = DIR_CONFIG / "cultivos.json") -> pd.DataFrame:
    """Una fila por cultivo; los rangos [min, max] se aplanan a columnas *_min / *_max."""
    filas = []
    for c in leer_json(ruta)["cultivos"]:
        fila = {k: v for k, v in c.items() if k not in PARES_CULTIVO}
        for par in PARES_CULTIVO:
            fila[f"{par}_min"], fila[f"{par}_max"] = c.get(par, [np.nan, np.nan])
        filas.append(fila)
    return pd.DataFrame(filas)


def cargar_rotaciones(ruta: Path | str = DIR_CONFIG / "rotaciones.json") -> list[dict]:
    return leer_json(ruta)["rotaciones"]


def validar_config(zonas: pd.DataFrame, cultivos: pd.DataFrame, rotaciones: list[dict]) -> list[str]:
    """Revisa coherencia entre los tres archivos de configuración. Lista vacía = todo bien."""
    problemas = []
    ids = set(cultivos["id"])
    if cultivos["id"].duplicated().any():
        problemas.append("cultivos: ids duplicados")
    for c in cultivos.itertuples():
        for var in ("temp", "lluvia"):
            a0, o0, o1, a1 = (getattr(c, f"{var}_{t}") for t in ("abs_min", "opt_min", "opt_max", "abs_max"))
            if not (a0 <= o0 <= o1 <= a1):
                problemas.append(f"cultivo {c.id}: se requiere {var}_abs_min <= opt_min <= opt_max <= abs_max")
        for campo in ("agua_relativa", "cubre_suelo", "mercado_local"):
            if not 0 <= getattr(c, campo) <= 1:
                problemas.append(f"cultivo {c.id}: {campo} fuera de 0-1")
        if not c.ciclo_meses > 0:
            problemas.append(f"cultivo {c.id}: ciclo_meses debe ser > 0")
        if not 1 <= c.siembra_mes <= 12:
            problemas.append(f"cultivo {c.id}: siembra_mes fuera de 1-12")
    actuales_cubiertos = set()
    for r in rotaciones:
        actuales_cubiertos |= set(r.get("actual_para", []))
        for c in r.get("requiere_actual", []):
            if c not in ids:
                problemas.append(f"rotación {r['id']}: requiere_actual con cultivo desconocido '{c}'")
        if not r.get("etapas"):
            problemas.append(f"rotación {r['id']}: sin etapas")
        for e in r.get("etapas", []):
            if e["cultivo"] not in ids:
                problemas.append(f"rotación {r['id']}: cultivo desconocido '{e['cultivo']}'")
            if "siembra_mes" in e and not 1 <= e["siembra_mes"] <= 12:
                problemas.append(f"rotación {r['id']}: siembra_mes fuera de 1-12")
    for z in zonas.itertuples():
        actuales = getattr(z, "cultivos_actuales", None)
        for c in actuales if isinstance(actuales, list) else []:
            if c not in ids:
                problemas.append(f"zona {z.id}: cultivo actual desconocido '{c}'")
            elif c not in actuales_cubiertos:
                problemas.append(f"zona {z.id}: ninguna rotación representa el cultivo actual '{c}'")
    return problemas


# ---------------------------------------------------------------- clima diario (NASA POWER)

def leer_power_csv(ruta: Path | str) -> pd.DataFrame:
    """Lee un CSV de NASA POWER (con o sin bloque -BEGIN/END HEADER-) y agrega columna 'fecha'."""
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    saltar = next((i + 1 for i, l in enumerate(lineas) if l.strip().startswith("-END HEADER-")), 0)
    df = pd.read_csv(ruta, skiprows=saltar)
    if "date" in df.columns:
        df["fecha"] = pd.to_datetime(df["date"])
    elif {"YEAR", "MO", "DY"} <= set(df.columns):
        df["fecha"] = pd.to_datetime(dict(year=df.YEAR, month=df.MO, day=df.DY))
    elif {"YEAR", "DOY"} <= set(df.columns):
        df["fecha"] = pd.to_datetime(df.YEAR.astype(str) + df.DOY.astype(str).str.zfill(3), format="%Y%j")
    else:
        raise ValueError(f"{ruta}: no encuentro columnas de fecha (date | YEAR,MO,DY | YEAR,DOY)")
    return df


def mapear_power(crudo: pd.DataFrame, zona: str) -> pd.DataFrame:
    """Columnas de POWER -> contrato. Lluvia = IMERG; si IMERG falta, PRECTOTCORR (precip_fuente)."""
    df = crudo.replace(SENTINELAS, np.nan)
    vacia = pd.Series(np.nan, index=df.index)
    imerg = df["IMERG_PRECTOT"] if "IMERG_PRECTOT" in df else vacia
    power = df["PRECTOTCORR"] if "PRECTOTCORR" in df else vacia
    fuente = pd.Series(pd.NA, index=df.index, dtype="string")
    fuente[power.notna()] = "POWER"
    fuente[imerg.notna()] = "IMERG"
    return pd.DataFrame({
        "zona": zona,
        "fecha": df["fecha"],
        "precip_mm": imerg.fillna(power),
        "precip_fuente": fuente,
        "precip_power_mm": power,
        "tmax_c": df["T2M_MAX"],
        "tmin_c": df["T2M_MIN"],
    })


def construir_clima_diario(zonas: pd.DataFrame, raiz: Path = RAIZ) -> pd.DataFrame:
    partes = [mapear_power(leer_power_csv(raiz / z.archivo_power), z.id) for z in zonas.itertuples()]
    return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------- NDVI (MODIS MOD13Q1 vía ORNL)

def leer_ornl(dir_ornl: Path | str, zona: str, banda: str) -> pd.DataFrame:
    """Une los JSON crudos de la API ORNL de una zona y banda: una fila por fecha x píxel."""
    filas = []
    for archivo in sorted(Path(dir_ornl).glob(f"{zona}__{banda}__*.json")):
        d = leer_json(archivo)
        try:
            escala = float(d.get("scale"))
        except (TypeError, ValueError):
            escala = 1.0
        for s in d.get("subset", []):
            filas += [(s["calendar_date"], i, v, escala) for i, v in enumerate(s["data"])]
    df = pd.DataFrame(filas, columns=["fecha", "pixel", "valor", "escala"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.drop_duplicates(["fecha", "pixel"])


def agregar_ndvi_pixeles(ndvi_px: pd.DataFrame, calidad_px: pd.DataFrame, zona: str) -> pd.DataFrame:
    """Resume la ventana de píxeles a un valor por compuesto de 16 días.

    ndvi    = mediana de los píxeles útiles (sin nube/nieve/relleno), ya escalado a 0-1.
    calidad = moda de pixel_reliability de la ventana (0 bueno ... 3 nube); NaN si no hay banda.
    La fecha es la de inicio del compuesto (calendar_date de MOD13Q1).
    """
    px = ndvi_px.merge(calidad_px[["fecha", "pixel", "valor"]], on=["fecha", "pixel"],
                       how="left", suffixes=("", "_cal"))
    valor = px["valor"].where(~px["valor"].isin(SENTINELAS))
    px["ndvi"] = valor * px["escala"]
    px["cal"] = px["valor_cal"].where(px["valor_cal"] != -1)
    px["ndvi_util"] = px["ndvi"].where(~px["valor_cal"].isin(CALIDAD_EXCLUIDA))
    g = px.groupby("fecha")
    out = pd.DataFrame({
        "ndvi": g["ndvi_util"].median(),
        "calidad": g["cal"].agg(lambda s: s.mode().min() if s.notna().any() else np.nan),
        "pix_utiles": g["ndvi_util"].count(),
        "pix_total": g["pixel"].count(),
    }).reset_index()
    out.insert(0, "zona", zona)
    return out


def construir_ndvi(zonas: pd.DataFrame, dir_ornl: Path = DIR_NDVI_ORNL) -> pd.DataFrame:
    partes = []
    for z in zonas["id"]:
        ndvi_px = leer_ornl(dir_ornl, z, BANDA_NDVI)
        if ndvi_px.empty:
            continue  # sin datos de esa zona: se reporta en validar(), no se inventa
        partes.append(agregar_ndvi_pixeles(ndvi_px, leer_ornl(dir_ornl, z, BANDA_CALIDAD), z))
    columnas = ["zona", "fecha", "ndvi", "calidad", "pix_utiles", "pix_total"]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=columnas)


# ---------------------------------------------------------------- validación

def validar(df: pd.DataFrame, tipo: str, zonas_esperadas: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Limpia y valida un DataFrame 'clima' o 'ndvi'. Devuelve (df_limpio, reporte).

    Sentinelas y valores fuera de rango -> NaN; tmin > tmax -> ambas NaN; duplicados (zona, fecha) -> se
    queda el primero. Nada se borra en silencio: todo se cuenta en el reporte.
    """
    if tipo not in COLS_REQUERIDAS:
        raise ValueError(f"tipo debe ser uno de {list(COLS_REQUERIDAS)}")
    faltan = [c for c in COLS_REQUERIDAS[tipo] if c not in df.columns]
    if faltan:
        raise ValueError(f"{tipo}: faltan columnas requeridas {faltan}")

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    rep = {"tipo": tipo, "filas_entrada": len(df)}

    numericas = df.select_dtypes("number").columns
    es_sentinela = df[numericas].isin(SENTINELAS)
    rep["sentinelas_a_nan"] = int(es_sentinela.to_numpy().sum())
    df[numericas] = df[numericas].mask(es_sentinela)

    rep["fuera_de_rango"] = {}
    for col, (lo, hi) in RANGOS.items():
        if col in df:
            mal = pd.Series(False, index=df.index)
            if lo is not None:
                mal |= df[col] < lo
            if hi is not None:
                mal |= df[col] > hi
            rep["fuera_de_rango"][col] = int(mal.sum())
            df.loc[mal, col] = np.nan

    if tipo == "clima":
        invertidas = df["tmin_c"] > df["tmax_c"]
        rep["tmin_mayor_tmax"] = int(invertidas.sum())
        df.loc[invertidas, ["tmin_c", "tmax_c"]] = np.nan

    dup = df.duplicated(["zona", "fecha"], keep="first")
    rep["duplicados"] = int(dup.sum())
    df = df[~dup].sort_values(["zona", "fecha"]).reset_index(drop=True)

    rep["por_zona"] = {}
    for zona in sorted(set(df["zona"]) | set(zonas_esperadas or [])):
        rep["por_zona"][zona] = _reporte_zona(df[df["zona"] == zona], tipo)
    rep["filas_salida"] = len(df)
    return df, rep


def _reporte_zona(d: pd.DataFrame, tipo: str) -> dict:
    if d.empty:
        return {"n": 0, "sin_datos": True}
    fechas = d["fecha"].drop_duplicates().sort_values()
    pasos = fechas.diff().dt.days.dropna()
    r = {
        "n": len(d),
        "desde": fechas.iloc[0].date().isoformat(),
        "hasta": fechas.iloc[-1].date().isoformat(),
        "paso_dias": float(pasos.median()) if len(pasos) else None,
        "nulos_pct": {c: round(100 * d[c].isna().mean(), 1) for c in d.columns if c not in ("zona", "fecha")},
    }
    if tipo == "clima":
        esperadas = pd.date_range(fechas.iloc[0], fechas.iloc[-1], freq="D")
        r["dias_faltantes"] = int(len(esperadas) - len(fechas))
        if "precip_fuente" in d:
            r["precip_fuente"] = d["precip_fuente"].value_counts(dropna=False).to_dict()
    else:
        # Entre años el paso es 12-13 días (DOY 353 -> 001); un hueco real es > 16 días
        r["huecos_mayores_16d"] = int((pasos > PASO_NDVI_DIAS).sum())
        r["hueco_max_dias"] = int(pasos.max()) if len(pasos) else None
        if "calidad" in d:
            r["calidad_conteo"] = d["calidad"].value_counts(dropna=False).sort_index().to_dict()
    return r


# ---------------------------------------------------------------- data/clean/ (escritura y lectura)

def preparar_datos_limpios(dir_clean: Path = DIR_CLEAN) -> dict:
    """Construye clima_diario.csv y ndvi.csv desde data/raw/, los valida y los escribe en data/clean/."""
    zonas = cargar_zonas()
    ids = list(zonas["id"])
    clima, rep_clima = validar(construir_clima_diario(zonas), "clima", ids)
    ndvi, rep_ndvi = validar(construir_ndvi(zonas), "ndvi", ids)
    Path(dir_clean).mkdir(parents=True, exist_ok=True)
    clima.to_csv(Path(dir_clean) / "clima_diario.csv", index=False, date_format="%Y-%m-%d")
    ndvi.to_csv(Path(dir_clean) / "ndvi.csv", index=False, date_format="%Y-%m-%d")
    return {"clima": rep_clima, "ndvi": rep_ndvi,
            "config": validar_config(zonas, cargar_cultivos(), cargar_rotaciones())}


def _leer_clean(nombre: str, dir_clean: Path, regenerar_si_falta: bool) -> pd.DataFrame:
    ruta = Path(dir_clean) / nombre
    if not ruta.exists():
        if not regenerar_si_falta:
            raise FileNotFoundError(f"Falta {ruta}. Ejecuta: python -m core.datos")
        preparar_datos_limpios(dir_clean)
    return pd.read_csv(ruta, parse_dates=["fecha"])


def cargar_clima_diario(dir_clean: Path = DIR_CLEAN, regenerar_si_falta: bool = True) -> pd.DataFrame:
    return _leer_clean("clima_diario.csv", dir_clean, regenerar_si_falta)


def cargar_ndvi(dir_clean: Path = DIR_CLEAN, regenerar_si_falta: bool = True) -> pd.DataFrame:
    return _leer_clean("ndvi.csv", dir_clean, regenerar_si_falta)


def resumen_texto(reportes: dict) -> str:
    """Reporte legible (ASCII para que no falle en consolas de Windows)."""
    lineas = []
    for tipo in ("clima", "ndvi"):
        r = reportes[tipo]
        lineas.append(f"== {tipo.upper()}: {r['filas_salida']} filas | sentinelas->NaN: {r['sentinelas_a_nan']}"
                      f" | fuera de rango: {r['fuera_de_rango']} | duplicados: {r['duplicados']}"
                      + (f" | tmin>tmax: {r['tmin_mayor_tmax']}" if tipo == "clima" else ""))
        for zona, z in r["por_zona"].items():
            if z.get("sin_datos"):
                lineas.append(f"   {zona:<11} NO DATA")
                continue
            nulos = {c: p for c, p in z["nulos_pct"].items() if p > 0} or "ninguno"
            extra = (f"dias faltantes {z['dias_faltantes']} | fuente lluvia {z.get('precip_fuente')}"
                     if tipo == "clima" else
                     f"huecos>16d {z['huecos_mayores_16d']} (max {z['hueco_max_dias']} d) | calidad {z.get('calidad_conteo')}")
            lineas.append(f"   {zona:<11} {z['n']:>5} filas {z['desde']}..{z['hasta']} paso {z['paso_dias']} d"
                          f" | nulos % {nulos} | {extra}")
    lineas.append("== CONFIG: " + ("ok" if not reportes["config"] else "; ".join(reportes["config"])))
    return "\n".join(lineas)


if __name__ == "__main__":
    print(resumen_texto(preparar_datos_limpios()))
