"""Pruebas de core/pronostico.py con series sintéticas (resultado conocido)."""
import numpy as np
import pandas as pd
import pytest

from core import periodos as P
from core import pronostico as F


def _zona(anios=range(2020, 2026), lluvia=None, ndvi=None):
    """Serie de una zona: por defecto, lluvia y NDVI perfectamente estacionales (se repiten cada año)."""
    cal = pd.concat([P.calendario(a) for a in anios], ignore_index=True)
    p = cal["periodo"].to_numpy()
    cal["precip_mm_21d"] = lluvia(cal) if lluvia else np.where((p >= 8) & (p <= 14), 100.0 + p, 5.0)
    cal["ndvi"] = ndvi(cal) if ndvi else 0.3 + 0.02 * p
    cal["tmax_media"] = 30.0
    return cal[["anio", "periodo", "fecha_inicio", "precip_mm_21d", "ndvi", "tmax_media"]]


def test_split_temporal_ultimo_20_por_ciento():
    assert F.n_entrenamiento(102) == 82            # 20 periodos de prueba
    df = _zona()
    n = F.n_entrenamiento(len(df))
    assert df["fecha_inicio"].iloc[:n].max() < df["fecha_inicio"].iloc[n:].min()   # prueba = lo más reciente


def test_baseline_estacional_usa_mismo_periodo_del_ultimo_anio_conocido():
    df = _zona(lluvia=lambda c: c["anio"] * 100.0 + c["periodo"])   # cambia cada año
    hist, fut = df.iloc[:82], df.iloc[82:][["anio", "periodo", "fecha_inicio"]]
    out = F.m_seasonal_naive(hist, fut, "precip_mm_21d")
    # hist llega a 2024-P14. Prueba: 2024-P15 … 2025-P17 (3 + 17 = 20 periodos)
    assert out["yhat"].iloc[0] == 2023 * 100 + 15     # 2024-P15 <- 2023-P15 (2024-P15 no se conoce)
    assert out["yhat"].iloc[3] == 2024 * 100 + 1      # 2025-P01 <- 2024-P01
    assert out["yhat"].iloc[-1] == 2023 * 100 + 17    # 2025-P17 <- 2023-P17 (2024-P17 es de prueba)


def test_baseline_perfecto_en_serie_estacional():
    met, _ = F.evaluar_zona(_zona(), "z", modelos={"precip_mm_21d": {F.BASELINE: F.m_seasonal_naive}})
    assert met["mae"].iloc[0] == pytest.approx(0.0)


def test_modelo_no_ve_el_objetivo_del_futuro():
    df = _zona()
    hist, fut = df.iloc[:82], df.iloc[82:][["anio", "periodo", "fecha_inicio"]]   # sin columnas objetivo
    for fn in (F.m_seasonal_naive, lambda h, f, v: F.m_ventana(h, f, v, "linear")):
        assert len(fn(hist, fut, "ndvi")) == 20


def test_matriz_rezagos_en_orden():
    y = np.arange(30, dtype=float)
    X = F._matriz(y, np.full(30, 7.0), np.full(30, 30.0), np.ones(30, int), [20], n=3, usar_lluvia=True)
    assert X[0, :3].tolist() == [19.0, 18.0, 17.0]      # y[t-1], y[t-2], y[t-3]
    assert X[0, 3:6].tolist() == [7.0, 7.0, 30.0]        # lluvia t-1, t-2, tmax t-1
    assert X.shape == (1, 3 + 2 + 1 + 2)


def test_ventana_lineal_aprende_serie_estacional():
    df = _zona()
    hist, fut = df.iloc[:85], df.iloc[85:][["anio", "periodo", "fecha_inicio"]]
    out = F.m_ventana(hist, fut, "ndvi", "linear")
    assert np.abs(out["yhat"].to_numpy() - df["ndvi"].iloc[85:].to_numpy()).max() < 0.02
    assert out.attrs["parametros"] in {"N=9", "N=17", "N=26"}


def test_random_forest_da_intervalo_y_respeta_limites():
    df = _zona()
    hist, fut = df.iloc[:85], df.iloc[85:][["anio", "periodo", "fecha_inicio"]]
    out = F.m_ventana(hist, fut, "precip_mm_21d", "random_forest", log=True)
    assert (out["yhat_lower"] <= out["yhat_upper"]).all()
    assert (out[["yhat", "yhat_lower", "yhat_upper"]] >= 0).all().all()


def test_prophet_intervalo_reproducible():
    df = _zona()
    hist, fut = df.iloc[:85], df.iloc[85:][["anio", "periodo", "fecha_inicio"]]
    a = F.m_prophet(hist, fut, "precip_mm_21d")
    b = F.m_prophet(hist, fut, "precip_mm_21d")
    assert np.allclose(a.to_numpy(), b.to_numpy())


def test_prophet_ndvi_con_regresores():
    df = _zona()
    hist, fut = df.iloc[:85], df.iloc[85:][["anio", "periodo", "fecha_inicio"]]
    out = F.m_prophet(hist, fut, "ndvi", regresores_lluvia=True)
    assert len(out) == 17 and out["yhat"].between(0, 1).all()
    assert (out["yhat_lower"] <= out["yhat"]).all() and (out["yhat"] <= out["yhat_upper"]).all()


def test_metricas_sesgo_negativo_si_subestima():
    m = F.metricas([10.0, 20.0, 30.0], [8.0, 18.0, 28.0])
    assert m["mae"] == pytest.approx(2.0) and m["sesgo"] == pytest.approx(-2.0)


def test_banda_angosta_mal_calibrada_se_reemplaza_por_empirica():
    angosto = lambda h, f, v: F._salida(np.full(len(f), 50.0), np.full(len(f), 49.9), np.full(len(f), 50.1),
                                        intervalo="native")
    modelos = {"precip_mm_21d": {F.BASELINE: F.m_seasonal_naive, "angosto": angosto}}
    df = _zona(lluvia=lambda c: 50 + 30 * np.sin(2 * np.pi * c["periodo"] / 17) + (c.index % 5) * 4.0)
    met, pred = F.evaluar_zona(df, "z", modelos)
    assert met.set_index("modelo").loc["angosto", "cobertura_intervalo_80"] < F.COBERTURA_MINIMA
    met["es_mejor"] = met["modelo"] == "angosto"          # forzamos que sea el elegido
    prono = F.pronosticar_zona(df, "z", met, pred, modelos)
    g = prono[prono["modelo"] == "angosto"]
    assert (g["tipo_intervalo"] == "empirical_abs_test_error_p80").all()
    assert (g["yhat_upper"] - g["yhat_lower"]).min() > 0.2  # ya no es la banda de 0.2 mm
    assert ((g["yhat_lower"] <= g["yhat"]) & (g["yhat"] <= g["yhat_upper"])).all()   # contiene al pronóstico


def test_evaluar_y_pronosticar_estructura():
    modelos = {"precip_mm_21d": {F.BASELINE: F.m_seasonal_naive,
                                 "linear": lambda h, f, v: F.m_ventana(h, f, v, "linear")},
               "ndvi": {F.BASELINE: F.m_seasonal_naive}}
    df = _zona(lluvia=lambda c: 50 + 40 * np.sin(2 * np.pi * c["periodo"] / 17) + c.index % 3)
    met, pred = F.evaluar_zona(df, "z", modelos)
    assert set(met["modelo"]) == {F.BASELINE, "linear"}
    assert met.groupby("variable")["es_mejor"].sum().eq(1).all()          # un mejor por variable
    assert (met["supera_baseline"] == (met["mae"] < met["mae_baseline"])).all()
    prono = F.pronosticar_zona(df, "z", met, pred, modelos)
    assert set(prono["anio"]) == {2026}
    assert prono.groupby(["variable", "modelo"]).size().eq(17).all()
    assert prono["etiqueta"].iloc[7].startswith("P08")
