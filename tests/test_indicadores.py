"""Pruebas de core/indicadores.py con series sintéticas donde el resultado se conoce."""
import json

import numpy as np
import pandas as pd
import pytest

from core import indicadores as I
from core import periodos as P


def _serie(anios=(2020, 2021), zona="z", precip=None, ndvi=None, helada=None, calor=None, tmax=30.0, tmin=15.0):
    """serie_21d sintética. precip/ndvi/helada/calor: funciones (anio, periodo) -> valor, o None (constante)."""
    filas = []
    for a in anios:
        for p in range(1, 18):
            filas.append({
                "zona": zona, "anio": a, "periodo": p,
                "precip_mm": precip(a, p) if precip else 10.0,
                "tmax_media": tmax, "tmin_media": tmin,
                "ndvi": ndvi(a, p) if ndvi else 0.5,
                "dias_helada": helada(a, p) if helada else 0,
                "dias_calor": calor(a, p) if calor else 0,
                "ndvi_obs": 1, "ndvi_interpolado": False,
            })
    s = pd.DataFrame(filas)
    s["precip_mm_21d"] = s["precip_mm"]
    return s


def test_climatologia_media_desviacion_y_etiquetas():
    s = _serie(precip=lambda a, p: 10.0 if a == 2020 else 30.0)
    c = I.climatologia(s, "z")
    assert len(c) == 17 and c["periodo"].tolist() == list(range(1, 18))
    assert c["precip_media"].iloc[0] == pytest.approx(20.0)
    assert c["precip_std"].iloc[0] == pytest.approx(np.std([10, 30], ddof=1))
    assert c["etiqueta"].iloc[7] == "P08 (May 28 – Jun 17)"


def test_climatologia_periodo_sin_datos_queda_nan():
    s = _serie(ndvi=lambda a, p: np.nan if p == 5 else 0.5)
    c = I.climatologia(s, "z").set_index("periodo")
    assert np.isnan(c.loc[5, "ndvi_media"]) and c.loc[5, "anios_con_ndvi"] == 0


def test_suelo_desnudo_con_umbral_configurable():
    c = I.climatologia(_serie(ndvi=lambda a, p: 0.2 if p <= 3 else 0.5), "z")
    assert I.periodos_suelo_desnudo(c) == [1, 2, 3]
    assert I.periodos_suelo_desnudo(c, umbral=0.15) == []


def test_temporal_inicio_y_fin():
    c = I.climatologia(_serie(precip=lambda a, p: 50.0 if 8 <= p <= 13 else 5.0), "z")
    assert I.temporal(c) == {"inicio": 8, "fin": 13, "periodos": [8, 9, 10, 11, 12, 13]}
    assert I.temporal(I.climatologia(_serie(), "z")) is None      # nunca > 35 mm


def test_riesgo_helada_y_calor_por_promedio():
    s = _serie(helada=lambda a, p: 1 if (p == 1 and a == 2020) else 0,
               calor=lambda a, p: {5: 4, 6: 2}.get(p, 0))
    c = I.climatologia(s, "z")
    assert I.periodos_helada(c) == [1]           # promedio 0.5 > 0
    assert I.periodos_calor(c) == [5]            # 4 >= 3; P06 promedio 2 < 3


def test_clasificar_anios_por_terciles():
    lluvia = pd.Series([600.0, 100.0, 300.0, 500.0, 200.0, 400.0], index=range(2020, 2026))
    tipos = I.clasificar_anios(lluvia)
    assert tipos == {2020: "wet", 2021: "dry", 2022: "normal", 2023: "wet", 2024: "dry", 2025: "normal"}
    assert I.clasificar_anios(pd.Series([1.0, 2.0], index=[2020, 2021])) == {2020: "unknown", 2021: "unknown"}


def test_racha_seca_temporal_usa_dias_y_solo_dentro_del_temporal():
    fechas = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    precip = pd.Series(5.0, index=fechas)
    precip["2023-01-01":"2023-03-31"] = 0.0           # 90 días secos FUERA del temporal
    precip["2023-07-25":"2023-08-05"] = 0.0           # 12 días secos que cruzan P10/P11 (frontera 30-jul)
    clima = pd.DataFrame({"zona": "z", "fecha": fechas, "precip_mm": precip.to_numpy()})
    assert I.racha_seca_temporal(clima, "z", inicio=8, fin=14) == {2023: 12}


def test_ventanas_libres_lluvia_o_sin_helada():
    s = _serie(ndvi=lambda a, p: 0.2 if p <= 3 else 0.5,
               precip=lambda a, p: 50.0 if p == 3 else 5.0,
               helada=lambda a, p: 2 if p == 1 else 0)
    c = I.climatologia(s, "z")
    v = I.ventanas_libres(c, I.periodos_suelo_desnudo(c), I.periodos_helada(c))
    assert [x["periodo"] for x in v] == [2, 3]          # P01: sin lluvia y con helada -> no
    assert v[0]["requiere_riego"] and not v[1]["requiere_riego"]


def test_diagnostico_todas_y_json_serializable():
    s = pd.concat([_serie(zona="a"), _serie(zona="b", ndvi=lambda a, p: 0.1)], ignore_index=True)
    clima = pd.DataFrame({"zona": ["a", "b"], "fecha": ["2020-06-01"] * 2, "precip_mm": [0.0, 0.0]})
    diags = I.diagnostico_todas(s, clima)
    assert set(diags) == {"a", "b"}
    assert diags["a"]["suelo_desnudo"] == [] and len(diags["b"]["suelo_desnudo"]) == 17
    assert diags["a"]["etiquetas"][8].startswith("P08")
    json.dumps(I.a_json(diags))                           # no debe fallar
    texto = I.resumen_texto(diags)
    assert "== A" in texto and "17 periods" in texto      # zona b: los 17 periodos desnudos
