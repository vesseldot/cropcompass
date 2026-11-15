"""Pruebas de core/explicacion.py: textos completos, con números reales y sin inventar."""
import re

import pytest

from core import datos
from core import explicacion as X
from core import indicadores as I
from core import periodos as P
from core import rotaciones as R
from tests.test_rotaciones import CULTIVOS, ROTS, _serie, _zonas


def _todos_los_textos(exp):
    return " ".join([exp["why_suggested"], exp["disclaimer"], *exp["evidence"], *exp["benefits"],
                     *exp["risks"], *exp["information_gaps"]])


@pytest.fixture(scope="module")
def reales():
    """Ranking explicado de las 3 zonas con los datos reales."""
    serie, clima, zonas = P.cargar_serie_21d(), datos.cargar_clima_diario(), datos.cargar_zonas()
    out = {}
    for z in zonas["id"]:
        diag = I.diagnostico(serie, clima, z)
        res = R.rankear(z, serie=serie, zonas=zonas)
        out[z] = X.explicar_ranking(res, diag, zonas.set_index("id").loc[z].to_dict())
    return out


def test_toda_rotacion_trae_disclaimer_y_gap_de_hipotesis(reales):
    for res in reales.values():
        for r in res:
            exp = r["explicacion"]
            assert exp["disclaimer"] == "This tool supports, not replaces, farmer judgment."
            assert exp["information_gaps"][0] == X.GAP_HIPOTESIS
            assert all(exp[k] for k in ("why_suggested", "evidence", "benefits", "risks", "information_gaps"))


def test_textos_sin_nan_ni_none(reales):
    for res in reales.values():
        for r in res:
            texto = _todos_los_textos(r["explicacion"])
            assert not re.search(r"\b(nan|None)\b", texto, flags=re.IGNORECASE)


def test_evidencia_con_numeros_del_backtest_y_fuentes(reales):
    r = reales["axochiapan"][0]
    ev = " ".join(r["explicacion"]["evidence"])
    bt = r["backtest"]
    assert f"Worked in {bt['anios_ok']} of {bt['anios_total']} years" in ev
    assert "GPM IMERG" in ev and "NASA POWER" in ev and "MODIS MOD13Q1" in ev


def test_aviso_de_zona_y_actual_como_referencia(reales):
    gaps = " ".join(reales["cuautla"][0]["explicacion"]["information_gaps"])
    assert "too cold" in gaps
    actual = next(r for r in reales["axochiapan"] if r["es_actual"])
    assert "This is your current rotation" in actual["explicacion"]["why_suggested"]


def test_anio_fallido_aparece_con_tipo_y_factor():
    serie = _serie(tmax=lambda a, p: 12.0 if a == 2022 else 30.0,
                   precip=lambda a, p: {2022: 10.0, 2023: 20.0}.get(a, 60.0 + a - 2020))
    res = X.explicar_ranking(R.rankear("z", None, serie=serie, cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas()))
    ev = " ".join(res[0]["explicacion"]["evidence"])
    assert "Failed in 2022 (dry year)" in ev and "limited by temperature" in ev
    assert any("Did not work in 1 of 6 years" in x for x in res[0]["explicacion"]["risks"])


def test_aviso_ndvi_interpolado_solo_si_es_alto():
    res = R.rankear("z", None, serie=_serie(), cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas())
    bajo = X.explicar(res[0], diag={"ndvi_interpolado_pct": 2.0})
    alto = X.explicar(res[0], diag={"ndvi_interpolado_pct": 45.0})
    assert not any("interpolated" in g for g in bajo["information_gaps"])
    assert any("NDVI partly interpolated: 45%" in g for g in alto["information_gaps"])


def test_beneficio_de_menos_agua_frente_a_la_actual():
    res = X.explicar_ranking(R.rankear("z", {"water": 1}, serie=_serie(), cultivos=CULTIVOS,
                                       rotaciones=ROTS, zonas=_zonas()))
    mejor = res[0]                                    # rb: agua_relativa 0.2 vs actual ra: 0.9
    assert any("Lower water demand than your current rotation" in b for b in mejor["explicacion"]["benefits"])
    assert "lower water use" in mejor["explicacion"]["why_suggested"]


def test_etiquetas_compactas_y_sueltas():
    assert X._etiquetas([1, 2, 3, 4, 5, 6, 7]) == "P01-P07 (Jan 1 – May 27)"
    assert X._etiquetas([8]) == "P08 (May 28 – Jun 17)"
    assert X._etiquetas([]) == "none"
