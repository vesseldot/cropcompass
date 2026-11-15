# CLAUDE.md — Contexto del proyecto (léelo antes de cada tarea)

## Qué es
Prototipo para **NASA Space Apps 2026**, reto **"Field Shift: Adapting Farms with NASA Data"**.
Herramienta de **apoyo a la decisión** para agricultores de **Morelos, México** (zonas cañeras).
El usuario elige una zona, su cultivo actual y sus prioridades (agua, suelo, ingreso); la app:
1. muestra el **diagnóstico** de la zona (clima 2020–2025 en periodos de 21 días: suelo desnudo, heladas, calor, rachas secas);
2. **pronostica** lluvia y NDVI de los próximos 17 periodos de 21 días (1 año) con series de tiempo integradas;
3. **compara al menos 3 rotaciones** (incluida la actual) con puntaje explicable y "funcionó en X de 6 años";
4. explica por qué, con qué evidencia, qué riesgos y qué falta validar. **Apoya, no sustituye** al agricultor ni al agrónomo.

## Prioridades (en este orden)
1. **Funcional y terminado** de punta a punta. 2. Explicable. 3. Visual (secundario).
Entrega: **domingo 15 nov 2026, 11:59 p. m.** Congelar funciones el domingo a la 1 p. m.

## Stack (no cambiar sin preguntar)
- Python 3.11 · pandas · numpy · scikit-learn · prophet · plotly · streamlit
- Backend = paquete `core/` (lógica pura, sin Streamlit). Frontend = `app/` (Streamlit, diseño por defecto).
- Sin GPU, sin servicios de pago, sin bases de datos: archivos CSV/JSON en `data/`.
- Todo el texto visible de la app y el README **en inglés** (requisito del concurso). Comentarios de código en español está bien.

## Estructura
```
data/raw/            # descargas originales (no se editan)
data/clean/          # datasets limpios (contrato abajo)
data/config/         # zonas.json, cultivos.json, rotaciones.json
data/processed/      # serie_21d.csv (tabla integrada) y salidas de modelos
core/
  datos.py           # carga + validación del contrato de datos
  periodos.py        # calendario de 17 periodos de 21 días + tabla integrada serie_21d
  indicadores.py     # indicadores agroclimáticos y de NDVI
  pronostico.py      # Prophet / baselines / ventana deslizante + métricas
  agrupamiento.py    # k-means de zonas por estacionalidad
  aptitud.py         # aptitud difusa tipo EcoCrop por cultivo y periodo
  rotaciones.py      # puntaje (suma ponderada) + backtesting por año
  explicacion.py     # textos: por qué, evidencia, riesgos, vacíos
app/streamlit_app.py # interfaz
tests/               # pytest con datos pequeños
notebooks/           # exploración (opcional)
```

## Unidad de análisis: PERIODOS DE 21 DÍAS
- Cada año se divide en **17 periodos fijos** anclados al 1 de enero: el periodo k empieza el día
  `1 + 21*(k-1)` del año; el **periodo 17 absorbe el resto** (días 337–365/366, ~29–30 días).
  Así el periodo 8 de 2021 es comparable con el periodo 8 de 2024 (estacionalidad = 17 periodos).
- Etiqueta legible por periodo: `P08 (May 28 – Jun 17)`.
- Los cultivos se definen en meses en `cultivos.json`; convertir: `ciclo_periodos = round(ciclo_meses * 30.44 / 21)`
  y `siembra_mes` → periodo que contiene el día 1 de ese mes.
- Lo mensual solo se usa para resúmenes visuales; **todo cálculo y pronóstico usa periodos de 21 días**.

## Contrato de datos limpios (`data/clean/`)
Entradas (como existan; adaptar nombres en `core/datos.py`):
- `clima_diario.csv`: `zona, fecha, precip_mm, tmax_c, tmin_c` (precip = IMERG; respaldo POWER)
- `ndvi.csv`: `zona, fecha, ndvi (0–1, ya escalado), calidad (0 bueno … 3 nube; opcional)` — compuestos de 16 días
Valores faltantes = NaN. Nunca −999 ni −3000 en `clean/`.

Tabla integrada que genera el código (`data/processed/serie_21d.csv`), una fila por `zona × año × periodo`:
`zona, anio, periodo (1–17), fecha_inicio, fecha_fin, n_dias, precip_mm, dias_lluvia (>=1 mm),
racha_seca_max, tmax_media, tmin_media, tmin_min, dias_helada (tmin<=2), dias_calor (tmax>=35),
ndvi, ndvi_obs (n.º de observaciones reales de NDVI en el periodo), ndvi_interpolado (bool)`
- NDVI: quitar calidad==3, **interpolar linealmente a diario** entre compuestos y promediar por periodo
  (los compuestos son cada 16 días, no coinciden con 21); `ndvi_obs` dice cuánto es dato real.

## Reglas de trabajo
- Antes de programar, **mostrar el plan** y esperar confirmación si cambia la estructura.
- Cada módulo de `core/` con **pruebas** en `tests/` y funciones puras (entrada → salida).
- Atributos de cultivos = **hipótesis por validar**; marcarlos así en la UI.
- Pronósticos: **split temporal** (el último 20 % de los periodos es prueba), **nunca aleatorio ni estratificado**.
  Reportar MAE (métrica principal), RMSE y R² y **compararlos contra un baseline** (estacional ingenuo:
  "igual que el mismo periodo del año pasado"). R² de lluvia es inestable en secas: no usarlo solo.
- No inventar datos. Si falta algo, decirlo en la UI ("No data").
- Commits pequeños y frecuentes con mensajes claros.
