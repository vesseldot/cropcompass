"""Descarga MODIS MOD13Q1 (NDVI + pixel_reliability) desde la API ORNL DAAC para las zonas.

Guarda cada respuesta JSON tal cual (dato crudo) en OUT_DIR. Es reanudable: salta lo ya descargado.
Uso: python -I bajar_ndvi_ornl.py <out_dir>
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ZONAS = {  # de resumen.json (repo satelitacos)
    "zacatepec": (18.655, -99.19),
    "cuautla": (18.81, -98.95),
    "axochiapan": (18.50, -98.75),
}
BANDAS = ["250m_16_days_NDVI", "250m_16_days_pixel_reliability"]
KM = 1  # ventana de ±1 km -> ~9x9 píxeles de 231 m
BASE = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"

# MOD13Q1 (Terra) compone cada 16 días empezando el DOY 001: 001, 017, ..., 353 (23 por año).
# Se agrega un compuesto antes (A2019353) y uno después (A2026001) para interpolar los bordes.
FECHAS = ["A2019353"] + [f"A{y}{d:03d}" for y in range(2020, 2026) for d in range(1, 366, 16)] + ["A2026001"]
TROZOS = [FECHAS[i:i + 10] for i in range(0, len(FECHAS), 10)]  # la API admite 10 fechas por petición

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()


def log(msg):
    with lock:
        print(time.strftime("%H:%M:%S"), msg, flush=True)


def pedir(url, intentos=6):
    espera = 15
    for i in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            log(f"   intento {i}/{intentos} falló: {e!r}; reintento en {espera}s")
            time.sleep(espera)
            espera *= 2
    return None


def zona_worker(zona, lat, lon):
    for banda in BANDAS:
        for trozo in TROZOS:
            f = out / f"{zona}__{banda}__{trozo[0]}_{trozo[-1]}.json"
            if f.exists():
                continue
            url = (f"{BASE}?latitude={lat}&longitude={lon}&band={banda}"
                   f"&startDate={trozo[0]}&endDate={trozo[-1]}&kmAboveBelow={KM}&kmLeftRight={KM}")
            t0 = time.time()
            data = pedir(url)
            if data is None:
                log(f"FALLO definitivo {f.name}")
                continue
            f.write_text(json.dumps(data), encoding="utf-8")
            n = len(data.get("subset", []))
            log(f"ok {f.name} ({n} fechas, {time.time() - t0:.0f}s)")


hilos = [threading.Thread(target=zona_worker, args=(z, *ll)) for z, ll in ZONAS.items()]
for h in hilos:
    h.start()
for h in hilos:
    h.join()

total = len(ZONAS) * len(BANDAS) * len(TROZOS)
hechos = len(list(out.glob("*.json")))
log(f"TERMINADO: {hechos}/{total} archivos en {out}")
