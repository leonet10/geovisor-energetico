"""Configuración central: rutas de datos, catálogo de tecnologías y paleta."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# El Excel puede vivir en el repo (por defecto) o en una URL pública, por ejemplo el enlace "raw"
# de GitHub. Así se actualizan los datos sin volver a desplegar el código.
RUTA_DATOS = os.getenv("GEOVISOR_DATOS", str(RAIZ / "data" / "geovisor_datos.xlsx"))
RUTA_GEOJSON = os.getenv("GEOVISOR_GEOJSON", str(RAIZ / "data" / "municipios.geojson"))

RECURSOS = ["Todos", "Solar", "Viento", "Geotermia"]
COLOR = {"Todos": "#EA4335", "Solar": "#B87E00", "Viento": "#2B6CD4", "Geotermia": "#C2461F"}
ICONO = {"Todos": "grid", "Solar": "sol", "Viento": "viento", "Geotermia": "llama"}

# Parámetros que el usuario ajusta en el panel, por tecnología.
# (clave, etiqueta, valor por defecto, unidad, mínimo, máximo, paso, grupo)
#  grupo "dim" = Dimensionamiento, "esp" = Especificaciones
PARAMETROS = {
    "fv": [
        ("n_paneles", "Paneles", 182, "und", 1, 1_000_000, 1, "dim"),
        ("wp_panel", "Potencia por panel", 550, "Wp", 50, 1000, 10, "dim"),
        ("area_panel", "Área por panel", 2.58, "m²", 0.5, 4, 0.01, "dim"),
        ("pr", "Performance ratio", 0.80, "", 0.5, 0.95, 0.01, "esp"),
    ],
    "colector": [
        ("area", "Área de colectores", 10, "m²", 1, 100_000, 1, "dim"),
        ("t_uso", "Temperatura de uso", 60, "°C", 25, 120, 1, "dim"),
        ("eta0", "Eficiencia óptica η0", 0.75, "", 0.4, 0.9, 0.01, "esp"),
        ("a1", "Pérdidas térmicas a1", 3.5, "W/m²·K", 0.5, 10, 0.1, "esp"),
    ],
    "eolico_grande": [
        ("n_turbinas", "Turbinas", 1, "und", 1, 500, 1, "dim"),
        ("p_nominal", "Potencia nominal", 2000, "kW", 500, 8000, 50, "dim"),
        ("buje", "Altura del buje", 80, "m", 30, 200, 1, "dim"),
        ("rotor", "Diámetro del rotor", 90, "m", 30, 220, 1, "dim"),
        ("perdidas", "Pérdidas", 12, "%", 0, 40, 1, "esp"),
        ("alfa", "Cizalladura α", 0.14, "", 0.05, 0.4, 0.01, "esp"),
    ],
    "eolico_pequeno": [
        ("n_turbinas", "Turbinas", 1, "und", 1, 100, 1, "dim"),
        ("p_nominal", "Potencia nominal", 10, "kW", 1, 100, 1, "dim"),
        ("buje", "Altura del buje", 20, "m", 6, 50, 1, "dim"),
        ("rotor", "Diámetro del rotor", 7, "m", 1, 30, 0.5, "dim"),
        ("perdidas", "Pérdidas", 15, "%", 0, 40, 1, "esp"),
        ("alfa", "Cizalladura α", 0.20, "", 0.05, 0.4, 0.01, "esp"),
    ],
    "geo_binaria": [
        ("p_mwe", "Potencia instalada", 5, "MWe", 0.5, 200, 0.5, "dim"),
        ("t_recurso", "Temperatura del recurso", 150, "°C", 50, 350, 5, "dim"),
        ("fp", "Factor de planta", 85, "%", 50, 98, 1, "esp"),
        ("aux", "Consumo auxiliar", 10, "%", 0, 30, 1, "esp"),
    ],
    "geo_flash": [
        ("p_mwe", "Potencia instalada", 20, "MWe", 1, 300, 1, "dim"),
        ("t_recurso", "Temperatura del recurso", 230, "°C", 100, 350, 5, "dim"),
        ("fp", "Factor de planta", 85, "%", 50, 98, 1, "esp"),
        ("aux", "Consumo auxiliar", 6, "%", 0, 30, 1, "esp"),
    ],
}

MESES = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
