"""Prueba de humo de la interfaz: corre app/streamlit_app.py sin navegador (streamlit AppTest)
para las 3 zonas, pesos extremos y modo sin riego. Falla si hay excepciones o avisos de error."""
import pytest
from streamlit.testing.v1 import AppTest

APP = "app/streamlit_app.py"
AVISOS_ESPERADOS = ("MERRA-2 cell elevation",)   # aviso de zona de Cuautla (es información, no error)


def _correr(zona="axochiapan", riego="Zone default", pesos=(5, 5, 5, 5)):
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.sidebar.selectbox[0].set_value(zona)
    at.sidebar.radio[0].set_value(riego)
    for slider, valor in zip(at.sidebar.slider[:4], pesos):
        slider.set_value(valor)
    at.sidebar.button[0].click()
    at.run()
    return at


def _problemas(at):
    avisos = [w.value for w in at.warning if not any(a in w.value for a in AVISOS_ESPERADOS)]
    return [str(e.value) for e in at.exception] + avisos + [e.value for e in at.error]


@pytest.mark.parametrize("zona", ["zacatepec", "cuautla", "axochiapan"])
def test_app_corre_en_cada_zona(zona):
    at = _correr(zona)
    assert _problemas(at) == []
    assert at.title[0].value.endswith("CropCompass")
    assert len(at.tabs) == 4


@pytest.mark.parametrize("pesos,riego", [((10, 0, 0, 0), "Zone default"), ((0, 0, 10, 0), "Rainfed"),
                                         ((0, 0, 0, 0), "Irrigated")])
def test_app_pesos_extremos_y_sin_riego(pesos, riego):
    at = _correr("zacatepec", riego=riego, pesos=pesos)
    assert _problemas(at) == []
