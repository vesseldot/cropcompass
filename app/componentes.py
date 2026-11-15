"""Piezas HTML de la interfaz (DESIGN.md §6.4-6.6). Funciones puras: datos -> cadena HTML, sin Streamlit.

Todo el texto llega ya traducido (el llamador usa T()); aquí solo se escapa y se maqueta.
El HTML va en una sola línea: Markdown trata las líneas con 4 espacios como bloque de código.
"""
from __future__ import annotations

from html import escape

# Iconos dibujados a mano, mismo trazo (2 px, redondeado) en una rejilla de 24 px.
ICONOS = {
    "lluvia": '<path d="M12 2.7s6 6.2 6 10.3a6 6 0 0 1-12 0c0-4.1 6-10.3 6-10.3z"/>',
    "suelo": '<path d="M3 6h18M3 12h18M3 18h18"/>',
    "calor": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "helada": '<path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "idea": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "alerta": '<path d="M12 3l10 18H2L12 3zM12 10v5M12 18h.01"/>',
}


def icono(nombre: str, tam: int = 22) -> str:
    return (f'<svg viewBox="0 0 24 24" width="{tam}" height="{tam}" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONOS[nombre]}</svg>')


def chip_metrica(nombre_icono: str, valor, etiqueta: str, ayuda: str = "", tono: str = "info") -> str:
    """Chip de métrica: icono + valor grande + etiqueta (ref-06). tono: ok | warn | risk | info."""
    return (f'<div class="chip-m" title="{escape(ayuda, quote=True)}">'
            f'<span class="chip-ico tono-{tono}">{icono(nombre_icono)}</span>'
            f'<div class="chip-val">{escape(str(valor))}</div>'
            f'<div class="chip-lbl">{escape(etiqueta)}</div></div>')


def fila_chips(chips: list[str]) -> str:
    return f'<div class="chips">{"".join(chips)}</div>'


def tarjeta_insight(texto: str) -> str:
    """Una frase en lenguaje sencillo con el hallazgo principal de la zona."""
    return f'<div class="insight">{icono("idea", 24)}<p>{escape(texto)}</p></div>'


def tono_funciono(ok: int, total: int) -> str:
    """Estado de 'funcionó X de Y años'. Siempre se acompaña de icono y texto, nunca solo color."""
    if total <= 0:
        return "warn"
    razon = ok / total
    return "ok" if razon >= 5 / 6 else "warn" if razon >= 0.5 else "risk"


def chip_estado(texto: str, tono: str) -> str:
    return (f'<span class="chip-estado tono-{tono}">'
            f'{icono("check" if tono == "ok" else "alerta", 14)}{escape(texto)}</span>')


def puntaje_grande(puntaje: float, delta: str | None = None) -> str:
    extra = f'<div class="score-delta">{escape(delta)}</div>' if delta else ""
    return (f'<div class="score"><span class="score-num">{puntaje:.0f}</span>'
            f'<span class="score-max">/100</span></div>{extra}')


def barra_apilada(partes: list[tuple[str, float, str, str]]) -> str:
    """Barra apilada del desglose. partes = [(nombre ya traducido, puntos, color, ayuda)].

    Los puntos suman el puntaje (0-100): el ancho de cada tramo es su contribución.
    Debajo va una leyenda con nombre y puntos, para no depender solo del color.
    """
    tramos = "".join(
        f'<span style="width:{max(p, 0):.1f}%;background:{c}" title="{escape(a, quote=True)}"></span>'
        for _, p, c, a in partes)
    leyenda = "".join(
        f'<span class="ley"><i style="background:{c}"></i>{escape(n)} <b>{max(p, 0):.0f}</b></span>'
        for n, p, c, _ in partes)
    return f'<div class="apilada">{tramos}</div><div class="leyenda">{leyenda}</div>'
