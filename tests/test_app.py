"""Prueba de humo de la interfaz: corre app/streamlit_app.py sin navegador (streamlit AppTest)
para las 3 zonas, pesos extremos, modo sin riego, español, modo oscuro y modo guía.
Falla si hay excepciones o avisos de error."""
import pytest
from streamlit.testing.v1 import AppTest

APP = "app/streamlit_app.py"
# Aviso de zona de Cuautla (es información, no error), en inglés y en español
AVISOS_ESPERADOS = ("MERRA-2 cell elevation", "La celda de MERRA-2")


def _correr(zona="axochiapan", riego="default", pesos=(5, 5, 5, 5), idioma="English", oscuro=False, guia=False):
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    cod = {"English": "en", "Español": "es"}[idioma]
    if idioma != "English":
        at.selectbox(key="idioma").set_value(idioma)
        at.run()
    if oscuro:
        at.toggle(key=f"oscuro_{cod}").set_value(True)
    if guia:
        at.toggle(key=f"guia_{cod}").set_value(True)
    at.selectbox(key=f"zona_{cod}").set_value(zona)
    at.radio(key=f"riego_{cod}").set_value(riego)
    for clave, valor in zip(("w_agua", "w_suelo", "w_ingreso", "w_clima"), pesos):
        at.slider(key=f"{clave}_{cod}").set_value(valor)
    next(b for b in at.button if b.label in ("Analyze", "Analizar")).click()
    at.run()
    return at


def _problemas(at):
    avisos = [w.value for w in at.warning if not any(a in w.value for a in AVISOS_ESPERADOS)]
    return [str(e.value) for e in at.exception] + avisos + [e.value for e in at.error]


def _textos(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info])


@pytest.fixture(autouse=True)
def _tema_claro():
    """El modo oscuro cambia una opción global de Streamlit: se restaura después de cada prueba."""
    yield
    from streamlit import config
    config.set_option("theme.base", "light")


@pytest.mark.parametrize("zona", ["zacatepec", "cuautla", "axochiapan"])
def test_app_corre_en_cada_zona(zona):
    at = _correr(zona)
    assert _problemas(at) == []
    assert at.title[0].value.endswith("CropCompass")
    assert len(at.tabs) == 4


@pytest.mark.parametrize("pesos,riego", [((10, 0, 0, 0), "default"), ((0, 0, 10, 0), "rainfed"),
                                         ((0, 0, 0, 0), "irrigated")])
def test_app_pesos_extremos_y_sin_riego(pesos, riego):
    at = _correr("zacatepec", riego=riego, pesos=pesos)
    assert _problemas(at) == []


@pytest.mark.parametrize("zona", ["zacatepec", "cuautla", "axochiapan"])
def test_app_en_espanol(zona):
    at = _correr(zona, idioma="Español")
    assert _problemas(at) == []
    texto = _textos(at)
    assert "Funcionó en" in texto and "rotaciones candidatas" in texto
    assert "Esta herramienta apoya, no sustituye, el criterio del agricultor." in texto
    assert "Worked in" not in texto and "candidate rotations" not in texto     # sin restos en inglés
    assert [t.label for t in at.tabs] == ["Diagnóstico", "Pronóstico", "Rotaciones", "Datos y método"]


def test_cambiar_idioma_conserva_la_seleccion():
    at = _correr("cuautla", riego="rainfed", pesos=(9, 1, 2, 3))
    at.selectbox(key="idioma").set_value("Español")
    at.run()
    assert at.selectbox(key="zona_es").value == "cuautla"
    assert at.radio(key="riego_es").value == "rainfed"
    assert at.slider(key="w_agua_es").value == 9
    assert _problemas(at) == []


@pytest.mark.parametrize("idioma", ["English", "Español"])
def test_app_modo_oscuro_y_guia(idioma):
    at = _correr("axochiapan", idioma=idioma, oscuro=True, guia=True)
    assert _problemas(at) == []
    guia = "Guide: how to use CropCompass" if idioma == "English" else "Guía: cómo usar CropCompass"
    assert guia in _textos(at)
    from streamlit import config
    assert config.get_option("theme.base") == "dark"


def test_cambiar_de_tema_conserva_la_zona_elegida():
    at = _correr("cuautla", riego="rainfed")
    at.toggle(key="oscuro_en").set_value(True)
    at.run()
    assert at.selectbox(key="zona_en").value == "cuautla"
    assert at.radio(key="riego_en").value == "rainfed"
    assert any("**Cuautla**" in c.value for c in at.caption)      # el análisis sigue siendo de Cuautla
    assert _problemas(at) == []


def test_sin_modo_guia_no_hay_notas():
    assert "Guide: how to use CropCompass" not in _textos(_correr("axochiapan"))
