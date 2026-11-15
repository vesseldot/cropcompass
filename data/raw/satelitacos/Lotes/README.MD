Análisis Agroclimático y Auditoría Técnica de Datos — Morelos (2020–2025)

Este documento consolida el análisis meteorológico, estadístico y técnico del lote de datos del proyecto para las zonas agrícolas de Zacatepec (caña de azúcar), Cuautla (sorgo / maíz) y Axochiapan (sorgo de temporal) en el estado de Morelos, abarcando el periodo comprendido del 1 de enero de 2020 al 31 de diciembre de 2025.

1. Inventario, Integridad y Auditoría Técnica del Lote

La revisión de los $13$ archivos del flujo de trabajo permitió verificar la calidad de las series meteorológicas e identificar inconsistencias operativas en las capas satelitales y de documentación:

Series meteorológicas crudos (POWER_Point_Daily_*_UTC.csv y *_UTC_2.csv):

Cada archivo contiene $2,192$ registros diarios completos ($2020\text{--}2025$, incluyendo los años bisiestos $2020$ y $2024$) sin datos faltantes (-999 o NaN $= 0$ en todas las variables).

Los tres archivos con sufijo *_UTC_2.csv son copias idénticas de los archivos *_UTC.csv originales (mismas coordenadas, elevación de celda MERRA-2 y registros diarios).

Tablas procesadas diarias y mensuales (*_power.csv y *_mensual.csv):

Se incluyen las series limpias diarias ($2,192$ filas) y agregadas mensuales ($72$ filas) de Cuautla y Axochiapan. En el lote base faltan zacatepec_power.csv y zacatepec_mensual.csv, aunque sus métricas sí fueron procesadas e integradas en resumen.json y graficas.png.

Los archivos *_power.csv provienen de una consulta en Hora Solar Local (LST), mientras que los archivos crudos *_UTC.csv están indexados en Tiempo Universal Coordinado (UTC). Este desfase de $6\text{ horas}$ genera variaciones mínimas en el reparto diario de tormentas nocturnas ($\le 0.1\text{ mm}$ en el acumulado anual) sin alterar los conteos de días extremos.

Comparación entre IMERG_PRECTOT y PRECTOTCORR:

El pipeline utiliza PRECTOTCORR (precipitación corregida por sesgo). Respecto a IMERG_PRECTOT (estimación satelital cruda), PRECTOTCORR atenúa los picos diarios extremos (reduciendo los máximos de $75.5\text{--}82.1\text{ mm/día}$ a $27.2\text{--}36.4\text{ mm/día}$) y aplica una reducción anual promedio de $\approx 13\%$ en Cuautla ($827.5$ frente a $951.8\text{ mm/año}$) y $\approx 14\%$ en Axochiapan ($810.5$ frente a $945.2\text{ mm/año}$), mientras que en Zacatepec el promedio anual permanece prácticamente invariable ($944.2$ frente a $944.8\text{ mm/año}$).

Fallos de integración satelital y documentación (resumen.json, graficas.png, DATASETS.MD):

Vegetación (MODIS MOD13Q1): La consulta a la API de ORNL DAAC falló en las tres localidades con el código 502 Server Error: Proxy Error, dejando vacío el tercer panel de graficas.png (donde solo se dibuja la línea base punteada en $0.3$).

Topografía (SRTM): El módulo de elevación se omitió en las tres zonas debido a la ausencia de la variable de entorno OPENTOPO_KEY.

Documentación (DATASETS.MD): Conserva únicamente el encabezado genérico # NEW DATASET / Default datasets sin especificar el esquema ni las fuentes de datos.

2. Estadísticas Descriptivas Diarias (2020–2025, $n = 2,192$ días)

Zona (Coordenadas / Elev. MERRA-2)

Variable

Media

Mediana

Mínimo

Máximo

Desv. Est.

Zacatepec ($18.655^\circ\text{ N}, -99.19^\circ\text{ W}$, $1,355.9\text{ m}$)

T2M_MAX ($^\circ\text{C}$)

$29.95$

$29.11$

$21.47$

$39.43$

$3.67$

Cultivo: Caña de azúcar

T2M_MIN ($^\circ\text{C}$)

$16.53$

$16.93$

$7.00$

$23.00$

$2.53$



PRECTOTCORR ($\text{mm/día}$)

$2.58$

$0.19$

$0.00$

$36.37$

$4.55$



IMERG_PRECTOT ($\text{mm/día}$)

$2.59$

$0.00$

$0.00$

$75.50$

$6.60$

Cuautla ($18.81^\circ\text{ N}, -98.95^\circ\text{ W}$, $2,120.0\text{ m}$)

T2M_MAX ($^\circ\text{C}$)

$25.86$

$25.34$

$15.68$

$35.09$

$3.32$

Cultivo: Sorgo / maíz

T2M_MIN ($^\circ\text{C}$)

$11.75$

$12.10$

$3.76$

$17.96$

$2.53$



PRECTOTCORR ($\text{mm/día}$)

$2.27$

$0.40$

$0.00$

$27.24$

$3.92$



IMERG_PRECTOT ($\text{mm/día}$)

$2.61$

$0.00$

$0.00$

$82.11$

$6.24$

Axochiapan ($18.50^\circ\text{ N}, -98.75^\circ\text{ W}$, $1,396.8\text{ m}$)

T2M_MAX ($^\circ\text{C}$)

$30.40$

$29.96$

$21.83$

$39.45$

$3.38$

Cultivo: Sorgo de temporal

T2M_MIN ($^\circ\text{C}$)

$16.07$

$16.35$

$6.43$

$23.15$

$2.63$



PRECTOTCORR ($\text{mm/día}$)

$2.22$

$0.21$

$0.00$

$28.93$

$4.12$



IMERG_PRECTOT ($\text{mm/día}$)

$2.59$

$0.00$

$0.00$

$81.63$

$6.80$

3. Comportamiento Interanual (2020–2025)

Año

Zacatepec Lluvia ($\text{mm}$)

Zacatepec Calor ($\ge 35^\circ\text{C}$)

Cuautla Lluvia ($\text{mm}$)

Cuautla Calor ($\ge 35^\circ\text{C}$)

Axochiapan Lluvia ($\text{mm}$)

Axochiapan Calor ($\ge 35^\circ\text{C}$)

Racha seca máx. jun–sep ($\text{días}$)

2020

$845.1$

$52$

$758.2$

$0$

$774.3$

$46$

$4\text{--}5$

2021

$1,032.8$

$17$

$944.1$

$0$

$915.3$

$14$

$3\text{--}5$

2022

$896.1$

$42$

$662.6$

$0$

$678.7$

$39$

$2$

2023

$757.4$

$38$

$661.1$

$0$

$668.1$

$36$

$26\text{--}28$

2024

$998.0$

$93$

$876.9$

$1$

$807.8$

$84$

$8$

2025

$1,136.0$

$45$

$1,082.0$

$0$

$1,018.7$

$42$

$3\text{--}5$

4. Interpretación Agroclimática y Patrones Clave

A. Efecto de Altitud de Celda y Piso Térmico

La celda de reanálisis MERRA-2 correspondiente a Cuautla presenta una altitud media de $2,120.01\text{ m}$ (debido a que su resolución espacial de $0.5^\circ \times 0.625^\circ$ abarca parte del gradiente altitudinal volcánico al norte), situándola aproximadamente $4.1^\circ\text{C}$ en $T_{\max}$ y $4.5^\circ\text{C}$ en $T_{\min}$ por debajo de Zacatepec ($1,355.9\text{ m}$) y Axochiapan ($1,396.8\text{ m}$).

Este diferencial térmico protege a Cuautla frente a episodios de calor extremo ($\ge 35^\circ\text{C}$): en todo el sexenio solo registró $1\text{ día}$ por encima de ese umbral ($35.09^\circ\text{C}$ en 2024). En contraste, durante la intensa ola de calor de 2024, Zacatepec acumuló $93\text{ días}$ y Axochiapan $84\text{ días}$ con temperaturas máximas $\ge 35^\circ\text{C}$, duplicando su promedio habitual y elevando la demanda evapotranspirativa de los cultivos.

B. Sincronía Regional y Anomalía Hídrica de 2023

Las tres localidades exhiben una fuerte coherencia climática diaria, con coeficientes de correlación de Pearson entre $r = 0.934$ y $r = 0.971$ para temperatura y entre $r = 0.884$ y $r = 0.959$ para precipitación.

El año 2023 representó el mínimo pluviométrico del periodo en las tres regiones ($757.4\text{ mm}$ en Zacatepec, $661.1\text{ mm}$ en Cuautla y $668.1\text{ mm}$ en Axochiapan), agravado por una canícula severa de $26\text{ a }28\text{ días}$ consecutivos sin lluvia entre junio y septiembre (frente a rachas secas normales de $2\text{ a }8\text{ días}$ en el resto de los años). Este déficit intraestival constituye el principal factor de riesgo hídrico para el sorgo de temporal en Axochiapan.

Por el contrario, 2025 registró el máximo acumulado anual de lluvia en las tres zonas ($1,136.0\text{ mm}$ en Zacatepec, $1,082.0\text{ mm}$ en Cuautla y $1,018.7\text{ mm}$ en Axochiapan), con septiembre consolidado como el mes más lluvioso del ciclo anual ($175.5\text{--}213.6\text{ mm}$ en promedio).

C. Amplitud Térmica Diurna ($\Delta T$) y Fenología de Cultivos

La oscilación térmica diaria ($\Delta T = T_{\max} - T_{\min}$) alcanza su máximo anual en marzo ($18.0\text{--}18.2^\circ\text{C}$) durante el estiaje cálido y desciende en la temporada de lluvias hasta septiembre ($8.6^\circ\text{C}$ en Zacatepec y $10.0^\circ\text{C}$ en Cuautla y Axochiapan).

En Zacatepec, el incremento de $\Delta T$ hasta $14.0\text{--}14.2^\circ\text{C}$ durante noviembre y diciembre, combinado con el descenso gradual de la humedad, favorece la maduración y acumulación de sacarosa en la caña de azúcar previo al inicio de la zafra.

D. Ausencia de Riesgo por Heladas

Ninguna de las tres zonas presentó días con temperatura mínima $\le 2.0^\circ\text{C}$ entre 2020 y 2025 ($0\text{ días}$ de helada en todo el registro). Los mínimos absolutos diarios fueron de $3.76^\circ\text{C}$ en Cuautla, $6.43^\circ\text{C}$ en Axochiapan y $7.00^\circ\text{C}$ en Zacatepec, confirmando condiciones térmicas invernales libres de daño por congelación para los cultivos evaluados.

5. Recomendaciones Técnicas para Cerrar el Pipeline

Recuperar la serie de NDVI (MODIS MOD13Q1): Incorporar reintentos con espera exponencial (exponential backoff) o consultar el producto vía NASA AppEEARS para evitar los errores 502 Proxy Error de ORNL DAAC y completar el tercer panel de graficas.png.

Integrar elevación real (SRTM): Configurar OPENTOPO_KEY para obtener la altitud puntual de cada coordenada y corregir el sesgo altitudinal de la celda gruesa de MERRA-2 en Cuautla ($2,120\text{ m}$ frente a la elevación real del valle agrícola de $\approx 1,300\text{--}1,350\text{ m}$).

Limpieza y documentación: Eliminar los archivos duplicados *_UTC_2.csv del repositorio y completar DATASETS.MD con el diccionario de variables y metadatos de las fuentes.