"""Pruebas de core/periodos.py: calendario de 21 días, NDVI diario y tabla integrada."""
import numpy as np
import pandas as pd
import pytest

from core import periodos as P


# ---------------------------------------------------------------- calendario

def test_2023_tiene_17_periodos_y_365_dias():
    cal = P.calendario(2023)
    assert len(cal) == 17 and cal["n_dias"].sum() == 365
    assert (cal["n_dias"].iloc[:16] == 21).all() and cal["n_dias"].iloc[16] == 29


def test_2024_bisiesto_suma_366():
    cal = P.calendario(2024)
    assert cal["n_dias"].sum() == 366 and cal["n_dias"].iloc[16] == 30


def test_periodos_contiguos_sin_huecos():
    cal = P.calendario(2023)
    assert cal["fecha_inicio"].iloc[0] == pd.Timestamp("2023-01-01")
    assert cal["fecha_fin"].iloc[-1] == pd.Timestamp("2023-12-31")
    assert ((cal["fecha_inicio"].iloc[1:].to_numpy() - cal["fecha_fin"].iloc[:-1].to_numpy())
            == np.timedelta64(1, "D")).all()


def test_1_de_junio_cae_en_P08_y_etiqueta():
    assert P.periodo_de_fecha("2023-06-01") == 8
    assert P.periodo_de_fecha("2024-06-01") == 8
    assert P.calendario(2023).loc[7, "etiqueta"] == "P08 (May 28 – Jun 17)"


def test_periodo_de_fecha_bordes_y_series():
    assert P.periodo_de_fecha("2023-01-21") == 1 and P.periodo_de_fecha("2023-01-22") == 2
    assert P.periodo_de_fecha("2023-12-31") == 17 and P.periodo_de_fecha("2024-12-31") == 17
    # P17 empieza el día 337 = 3 de diciembre (año no bisiesto)
    s = P.periodo_de_fecha(pd.Series(pd.to_datetime(["2023-01-01", "2023-12-02", "2023-12-03"])))
    assert s.tolist() == [1, 16, 17]


def test_mes_a_periodo_y_meses_a_periodos():
    assert P.mes_a_periodo(1) == 1 and P.mes_a_periodo(6) == 8 and P.mes_a_periodo(12) == 16
    assert P.meses_a_periodos(4) == 6     # round(5.80)
    assert P.meses_a_periodos(3) == 4     # round(4.35)
    assert P.meses_a_periodos(12) == 17   # round(17.39)


def test_racha_seca_max():
    assert P.racha_seca_max([0, 0, 5, 0, 0, 0, 0.5, 2]) == 4
    assert P.racha_seca_max([0, np.nan, 0]) == 1      # un día sin dato corta la racha
    assert P.racha_seca_max([3, 4]) == 0


# ---------------------------------------------------------------- NDVI diario

def test_ndvi_diario_interpola_linealmente_y_no_extrapola():
    nd = pd.DataFrame({"zona": "z", "fecha": ["2023-01-01", "2023-01-17"], "ndvi": [0.2, 0.6]})
    d = P.ndvi_diario(nd).set_index("fecha")
    assert d.loc["2023-01-09", "ndvi"] == pytest.approx(0.4)         # punto medio
    assert d.index.min() == pd.Timestamp("2023-01-01") and d.index.max() == pd.Timestamp("2023-01-17")
    assert d["es_obs"].sum() == 2


def test_ndvi_diario_quita_nubes_y_respeta_hueco_maximo():
    nd = pd.DataFrame({
        "zona": "z",
        "fecha": ["2023-01-01", "2023-01-17", "2023-02-02", "2023-03-22"],
        "ndvi": [0.2, 0.9, 0.4, 0.5],
        "calidad": [0, 3, 0, 0],   # 17-ene nuboso -> se quita
    })
    d = P.ndvi_diario(nd).set_index("fecha")
    assert d.loc["2023-01-17", "ndvi"] == pytest.approx(0.3)         # interpolado sin el nuboso (hueco 32 d)
    assert np.isnan(d.loc["2023-03-01", "ndvi"])                      # hueco de 48 d > 32 -> NaN
    assert d.loc["2023-03-22", "ndvi"] == pytest.approx(0.5)


# ---------------------------------------------------------------- tabla integrada

def _clima_constante(anios=(2023,), precip=1.0, tmax=30.0, tmin=15.0, zonas=("z",)):
    fechas = pd.date_range(f"{min(anios)}-01-01", f"{max(anios)}-12-31", freq="D")
    return pd.concat([pd.DataFrame({"zona": z, "fecha": fechas, "precip_mm": precip,
                                    "tmax_c": tmax, "tmin_c": tmin}) for z in zonas], ignore_index=True)


def _ndvi_vacio():
    return pd.DataFrame({"zona": pd.Series(dtype=object), "fecha": pd.Series(dtype="datetime64[ns]"),
                         "ndvi": pd.Series(dtype=float)})


def test_lluvia_constante_1mm_da_precip_igual_a_n_dias():
    s = P.construir_serie_21d(_clima_constante(anios=(2023, 2024)), _ndvi_vacio())
    assert len(s) == 2 * 17
    assert (s["precip_mm"] == s["n_dias"]).all()
    assert (s["dias_lluvia"] == s["n_dias"]).all() and (s["racha_seca_max"] == 0).all()
    assert s["precip_mm_21d"].to_numpy() == pytest.approx(21.0)       # P17 normalizado a 21 días


def test_rejilla_completa_zonas_x_anios_x_periodos():
    s = P.construir_serie_21d(_clima_constante(anios=(2022, 2023), zonas=("a", "b", "c")), _ndvi_vacio())
    assert len(s) == 3 * 2 * 17
    assert not s.duplicated(["zona", "anio", "periodo"]).any()
    assert s["ndvi"].isna().all() and s["ndvi_interpolado"].all()      # sin NDVI: NaN, no inventado


def test_helada_calor_y_racha_en_un_periodo():
    clima = _clima_constante(precip=0.0, tmax=36.0, tmin=1.0)       # todo seco, caliente y con helada
    s = P.construir_serie_21d(clima, _ndvi_vacio()).set_index("periodo")
    assert s.loc[1, "dias_helada"] == 21 and s.loc[1, "dias_calor"] == 21
    assert s.loc[1, "racha_seca_max"] == 21 and s.loc[17, "racha_seca_max"] == 29
    assert s.loc[1, "tmin_min"] == 1.0 and s.loc[1, "tmax_media"] == 36.0


def test_ndvi_obs_cuenta_compuestos_reales_por_periodo():
    nd = pd.DataFrame({
        "zona": "z",
        "fecha": pd.to_datetime(["2023-01-01", "2023-01-17", "2023-02-02", "2023-02-18"]),
        "ndvi": [0.3, 0.3, 0.3, 0.3],
        "calidad": [0, 0, 3, 0],
    })
    s = P.construir_serie_21d(_clima_constante(), nd).set_index("periodo")
    assert s.loc[1, "ndvi_obs"] == 2                     # 1-ene y 17-ene en P01 (1-21 ene)
    assert s.loc[2, "ndvi_obs"] == 0 and s.loc[2, "ndvi_interpolado"]   # 2-feb nuboso, no cuenta
    assert s.loc[2, "ndvi"] == pytest.approx(0.3)       # pero sí tiene NDVI interpolado
    assert s.loc[3, "ndvi_obs"] == 1                     # 18-feb en P03 (12 feb - 4 mar)
    assert np.isnan(s.loc[10, "ndvi"])                   # después del último compuesto: NaN
