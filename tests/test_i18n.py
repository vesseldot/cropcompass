"""Pruebas de core/i18n.py: todo texto visible tiene traducción y las plantillas conservan sus marcadores."""
import ast
import re
from pathlib import Path

import pytest

from core import explicacion as X
from core import i18n
from core import rotaciones as R
from tests.test_rotaciones import CULTIVOS, ROTS, _serie, _zonas

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS = [RAIZ / "app" / "streamlit_app.py", RAIZ / "core" / "explicacion.py"]


def _literales_T(ruta: Path) -> set[str]:
    """Textos literales pasados a T("...") en un archivo (las cadenas concatenadas cuentan como una)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return {n.args[0].value for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "T"
            and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)}


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda r: r.name)
def test_todo_texto_de_T_tiene_traduccion(ruta):
    faltan = sorted(_literales_T(ruta) - set(i18n.ES))
    assert faltan == [], f"Sin traducción al español en {ruta.name}: {faltan}"


def test_vocabulario_dinamico_tiene_traduccion():
    """Textos que llegan a T() desde variables: criterios, factores, tipos de año, modelos, secciones."""
    from core.aptitud import FACTORES
    from core.indicadores import TIPOS_ANIO
    dinamicos = [*X.NOMBRE_CRITERIO.values(), *[v for par in X.CAMBIO_CRITERIO.values() for v in par],
                 *FACTORES, *TIPOS_ANIO, "unknown", X.DISCLAIMER, X.GAP_HIPOTESIS, X.FUENTES,
                 "Climate fit", "Water saving", "Soil health", "Income",
                 "Evidence", "Benefits", "Risks", "Information gaps",
                 "Zone default", "Irrigated", "Rainfed", "Seasonal naive (baseline)",
                 "Rainfall (mm per 21 days)", "NDVI (vegetation greenness)", "Prophet 80% interval",
                 "± 80th percentile of the model's test error"]
    assert [t for t in dinamicos if t not in i18n.ES] == []


def test_plantillas_conservan_los_mismos_marcadores():
    marcadores = lambda s: sorted(re.findall(r"(?<!\{)\{(\w+)[^{}]*\}(?!\})", s))
    distintos = {en: es for en, es in i18n.ES.items() if marcadores(en) != marcadores(es)}
    assert distintos == {}


def test_tr_y_fechas():
    assert i18n.tr("dry", "es") == "seco" and i18n.tr("dry", "en") == "dry"
    assert i18n.tr("texto sin traducción", "es") == "texto sin traducción"      # nunca falla
    assert i18n.fechas("P08 (May 28 – Jun 17)", "es") == "P08 (28 may – 17 jun)"
    assert i18n.fechas("P08 (May 28 – Jun 17)", "en") == "P08 (May 28 – Jun 17)"
    assert i18n.fechas("P01-P07 (Jan 1 – May 27)", "es") == "P01-P07 (1 ene – 27 may)"


def test_bloques_en_ambos_idiomas():
    for nombre, textos in i18n.BLOQUES.items():
        assert textos["en"].strip() and textos["es"].strip(), nombre
        assert textos["en"] != textos["es"], nombre


def test_explicacion_en_espanol_mismos_numeros_sin_ingles():
    serie = _serie(tmax=lambda a, p: 12.0 if a == 2022 else 30.0,
                   precip=lambda a, p: {2022: 10.0, 2023: 20.0}.get(a, 60.0 + a - 2020))
    kw = dict(serie=serie, cultivos=CULTIVOS, rotaciones=ROTS, zonas=_zonas())
    en = X.explicar_ranking(R.rankear("z", None, **kw), idioma="en")[0]["explicacion"]
    es = X.explicar_ranking(R.rankear("z", None, **kw), idioma="es")[0]["explicacion"]
    plano = lambda e: " ".join([e["why_suggested"], *e["evidence"], *e["benefits"], *e["risks"],
                                *e["information_gaps"], e["disclaimer"]])
    assert "Falló en 2022 (año seco)" in plano(es) and "limitado por temperatura" in plano(es)
    assert es["disclaimer"] == "Esta herramienta apoya, no sustituye, el criterio del agricultor."
    assert re.findall(r"\d+(?:\.\d+)?", plano(en)) == re.findall(r"\d+(?:\.\d+)?", plano(es))   # mismos números
    for resto in ("Worked in", "Failed in", "limited by", "Ranked", "suitability", "rotation"):
        assert resto not in plano(es), resto
    assert [len(en[k]) for k in ("evidence", "benefits", "risks", "information_gaps")] == \
           [len(es[k]) for k in ("evidence", "benefits", "risks", "information_gaps")]
