"""Pronóstico de lluvia (precip_mm_21d) y NDVI por zona, 17 periodos de 21 días adelante (1 año).

Evaluación honesta:
- Split temporal: el último 20 % de los periodos es prueba (nunca aleatorio ni estratificado).
- Cada modelo pronostica TODO el bloque de prueba desde el final del entrenamiento (multi-paso),
  igual que el pronóstico real. Lluvia/temperatura futuras que un modelo use como entrada se
  reemplazan por la climatología calculada SOLO con el entrenamiento (sin fuga de información).
- Métrica principal MAE; también RMSE y R² (el R² de lluvia es inestable en secas: no usarlo solo).
- Todo se compara contra el baseline estacional ingenuo (mismo periodo del año anterior).

Generar data/processed/metricas.csv, pronosticos.csv y predicciones_prueba.csv:   python -m core.pronostico
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from core import periodos as P

HORIZONTE = P.N_PERIODOS          # 17 periodos = 1 año
FRACCION_PRUEBA = 0.20
VENTANAS = (9, 17, 26)            # N candidatos de la ventana deslizante
PCT_INTERVALO = (10, 90)          # intervalo de 80 %
COBERTURA_MINIMA = 0.70           # si la banda propia cubrió menos que esto en prueba, se usa la empírica
SEMILLA = 42
LIMITES = {"precip_mm_21d": (0.0, None), "ndvi": (0.0, 1.0)}
BASELINE = "seasonal_naive"

DIR_PROC = P.RAIZ / "data" / "processed"
RUTA_METRICAS = DIR_PROC / "metricas.csv"
RUTA_PRONOSTICOS = DIR_PROC / "pronosticos.csv"
RUTA_PRUEBA = DIR_PROC / "predicciones_prueba.csv"

for _log in ("cmdstanpy", "prophet"):
    logging.getLogger(_log).setLevel(logging.ERROR)


# ---------------------------------------------------------------- utilidades

def preparar_zona(serie: pd.DataFrame, zona: str) -> pd.DataFrame:
    """Serie de una zona en orden temporal (año, periodo)."""
    s = serie[serie["zona"] == zona].sort_values(["anio", "periodo"]).reset_index(drop=True)
    return s[["anio", "periodo", "fecha_inicio", "precip_mm_21d", "ndvi", "tmax_media"]].copy()


def n_entrenamiento(n: int, fraccion_prueba: float = FRACCION_PRUEBA) -> int:
    return n - int(round(n * fraccion_prueba))


def recortar(x, var: str) -> np.ndarray:
    lo, hi = LIMITES[var]
    return np.clip(np.asarray(x, dtype=float), lo, hi)


def exogena_extendida(hist: pd.DataFrame, futuro: pd.DataFrame, col: str) -> np.ndarray:
    """Variable de apoyo (lluvia, tmax) observada en hist y climatología de hist en el futuro."""
    clim = hist.groupby("periodo")[col].mean()
    pasado = hist[col].fillna(hist["periodo"].map(clim)).to_numpy(dtype=float)
    return np.concatenate([pasado, futuro["periodo"].map(clim).to_numpy(dtype=float)])


def metricas(real, pred) -> dict:
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    ok = ~np.isnan(real) & ~np.isnan(pred)
    if ok.sum() < 2:
        return {"mae": np.nan, "rmse": np.nan, "r2": np.nan, "sesgo": np.nan}
    return {"mae": mean_absolute_error(real[ok], pred[ok]),
            "rmse": float(np.sqrt(mean_squared_error(real[ok], pred[ok]))),
            "r2": r2_score(real[ok], pred[ok]),
            "sesgo": float(np.mean(pred[ok] - real[ok]))}   # < 0 = subestima


def _salida(yhat, lo=None, hi=None, **attrs) -> pd.DataFrame:
    n = len(yhat)
    out = pd.DataFrame({"yhat": np.asarray(yhat, float),
                        "yhat_lower": np.full(n, np.nan) if lo is None else np.asarray(lo, float),
                        "yhat_upper": np.full(n, np.nan) if hi is None else np.asarray(hi, float)})
    out.attrs.update(attrs)
    return out


# ---------------------------------------------------------------- modelos
# Firma común: modelo(hist, futuro, var) -> DataFrame(yhat, yhat_lower, yhat_upper)
#   hist   = periodos conocidos (con la variable objetivo)
#   futuro = periodos a pronosticar (solo anio, periodo, fecha_inicio: el modelo NO ve el objetivo)

def m_seasonal_naive(hist: pd.DataFrame, futuro: pd.DataFrame, var: str) -> pd.DataFrame:
    """Baseline: el valor del mismo periodo en el año más reciente conocido."""
    ultimo = hist.groupby("periodo")[var].last()   # last() ignora NaN
    return _salida(futuro["periodo"].map(ultimo).to_numpy(), intervalo="none")


def m_prophet(hist: pd.DataFrame, futuro: pd.DataFrame, var: str, log: bool = False,
              regresores_lluvia: bool = False) -> pd.DataFrame:
    from prophet import Prophet

    y = hist[var].astype(float)
    df = pd.DataFrame({"ds": hist["fecha_inicio"].to_numpy(), "y": np.log1p(y) if log else y})
    fut = pd.DataFrame({"ds": futuro["fecha_inicio"].to_numpy()})
    # growth="flat": 6 años no bastan para estimar una tendencia climática; con tendencia lineal Prophet
    # extrapolaba la racha húmeda 2024-2025 (~1,150 mm/año vs ~945 de media). Solo estacionalidad anual.
    modelo = Prophet(growth="flat", yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False,
                     interval_width=(PCT_INTERVALO[1] - PCT_INTERVALO[0]) / 100)
    if regresores_lluvia:
        lluvia = pd.Series(exogena_extendida(hist, futuro, "precip_mm_21d"))
        for k in (1, 2):
            rezago = lluvia.shift(k).bfill().to_numpy()
            df[f"lluvia_lag{k}"], fut[f"lluvia_lag{k}"] = rezago[:len(hist)], rezago[len(hist):]
            modelo.add_regressor(f"lluvia_lag{k}")
    modelo.fit(df.dropna(subset=["y"]))
    np.random.seed(SEMILLA)   # Prophet muestrea al azar para yhat_lower/upper: semilla = resultados reproducibles
    fc = modelo.predict(fut)
    vals = [fc[c].to_numpy() for c in ("yhat", "yhat_lower", "yhat_upper")]
    if log:
        vals = [np.expm1(v) for v in vals]
    return _salida(*[recortar(v, var) for v in vals], intervalo="prophet_80")


def _matriz(y, lluvia, tmax, periodo, indices, n: int, usar_lluvia: bool) -> np.ndarray:
    """Features en t: y[t-1..t-n], lluvia[t-1], lluvia[t-2] (NDVI), tmax[t-1], sin/cos del periodo."""
    filas = []
    for t in indices:
        f = list(y[t - n:t][::-1])
        if usar_lluvia:
            f += [lluvia[t - 1], lluvia[t - 2]]
        angulo = 2 * np.pi * periodo[t] / P.N_PERIODOS
        f += [tmax[t - 1], np.sin(angulo), np.cos(angulo)]
        filas.append(f)
    return np.asarray(filas, dtype=float)


def _nuevo(tipo: str):
    if tipo == "linear":
        return LinearRegression()
    return RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=SEMILLA)


def elegir_ventana(y, lluvia, tmax, periodo, tipo: str, usar_lluvia: bool) -> tuple[int, dict]:
    """Elige N con TimeSeriesSplit (MAE a un paso). Todas las N se evalúan sobre las mismas filas."""
    inicio = max(VENTANAS)
    idx = np.arange(inicio, len(y))
    if len(idx) < 12:
        return min(VENTANAS), {}
    cv = {}
    for n in VENTANAS:
        X, Y = _matriz(y, lluvia, tmax, periodo, idx, n, usar_lluvia), y[idx]
        errores = [mean_absolute_error(Y[va], _nuevo(tipo).fit(X[tr], Y[tr]).predict(X[va]))
                   for tr, va in TimeSeriesSplit(n_splits=3).split(X)]
        cv[n] = float(np.mean(errores))
    return min(cv, key=cv.get), cv


def m_ventana(hist: pd.DataFrame, futuro: pd.DataFrame, var: str, tipo: str, log: bool = False) -> pd.DataFrame:
    """Ventana deslizante + scikit-learn, pronóstico multi-paso recursivo."""
    usar_lluvia = var == "ndvi"
    n_h, n_f = len(hist), len(futuro)
    y_h = hist[var].astype(float).interpolate(limit_direction="both").to_numpy()  # huecos solo para features
    if log:
        y_h = np.log1p(y_h)
    lluvia = exogena_extendida(hist, futuro, "precip_mm_21d")
    tmax = exogena_extendida(hist, futuro, "tmax_media")
    periodo = np.concatenate([hist["periodo"].to_numpy(), futuro["periodo"].to_numpy()])

    n, _ = elegir_ventana(y_h, lluvia, tmax, periodo, tipo, usar_lluvia)
    idx = np.arange(n, n_h)
    modelo = _nuevo(tipo).fit(_matriz(y_h, lluvia, tmax, periodo, idx, n, usar_lluvia), y_h[idx])

    y = np.concatenate([y_h, np.full(n_f, np.nan)])
    lo, hi = np.full(n_f, np.nan), np.full(n_f, np.nan)
    lim = (0.0, None) if log else LIMITES[var]
    for i, t in enumerate(range(n_h, n_h + n_f)):
        x = _matriz(y, lluvia, tmax, periodo, [t], n, usar_lluvia)
        y[t] = np.clip(modelo.predict(x)[0], *lim)
        if tipo == "random_forest":
            arboles = [arbol.predict(x)[0] for arbol in modelo.estimators_]
            lo[i], hi[i] = np.percentile(arboles, PCT_INTERVALO)
    vals = [y[n_h:], lo, hi]
    if log:
        vals = [np.expm1(v) for v in vals]
    intervalo = "rf_trees_p10_p90" if tipo == "random_forest" else "none"
    return _salida(*[recortar(v, var) for v in vals], intervalo=intervalo, parametros=f"N={n}")


MODELOS: dict[str, dict[str, Callable]] = {
    "precip_mm_21d": {
        BASELINE: m_seasonal_naive,
        "prophet": lambda h, f, v: m_prophet(h, f, v),
        "prophet_log1p": lambda h, f, v: m_prophet(h, f, v, log=True),
        "linear": lambda h, f, v: m_ventana(h, f, v, "linear"),
        "linear_log1p": lambda h, f, v: m_ventana(h, f, v, "linear", log=True),
        "random_forest": lambda h, f, v: m_ventana(h, f, v, "random_forest"),
        "random_forest_log1p": lambda h, f, v: m_ventana(h, f, v, "random_forest", log=True),
    },
    "ndvi": {
        BASELINE: m_seasonal_naive,
        "prophet_rain_lags": lambda h, f, v: m_prophet(h, f, v, regresores_lluvia=True),
        "linear": lambda h, f, v: m_ventana(h, f, v, "linear"),
        "random_forest": lambda h, f, v: m_ventana(h, f, v, "random_forest"),
    },
}


# ---------------------------------------------------------------- evaluación y pronóstico

def evaluar_zona(df: pd.DataFrame, zona: str, modelos: dict = MODELOS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Métricas en el bloque de prueba (último 20 %) y predicciones de prueba de cada modelo."""
    n_tr = n_entrenamiento(len(df))
    hist, prueba = df.iloc[:n_tr], df.iloc[n_tr:]
    futuro = prueba[["anio", "periodo", "fecha_inicio"]].reset_index(drop=True)
    filas, preds = [], []
    for var, mods in modelos.items():
        real = prueba[var].to_numpy(dtype=float)
        for nombre, fn in mods.items():
            out = fn(hist, futuro, var)
            m = metricas(real, out["yhat"])
            dentro = (real >= out["yhat_lower"]) & (real <= out["yhat_upper"])
            con_int = out["yhat_lower"].notna() & ~np.isnan(real)
            filas.append({"zona": zona, "variable": var, "modelo": nombre, **m,
                          "cobertura_intervalo_80": float(dentro[con_int].mean()) if con_int.any() else np.nan,
                          "parametros": out.attrs.get("parametros", ""),
                          "n_train": n_tr, "n_test": len(prueba)})
            preds.append(futuro.assign(zona=zona, variable=var, modelo=nombre, real=real,
                                       yhat=out["yhat"], yhat_lower=out["yhat_lower"], yhat_upper=out["yhat_upper"]))
    met = pd.DataFrame(filas)
    base = met[met["modelo"] == BASELINE].set_index("variable")["mae"]
    met["mae_baseline"] = met["variable"].map(base)
    met["mejora_vs_baseline_pct"] = 100 * (1 - met["mae"] / met["mae_baseline"])
    met["supera_baseline"] = met["mae"] < met["mae_baseline"]
    met["es_mejor"] = met.index.isin(met.groupby("variable")["mae"].idxmin())  # uno por variable
    return met, pd.concat(preds, ignore_index=True)


def pronosticar_zona(df: pd.DataFrame, zona: str, met: pd.DataFrame, preds_prueba: pd.DataFrame,
                     modelos: dict = MODELOS) -> pd.DataFrame:
    """Reentrena el mejor modelo (y el baseline, como referencia) con TODOS los datos y pronostica
    los 17 periodos del año siguiente. Si el modelo no da intervalo propio, o su banda de 80 % cubrió
    menos de COBERTURA_MINIMA de los valores de prueba, se usa uno empírico simétrico:
    yhat ± percentil 80 del error absoluto de ese modelo en el bloque de prueba."""
    anio = int(df["anio"].max()) + 1
    cal = P.calendario(anio)
    futuro = cal[["anio", "periodo", "fecha_inicio"]]
    partes = []
    for var, mods in modelos.items():
        mejor = met[(met["variable"] == var) & met["es_mejor"]]["modelo"].iloc[0]
        for nombre in dict.fromkeys([mejor, BASELINE]):
            out = mods[nombre](df, futuro, var)
            tipo_int = out.attrs.get("intervalo", "none")
            fila = met[(met["variable"] == var) & (met["modelo"] == nombre)].iloc[0]
            cobertura = fila["cobertura_intervalo_80"]
            if out["yhat_lower"].isna().all() or (not np.isnan(cobertura) and cobertura < COBERTURA_MINIMA):
                p = preds_prueba[(preds_prueba["variable"] == var) & (preds_prueba["modelo"] == nombre)]
                errores = (p["real"] - p["yhat"]).dropna()
                if len(errores) >= 5:
                    # Banda simétrica: el modelo final se reentrena con la prueba incluida, así que no se
                    # arrastra el sesgo de prueba (2024-25 fue húmedo); solo su tamaño típico de error.
                    q = np.percentile(np.abs(errores), PCT_INTERVALO[1] - PCT_INTERVALO[0])
                    out["yhat_lower"] = recortar(out["yhat"] - q, var)
                    out["yhat_upper"] = recortar(out["yhat"] + q, var)
                    tipo_int = "empirical_abs_test_error_p80"
            partes.append(cal[["anio", "periodo", "etiqueta", "fecha_inicio"]].assign(
                zona=zona, variable=var, modelo=nombre, es_mejor=nombre == mejor,
                yhat=out["yhat"].to_numpy(), yhat_lower=out["yhat_lower"].to_numpy(),
                yhat_upper=out["yhat_upper"].to_numpy(), tipo_intervalo=tipo_int))
    return pd.concat(partes, ignore_index=True)


def ejecutar(serie: pd.DataFrame, modelos: dict = MODELOS) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mets, pronos, pruebas = [], [], []
    for zona in sorted(serie["zona"].unique()):
        df = preparar_zona(serie, zona)
        met, pred = evaluar_zona(df, zona, modelos)
        mets.append(met)
        pruebas.append(pred)
        pronos.append(pronosticar_zona(df, zona, met, pred, modelos))
    return (pd.concat(mets, ignore_index=True), pd.concat(pronos, ignore_index=True),
            pd.concat(pruebas, ignore_index=True))


def generar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    met, prono, prueba = ejecutar(P.cargar_serie_21d())
    DIR_PROC.mkdir(parents=True, exist_ok=True)
    met.to_csv(RUTA_METRICAS, index=False, float_format="%.4f")
    prono.to_csv(RUTA_PRONOSTICOS, index=False, float_format="%.4f", date_format="%Y-%m-%d")
    prueba.to_csv(RUTA_PRUEBA, index=False, float_format="%.4f", date_format="%Y-%m-%d")
    return met, prono, prueba


def cargar_resultados(regenerar_si_falta: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rutas = (RUTA_METRICAS, RUTA_PRONOSTICOS, RUTA_PRUEBA)
    if not all(r.exists() for r in rutas):
        if not regenerar_si_falta:
            raise FileNotFoundError("Faltan resultados. Ejecuta: python -m core.pronostico")
        return generar()
    return (pd.read_csv(RUTA_METRICAS), pd.read_csv(RUTA_PRONOSTICOS, parse_dates=["fecha_inicio"]),
            pd.read_csv(RUTA_PRUEBA, parse_dates=["fecha_inicio"]))


def tabla_texto(met: pd.DataFrame) -> str:
    """Tabla comparativa ASCII: * = mejor modelo, + = supera al baseline."""
    lineas = []
    for (zona, var), g in met.groupby(["zona", "variable"], sort=False):
        lineas.append(f"== {zona} / {var}  (train {g['n_train'].iloc[0]}, test {g['n_test'].iloc[0]} periods)")
        lineas.append(f"   {'model':<22}{'MAE':>8}{'RMSE':>8}{'R2':>7}{'bias':>8}{'vs base':>9}{'cov80':>7}  params")
        for r in g.itertuples():
            marca = ("*" if r.es_mejor else " ") + ("+" if r.supera_baseline else " ")
            cob = "" if np.isnan(r.cobertura_intervalo_80) else f"{100 * r.cobertura_intervalo_80:.0f}%"
            params = r.parametros if isinstance(r.parametros, str) else ""
            lineas.append(f" {marca}{r.modelo:<22}{r.mae:>8.3f}{r.rmse:>8.3f}{r.r2:>7.2f}{r.sesgo:>8.3f}"
                          f"{r.mejora_vs_baseline_pct:>8.0f}%{cob:>7}  {params}")
    return "\n".join(lineas)


if __name__ == "__main__":
    import time
    t0 = time.time()
    met, prono, _ = generar()
    print(tabla_texto(met))
    print(f"\n* best model   + beats seasonal naive baseline   ({time.time() - t0:.0f}s)")
    print(f"Forecast: {prono['anio'].iloc[0]}, {prono['periodo'].nunique()} periods -> {RUTA_PRONOSTICOS.relative_to(P.RAIZ)}")
