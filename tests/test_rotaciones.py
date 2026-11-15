"""Pruebas de core/rotaciones.py: pesos, criterios, backtesting y ranking."""
import pandas as pd
import pytest

from core import rotaciones as R
from tests.test_aptitud import cultivo


def _serie(anios=range(2020, 2026), ndvi=lambda p: 0.5, tmax=lambda a, p: 30.0, precip=lambda a, p: 60.0):
    filas = []
    for a in anios:
        for p in range(1, 18):
            pr = precip(a, p)
            filas.append({"zona": "z", "anio": a, "periodo": p, "precip_mm": pr, "precip_mm_21d": pr,
                          "tmax_media": tmax(a, p), "tmin_media": 14.0, "ndvi": ndvi(p),
                          "dias_helada": 0, "dias_calor": 0, "ndvi_obs": 1, "ndvi_interpolado": False})
    return pd.DataFrame(filas)


def _zonas(riego=True, actuales=("a",)):
    return pd.DataFrame([{"id": "z", "nombre": "Z", "lat": 0, "lon": 0, "riego": riego,
                          "cultivos_actuales": list(actuales)}])


def _cultivos(*cs):
    return pd.DataFrame(list(cs))


def _rot(id_, *etapas, actual=(), requiere=None):
    r = {"id": id_, "nombre": id_.upper(), "actual_para": list(actual),
         "etapas": [{"cultivo": c, "siembra_mes": m} for c, m in etapas]}
    if requiere:
        r["requiere_actual"] = requiere
    return r


CULTIVOS = _cultivos(
    cultivo(id="a", agua_relativa=0.9, mercado_local=0.9, cubre_suelo=0.6),
    cultivo(id="b", agua_relativa=0.2, mercado_local=0.3, cubre_suelo=0.6),
    cultivo(id="c", agua_relativa=0.5, mercado_local=0.6, cubre_suelo=0.6),
    cultivo(id="leg", agua_relativa=0.3, fija_nitrogeno=True, cubre_suelo=0.9, ciclo_meses=3, siembra_mes=1),
)
ROTS = [_rot("ra", ("a", 6), actual=["a"]), _rot("rb", ("b", 6)), _rot("rc", ("c", 6))]


def test_normalizar_pesos():
    assert R.normalizar_pesos({"water": 2, "soil": 2}) == {"climate": 0, "water": 0.5, "soil": 0.5, "income": 0}
    assert R.normalizar_pesos({"water": 0}) == {c: 0.25 for c in R.CRITERIOS}
    assert R.normalizar_pesos({"water": -3, "income": 1})["water"] == 0


def test_pesos_solo_agua_gana_la_de_menor_agua_relativa():
    res = R.rankear("z", {"water": 1}, serie=_serie(), cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas())
    assert [r["id"] for r in res] == ["rb", "rc", "ra"]
    assert res[0]["puntaje"] == pytest.approx(100 * res[0]["criterios"]["water"])


def test_pesos_solo_ingreso_gana_mercado_local():
    res = R.rankear("z", {"income": 1}, serie=_serie(), cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas())
    assert res[0]["id"] == "ra" and res[0]["es_actual"]


def test_agua_pondera_por_tiempo_agregar_cultivo_aumenta_demanda():
    cul = {c["id"]: c for c in CULTIVOS.to_dict("records")}
    solo = R.etapas_de_rotacion(_rot("x", ("b", 6)), cul)
    con_leg = R.etapas_de_rotacion(_rot("y", ("b", 6), ("leg", 1)), cul)
    assert R.criterio_agua(con_leg) < R.criterio_agua(solo)


def test_suelo_premia_cubrir_periodos_desnudos_y_omite_si_no_hay():
    cul = {c["id"]: c for c in CULTIVOS.to_dict("records")}
    etapas = R.etapas_de_rotacion(_rot("y", ("b", 6), ("leg", 1)), cul)      # leg ocupa P01-P04
    _, partes = R.criterio_suelo(etapas, desnudos=[1, 2, 3, 4, 5, 6, 7, 8])
    assert partes["bare_periods_covered"] == pytest.approx(5 / 8)            # P01-P04 + P08
    assert partes["nitrogen_fixing_share"] == 0.5
    _, sin = R.criterio_suelo(etapas, desnudos=[])
    assert "bare_periods_covered" not in sin


def test_rankear_estructura_actual_y_desglose():
    res = R.rankear("z", None, serie=_serie(ndvi=lambda p: 0.2 if p <= 5 else 0.5),
                    cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas())
    assert len(res) >= 3 and sum(r["es_actual"] for r in res) == 1
    r = res[0]
    assert set(r["criterios"]) == set(R.CRITERIOS) and r["rango"] == 1
    assert r["puntaje"] == pytest.approx(sum(r["contribuciones"].values()))
    assert r["desnudos_zona"] == [1, 2, 3, 4, 5]
    assert r["backtest"]["anios_total"] == 6
    assert r["etapas"][0]["inicio"].startswith("P08")


def test_requiere_actual_filtra_rotaciones():
    rots = ROTS + [_rot("solo_si_a", ("leg", 1), requiere=["a"])]
    ids_a = {r["id"] for r in R.rankear("z", None, serie=_serie(), cultivos=CULTIVOS, rotaciones=rots,
                                        zonas=_zonas(), cultivo_actual="a")}
    ids_b = {r["id"] for r in R.rankear("z", None, serie=_serie(), cultivos=CULTIVOS, rotaciones=rots,
                                        zonas=_zonas(), cultivo_actual="b")}
    assert "solo_si_a" in ids_a and "solo_si_a" not in ids_b


def test_backtest_anio_frio_falla_con_factor_y_tipo_de_anio():
    # 2022 frío (tmax 12 -> tmedia 13 < 18 óptimo) y además el año más seco
    serie = _serie(tmax=lambda a, p: 12.0 if a == 2022 else 30.0,
                   precip=lambda a, p: {2022: 10.0, 2023: 20.0}.get(a, 60.0 + a - 2020))
    res = R.rankear("z", None, serie=serie, cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas())
    bt = res[0]["backtest"]
    assert bt["anios_ok"] == 5
    (fallo,) = bt["fallidos"]
    assert fallo["anio"] == 2022 and fallo["factor_limitante"] == "temperature"
    assert fallo["tipo_anio"] == "dry"


def test_sin_riego_la_lluvia_si_limita():
    seco = _serie(precip=lambda a, p: 5.0)            # ~30 mm por ciclo de 6 periodos < 200 absoluto
    con = R.rankear("z", None, serie=seco, cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas(riego=True))
    sin = R.rankear("z", None, serie=seco, cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas(riego=False))
    assert all(r["backtest"]["anios_ok"] == 6 for r in con)
    assert all(r["backtest"]["anios_ok"] == 0 for r in sin)
    assert sin[0]["etapas"][0]["limitante"] == "rainfall"


def test_outlook_con_lluvia_pronosticada():
    lluvia = pd.Series(0.0, index=range(1, 18))
    res = R.rankear("z", None, serie=_serie(), cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas(riego=False),
                    lluvia_outlook=lluvia, anio_outlook=2026)
    assert res[0]["outlook"]["anio"] == 2026 and not res[0]["outlook"]["ok"]


def test_rankear_datos_reales_las_tres_zonas():
    for zona in ("zacatepec", "cuautla", "axochiapan"):
        res = R.rankear(zona, {"climate": 1, "water": 1, "soil": 1, "income": 1})
        assert len(res) >= 3
        assert any(r["es_actual"] for r in res)
        assert all(r["backtest"]["anios_total"] == 6 for r in res)
        assert all(0 <= r["puntaje"] <= 100 for r in res)
