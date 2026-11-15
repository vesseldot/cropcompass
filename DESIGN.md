# DESIGN.md — Dirección visual (Field Shift · Morelos)

> Fuente de verdad visual del proyecto. Impeccable y frontend-design deben leer este archivo antes de tocar UI.
> Referencias en `docs/design-refs/` (inspiración: no copiar marcas, textos ni datos de esas imágenes).

## 1. Idea central
**"El campo de Morelos visto desde el satélite, con la información flotando encima."**
El mapa satelital es el protagonista y ocupa la pantalla. Paneles claros semitransparentes flotan sobre él.
Las parcelas analizadas se resaltan con contorno ámbar, como en `ref-01` y `ref-04`.
Modo: **Operate** (herramienta de decisión): claridad y escaneo por encima de lo decorativo.

## 2. Referencias y qué tomar de cada una
| Archivo | Qué tomar | Qué NO tomar |
|---|---|---|
| ref-01-mobile-fields.jpg | Parcelas con contorno ámbar sobre satélite, botones flotantes redondeados, hoja inferior con buscador y tarjeta de parcela | Marcas o nombres de ejemplo |
| ref-02-crop-labels.jpg | Etiquetas de cultivo sobre cada parcela (icono + nombre + dato clave) | El estilo 3D de video |
| ref-03-big-numbers.jpg | Cifras grandes y en negrita sobre la imagen para los datos clave | Datos de maquinaria |
| ref-04-land-panel.jpg | Panel lateral izquierdo con tarjetas y mapa a la derecha; marcadores circulares claros | Precios y ventas |
| ref-05-field-markers.jpg | Marcadores tipo pin con icono; panel de detalle flotante a la derecha | Datos personales del perfil |
| ref-06-dark-dashboard.jpg | Tarjetas de "insights", índice de estrés con barra de color, parcela seleccionada con contorno punteado | El modo oscuro completo (solo como alternativa) |
| ref-07-glass-panel.jpg | Panel con fondo difuminado, jerarquía tipográfica limpia, un único botón de acción de color fuerte | El contenido turístico |
| ref-08-map-pins.jpg | Pines con etiqueta y línea conectora para nombrar zonas | El estilo ilustrado 3D |

## 3. Paleta (tokens)
| Token | Hex | Uso |
|---|---|---|
| `--forest-900` | `#1C2A1E` | Texto principal sobre claro, fondos oscuros |
| `--forest-700` | `#2F4A32` | Encabezados, iconos |
| `--field-amber` | `#E8B53A` | Contorno y relleno (25 %) de parcelas analizadas |
| `--action-orange` | `#EF6A2A` | **Único** color de acción (botón "Analyze", CTA). Máximo 1 por pantalla |
| `--sky-blue` | `#1F5FA8` | Marcadores de datos / enlaces |
| `--panel` | `rgba(250,250,246,0.88)` | Paneles flotantes (con `backdrop-filter: blur(12px)`) |
| `--muted` | `#6B7266` | Texto secundario |
| `--ok` / `--warn` / `--risk` | `#3E8E4E` / `#D9A21B` / `#C2452D` | Estado. **Siempre con icono o texto**, nunca solo color |
| `--line` | `rgba(28,42,30,0.12)` | Bordes y separadores |

## 4. Tipografía
- Familia: **Inter** (Google Fonts) con respaldo `system-ui, sans-serif`.
- Escala: cifras clave 40–56 px peso 800 · títulos 22–28 px peso 700 · cuerpo 15–16 px peso 400 · etiquetas 12–13 px peso 600 en mayúsculas con espaciado 0.06em (como "RIVERSIDE, CALIFORNIA · 8 FIELDS" en ref-01).
- Números con `font-variant-numeric: tabular-nums`.

## 5. Forma y profundidad
- Radios: paneles 20 px · tarjetas 16 px · botones e inputs 12 px · botones de mapa 12 px cuadrados.
- Sombra paneles: `0 8px 32px rgba(0,0,0,0.18)`. Sin sombras en tarjetas internas (solo borde `--line`).
- Espaciado base 8 px (8/16/24/32).

## 6. Componentes
1. **Mapa héroe**: satélite (Esri World Imagery, con su atribución), alto ~70 vh, ancho completo.
   Zonas como polígonos con contorno `--field-amber` 2 px y relleno 25 %. La zona seleccionada con contorno punteado.
   Etiqueta flotante por zona: icono de cultivo + nombre + "worked X/6 yrs" (ref-02).
2. **Panel flotante de análisis** (izquierda, sobre el mapa, ref-04/07): selector de zona, cultivo actual,
   sliders de prioridades, botón naranja "Analyze".
3. **Hoja de resultados** (debajo del mapa, ref-01): pestañas Diagnosis / Forecast / Rotations / Data & Method.
4. **Tarjeta de rotación**: nombre, puntaje grande, chip "Worked in 5 of 6 years", barra apilada del desglose
   (clima/agua/suelo/ingreso), expander con Why / Evidence / Risks / Gaps.
5. **Chips de métricas** (ref-06): icono + valor grande + etiqueta: bare-soil periods, frost periods, heat periods, dry spell.
6. **Tarjeta de insight** (ref-06): una frase en lenguaje sencillo con el hallazgo principal de la zona.
7. **Aviso fijo**: "This tool supports, not replaces, farmer judgment" (discreto, al pie del panel).

## 7. Restricciones técnicas (Streamlit)
- No cambiar de framework. Usar `st.set_page_config(layout="wide", initial_sidebar_state="collapsed")`.
- Mapa con `st.pydeck_chart`: `TileLayer` de Esri World Imagery + `PolygonLayer` + `TextLayer`/`IconLayer`.
- Estilos con **un solo** bloque CSS en `app/estilos.css` cargado con `st.markdown(..., unsafe_allow_html=True)`.
- Para paneles flotantes usar `st.container(key="panel_analisis")` y apuntar a la clase `.st-key-panel_analisis` en CSS.
- Ocultar el menú y pie de Streamlit por CSS. Tema base en `.streamlit/config.toml`.
- Nada de JavaScript propio ni componentes de terceros nuevos sin preguntar.

## 8. Reglas
- Funcional antes que bonito: **ninguna** mejora visual puede romper un flujo o cambiar cálculos de `core/`.
- Todo texto visible en inglés. Contraste WCAG AA mínimo (texto sobre `--panel` y sobre satélite con sombra o fondo).
- Sin logos de NASA ni de Space Apps. Atribución de imágenes satelitales visible.
- Animaciones: solo transiciones suaves de 150–250 ms en hover y aparición de tarjetas. Nada que distraiga en la demo.
