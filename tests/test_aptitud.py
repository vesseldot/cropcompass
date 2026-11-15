"""Pruebas de core/aptitud.py: trapecios, ciclos que cruzan el año, helada y riego."""
import numpy as np
import pandas as pd
import pytest

from core import aptitud as A


def cultivo(**cambios):
    base = {"id": "c", "nombre": "Crop", "ciclo_meses": 4, "siembra_mes": 6, "tolera_helada": False,
            "temp_abs_min": 10, "temp_opt_min": 18, "temp_opt_max": 30, "temp_abs_max": 40,
            "lluvia_abs_min": 200, "lluvia_opt_min": 400, "lluvia_opt_max": 800, "lluvia_abs_max": 1500,
            "agua_relativa": 0.5, "fija_nitrogeno": False, "cubre_suelo": 0.5, "mercado_local": 0.5}
    base.update(cambios)
    return base


def clima_ciclo(n=6, tmedia=22.0, precip=100.0, helada=0.0):
    return pd.DataFrame({"periodo": range(8, 8 + n), "tmedia": tmedia, "precip_mm": precip,
                         "dias_helada": helada, "climatologia": True})


def test_trapecio():
    t = lambda x: A.trapecio(x, 10, 18, 30, 40)
    assert t(20) == 1.0 and t(18) == 1.0 and t(30) == 1.0
    assert t(10) == 0.0 and t(45) == 0.0
    assert t(14) == pytest.approx(0.5) and t(35) == pytest.approx(0.5)
    assert np.isnan(t(np.nan))
    assert A.trapecio(10, 10, 10, 20, 30) == 1.0          # abs_min == opt_min no divide entre cero


def test_periodos_etapa_cruza_fin_de_anio():
    assert A.periodos_etapa(15, 4) == [(0, 15), (0, 16), (0, 17), (1, 1)]
    assert A.periodos_de_cultivo(cultivo(ciclo_meses=4, siembra_mes=6)) == [(0, p) for p in range(8, 14)]


def test_sin_heladas_no_penaliza_cultivo_sensible():
    r = A.aptitud(cultivo(tolera_helada=False), clima_ciclo(helada=0.0), riego=False)
    assert r["factores"]["frost"] == 1.0 and r["aptitud"] == 1.0 and r["limitante"] is None


def test_heladas_penalizan_solo_al_sensible():
    # riego=True para aislar el factor helada (2 periodos x 100 mm = 200 mm limitaría por lluvia)
    sensible = A.aptitud(cultivo(tolera_helada=False), clima_ciclo(n=2, helada=1.0), riego=True)
    tolerante = A.aptitud(cultivo(tolera_helada=True), clima_ciclo(n=2, helada=1.0), riego=True)
    assert sensible["factores"]["frost"] == pytest.approx(1 - 2 / A.DIAS_HELADA_FALLA)
    assert sensible["limitante"] == "frost"
    assert tolerante["factores"]["frost"] == 1.0


def test_riego_anula_limitacion_por_lluvia():
    seco = clima_ciclo(precip=0.0)                     # 0 mm en todo el ciclo
    temporal = A.aptitud(cultivo(), seco, riego=False)
    con_riego = A.aptitud(cultivo(), seco, riego=True)
    assert temporal["factores"]["rainfall"] == 0.0 and temporal["limitante"] == "rainfall"
    assert con_riego["factores"]["rainfall"] == 1.0 and con_riego["aptitud"] == 1.0


def test_aptitud_es_el_factor_minimo():
    frio = clima_ciclo(tmedia=14.0)                    # trapecio de temperatura = 0.5
    r = A.aptitud(cultivo(), frio, riego=True)
    assert r["aptitud"] == pytest.approx(0.5) and r["limitante"] == "temperature"


def _ctx():
    filas = [{"zona": "z", "anio": a, "periodo": p, "tmax_media": 30.0 + (a - 2020), "tmin_media": 14.0,
              "precip_mm": 10.0 * p, "dias_helada": 0} for a in (2020, 2021) for p in range(1, 18)]
    return A.contexto_clima(pd.DataFrame(filas), "z")


def test_clima_de_etapa_usa_anio_siguiente_y_climatologia_al_final():
    ctx = _ctx()
    periodos = A.periodos_etapa(16, 3)                     # P16, P17, P01 del año siguiente
    c2020 = A.clima_de_etapa(ctx, periodos, anio=2020)
    assert c2020["anio"].tolist() == [2020, 2020, 2021]
    assert c2020["tmedia"].iloc[2] == pytest.approx((31.0 + 14.0) / 2) and not c2020["climatologia"].any()
    c2021 = A.clima_de_etapa(ctx, periodos, anio=2021)     # 2022-P01 no existe -> climatología
    assert c2021["climatologia"].tolist() == [False, False, True]
    assert c2021["tmedia"].iloc[2] == pytest.approx((30.5 + 14.0) / 2)


def test_clima_de_etapa_con_lluvia_pronosticada():
    c = A.clima_de_etapa(_ctx(), [(0, 8), (0, 9)], lluvia={8: 1.0, 9: 2.0})
    assert c["precip_mm"].tolist() == [1.0, 2.0]
