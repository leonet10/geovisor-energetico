"""Geovisor de recursos energéticos de Colombia.

Local:       python app.py            → http://127.0.0.1:8050
Producción:  gunicorn app:server      (lo usan Render, Docker y Hugging Face)
"""

import os

from dash import Dash

from geovisor import callbacks, componentes, config
from geovisor.datos import Datos

datos = Datos.cargar(config.RUTA_DATOS, config.RUTA_GEOJSON)

app = Dash(__name__, title="Geovisor energético de Colombia", update_title=None,
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"},
                      {"name": "description", "content": "Recurso solar, eólico y geotérmico por municipio en Colombia"}],
           external_stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"])
app.layout = componentes.pagina(datos, os.getenv("GEOVISOR_URL_EXCEL"))
callbacks.registrar(app, datos)
server = app.server                     # objeto WSGI para gunicorn

if __name__ == "__main__":
    app.run(debug=os.getenv("DASH_DEBUG", "0") == "1", host="127.0.0.1", port=int(os.getenv("PORT", 8050)))
