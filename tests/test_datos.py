"""Pruebas de core/datos.py con DataFrames pequeños donde el resultado se conoce."""
import json

import numpy as np
import pandas as pd
import pytest

from core import datos


def _clima(**cambios):
    """3 días de clima válidos de una zona; 'cambios' sobrescribe columnas."""
    base = {
        "zona": ["z1"] * 3,
        "fecha": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "precip_mm": [0.0, 5.0, 1.0],
        "tmax_c": [30.0, 31.0, 29.0],
        "tmin_c": [15.0, 16.0, 14.0],
    }
    base.update(cambios)
    return pd.DataFrame(base)


# ---------------------------------------------------------------- clima

def test_mapear_power_usa_imerg_y_rellena_con_power():
    crudo = pd.DataFrame({
        "fecha": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        "IMERG_PRECTOT": [2.0, np.nan, -999],
        "PRECTOTCORR": [1.0, 3.0, 4.0],
        "T2M_MAX": [30.0, 31.0, 29.0],
        "T2M_MIN": [15.0, 16.0, 14.0],
    })
    df = datos.mapear_power(crudo, "z1")
    assert df["precip_mm"].tolist() == [2.0, 3.0, 4.0]
    assert df["precip_fuente"].tolist() == ["IMERG", "POWER", "POWER"]
    assert (df["zona"] == "z1").all()


def test_validar_clima_valido_no_cambia_nada():
    df, rep = datos.validar(_clima(), "clima")
    assert len(df) == 3
    assert rep["sentinelas_a_nan"] == 0 and rep["duplicados"] == 0 and rep["tmin_mayor_tmax"] == 0
    assert rep["por_zona"]["z1"]["dias_faltantes"] == 0
    assert rep["por_zona"]["z1"]["nulos_pct"]["precip_mm"] == 0


def test_validar_clima_sentinelas_rangos_e_invertidas_a_nan():
    df, rep = datos.validar(_clima(tmax_c=[-999, 31.0, 10.0], precip_mm=[-1.0, 5.0, 1.0]), "clima")
    assert rep["sentinelas_a_nan"] == 1
    assert rep["fuera_de_rango"]["precip_mm"] == 1
    assert rep["tmin_mayor_tmax"] == 1          # día 3: tmin 14 > tmax 10
    assert np.isnan(df.loc[0, "tmax_c"]) and np.isnan(df.loc[0, "precip_mm"])
    assert df.loc[2, ["tmin_c", "tmax_c"]].isna().all()
    assert df.loc[1, "precip_mm"] == 5.0        # lo válido no se toca


def test_validar_quita_duplicados_y_detecta_dias_faltantes():
    df_in = _clima(fecha=["2023-01-01", "2023-01-01", "2023-01-04"])
    df, rep = datos.validar(df_in, "clima")
    assert rep["duplicados"] == 1 and len(df) == 2
    assert rep["por_zona"]["z1"]["dias_faltantes"] == 2   # faltan 02 y 03


def test_validar_falta_columna_lanza_error():
    with pytest.raises(ValueError, match="tmin_c"):
        datos.validar(_clima().drop(columns="tmin_c"), "clima")


def test_validar_reporta_zona_esperada_sin_datos():
    _, rep = datos.validar(_clima(), "clima", zonas_esperadas=["z1", "z2"])
    assert rep["por_zona"]["z2"]["sin_datos"]


# ---------------------------------------------------------------- NDVI

def test_validar_ndvi_rango_y_huecos():
    df_in = pd.DataFrame({
        "zona": "z1",
        "fecha": ["2023-01-01", "2023-01-17", "2023-02-18", "2023-03-06"],  # falta 2023-02-02
        "ndvi": [0.5, 1.5, -3000, 0.4],
    })
    df, rep = datos.validar(df_in, "ndvi")
    assert rep["fuera_de_rango"]["ndvi"] == 1 and rep["sentinelas_a_nan"] == 1
    assert df["ndvi"].isna().sum() == 2
    assert rep["por_zona"]["z1"]["huecos_mayores_16d"] == 1
    assert rep["por_zona"]["z1"]["hueco_max_dias"] == 32


def test_validar_ndvi_cambio_de_anio_no_es_hueco():
    # MOD13Q1: DOY 353 (19 dic) -> DOY 001 (1 ene) son 13 días, no un hueco
    df_in = pd.DataFrame({"zona": "z1", "fecha": ["2022-12-19", "2023-01-01", "2023-01-17"], "ndvi": 0.5})
    _, rep = datos.validar(df_in, "ndvi")
    assert rep["por_zona"]["z1"]["huecos_mayores_16d"] == 0


def _json_ornl(ruta, banda, fecha, valores, escala):
    ruta.write_text(json.dumps({
        "scale": escala, "band": banda,
        "subset": [{"calendar_date": fecha, "modis_date": "A2023001", "band": banda, "data": valores}],
    }), encoding="utf-8")


def test_construir_ndvi_excluye_nubes_relleno_y_escala(tmp_path):
    # 4 píxeles: 0.50 bueno, 0.60 marginal, 0.70 nube (fuera), -3000 relleno (fuera)
    _json_ornl(tmp_path / f"z1__{datos.BANDA_NDVI}__A2023001_A2023001.json",
               datos.BANDA_NDVI, "2023-01-01", [5000, 6000, 7000, -3000], "0.0001")
    _json_ornl(tmp_path / f"z1__{datos.BANDA_CALIDAD}__A2023001_A2023001.json",
               datos.BANDA_CALIDAD, "2023-01-01", [0, 1, 3, 0], "Not Applicable")
    zonas = pd.DataFrame({"id": ["z1", "z2"]})
    out = datos.construir_ndvi(zonas, dir_ornl=tmp_path)
    assert list(out["zona"]) == ["z1"]                 # z2 sin archivos: no se inventa
    fila = out.iloc[0]
    assert fila["ndvi"] == pytest.approx(0.55)          # mediana de 0.50 y 0.60
    assert fila["calidad"] == 0                         # moda de [0, 1, 3, 0]
    assert fila["pix_utiles"] == 2 and fila["pix_total"] == 4


def test_construir_ndvi_sin_banda_de_calidad_usa_todos_los_pixeles(tmp_path):
    _json_ornl(tmp_path / f"z1__{datos.BANDA_NDVI}__A2023001_A2023001.json",
               datos.BANDA_NDVI, "2023-01-01", [4000, 6000], "0.0001")
    out = datos.construir_ndvi(pd.DataFrame({"id": ["z1"]}), dir_ornl=tmp_path)
    assert out.iloc[0]["ndvi"] == pytest.approx(0.5)
    assert np.isnan(out.iloc[0]["calidad"])


# ---------------------------------------------------------------- configuración

def test_leer_json_acepta_cp1252(tmp_path):
    ruta = tmp_path / "r.json"
    ruta.write_bytes('{"cultivo": "caña de azúcar"}'.encode("cp1252"))
    assert datos.leer_json(ruta)["cultivo"] == "caña de azúcar"


def _config_minima():
    zonas = pd.DataFrame([{"id": "z1", "nombre": "Z1", "lat": 0, "lon": 0, "riego": True,
                           "cultivos_actuales": ["a"]}])
    cultivos = pd.DataFrame([{
        "id": "a", "ciclo_meses": 4, "siembra_mes": 6, "agua_relativa": 0.5, "cubre_suelo": 0.5,
        "mercado_local": 0.5, "temp_abs_min": 10, "temp_opt_min": 20, "temp_opt_max": 30, "temp_abs_max": 40,
        "lluvia_abs_min": 200, "lluvia_opt_min": 400, "lluvia_opt_max": 800, "lluvia_abs_max": 1500,
    }])
    rotaciones = [{"id": "r1", "actual_para": ["a"], "etapas": [{"cultivo": "a", "siembra_mes": 6}]}]
    return zonas, cultivos, rotaciones


def test_validar_config_minima_ok():
    assert datos.validar_config(*_config_minima()) == []


def test_validar_config_detecta_problemas():
    zonas, cultivos, rotaciones = _config_minima()
    cultivos.loc[0, "temp_opt_max"] = 45                       # óptimo fuera del absoluto
    rotaciones[0]["etapas"].append({"cultivo": "zzz"})          # cultivo inexistente
    rotaciones[0]["actual_para"] = []                           # nadie representa el cultivo actual
    problemas = " | ".join(datos.validar_config(zonas, cultivos, rotaciones))
    assert "temp_abs_min <= opt_min" in problemas
    assert "'zzz'" in problemas
    assert "ninguna rotación representa" in problemas


def test_config_real_del_proyecto_es_consistente():
    problemas = datos.validar_config(datos.cargar_zonas(), datos.cargar_cultivos(), datos.cargar_rotaciones())
    assert problemas == []
