# Geovisor de recursos energéticos de Colombia

Dashboard web que muestra el recurso **solar, eólico y geotérmico** de los 1.122 municipios de Colombia y calcula la **energía útil, el CAPEX, el OPEX y el LCOE** de seis tecnologías:

| Recurso | Tecnologías | Cobertura |
|---|---|---|
| Solar | Paneles fotovoltaicos, colector solar térmico | Todo el país |
| Viento | Aerogenerador gran escala, aerogenerador pequeño | Todo el país |
| Geotermia | Planta binaria (ORC), planta flash | Solo zona central (región Andina) |

> ⚠️ **Datos ilustrativos.** Las coordenadas y los límites municipales son del DANE (MGN 2018). Los valores de irradiación, viento e índice geotérmico son estimaciones con estructura espacial plausible, **no mediciones**. Reemplázalos con NASA POWER antes de usar los resultados en decisiones.

---

## Estructura del repositorio

```
geovisor-energetico/
├── app.py                      # Punto de entrada (Dash); expone `server` para gunicorn
├── geovisor/
│   ├── config.py               # Rutas, catálogo de parámetros y colores
│   ├── datos.py                # Lectura del Excel y la geometría
│   ├── modelos.py              # Modelos de energía y LCOE (funciones puras)
│   ├── calculo.py              # Une datos del Excel + parámetros + modelo
│   ├── componentes.py          # Interfaz: paneles, mapa, gráficos
│   └── callbacks.py            # Interacciones
├── assets/                     # CSS, JavaScript del mapa e íconos (Dash los carga solo)
├── data/
│   ├── geovisor_datos.xlsx     # ÚNICA fuente de datos del dashboard
│   └── municipios.geojson      # Límites municipales simplificados (DANE MGN 2018)
├── scripts/construir_datos.py  # Regenera el Excel y el GeoJSON desde el MGN
├── tests/                      # Pruebas de modelos y datos (pytest)
├── render.yaml                 # Despliegue en Render
├── Dockerfile                  # Despliegue en Hugging Face, Azure o cualquier Docker
└── .github/workflows/pruebas.yml  # Pruebas automáticas en cada push
```

## El Excel: `data/geovisor_datos.xlsx`

| Hoja | Contenido | ¿Se edita? |
|---|---|---|
| `Municipios` | Código DANE, nombre, latitud, longitud, región, densidad del aire, k de Weibull, índice geotérmico | Sí (celdas azules) |
| `GHI_mensual` | Irradiación media diaria por mes (kWh/m²·día) | Sí |
| `Viento_mensual` | Velocidad media del viento a 50 m por mes (m/s) | Sí |
| `Tecnologias` | CAPEX, OPEX y vida útil por tecnología | Sí (celdas amarillas) |
| `Supuestos` | Tasa de descuento, PR, α, Cp, pérdidas, umbrales | Sí (celdas amarillas) |
| `Diccionario` | Qué es cada columna y de dónde viene | — |

Reglas para no romper el dashboard:

1. **No cambies los nombres de las hojas ni de las columnas.** La app los busca por nombre.
2. **`cod_dane` es la llave** que une las hojas. Debe tener 5 dígitos y estar en las tres primeras hojas.
3. Las columnas en negro son fórmulas. La app las recalcula por su cuenta, así que no dependes de que Excel las haya guardado.

---

## Ejecutar en tu computador

```bash
git clone https://github.com/TU_USUARIO/geovisor-energetico.git
cd geovisor-energetico
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # abre http://127.0.0.1:8050
```

Pruebas:

```bash
pip install -r requirements-dev.txt
pytest -q                          # 18 pruebas
```

---

## Publicarlo con un enlace (Render, recomendado)

GitHub Pages solo sirve páginas estáticas y Dash necesita un servidor Python. Por eso el código y los datos viven en GitHub y **Render** ejecuta la app.

### 1. Subir el repositorio a GitHub

1. En GitHub: **New repository** → nombre `geovisor-energetico` → público o privado → **Create**.
2. En tu computador, dentro de la carpeta:

```bash
git init
git add .
git commit -m "Geovisor energético v1"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/geovisor-energetico.git
git push -u origin main
```

3. En la pestaña **Actions** de GitHub verás correr las pruebas. Deben quedar en verde.

### 2. Desplegar en Render

1. Crea una cuenta en [render.com](https://render.com) con tu usuario de GitHub.
2. **New → Blueprint** → elige el repositorio `geovisor-energetico`.
3. Render lee `render.yaml` y crea el servicio. La primera construcción tarda unos minutos.
4. Te da un enlace público, por ejemplo `https://geovisor-energetico.onrender.com`. Ese es el enlace que compartes.

### 3. Actualizar los datos

Edita `data/geovisor_datos.xlsx` y súbelo:

```bash
git add data/geovisor_datos.xlsx
git commit -m "Actualiza datos"
git push
```

Render redespliega solo en uno o dos minutos. También puedes subir el archivo desde la web de GitHub (**Add file → Upload files**).

**Plan gratuito:** el servicio se duerme tras 15 minutos sin visitas. La primera visita después de eso tarda entre 30 y 60 segundos. Para una presentación, abre el enlace unos minutos antes.

---

## Alternativas de despliegue

### Hugging Face Spaces (gratis, buena vitrina académica)

1. En [huggingface.co](https://huggingface.co): **New Space** → SDK **Docker** → plantilla en blanco.
2. Sube el contenido del repositorio. El `Dockerfile` ya usa el puerto 7860 que exige Hugging Face.
3. Agrega al inicio de este README el bloque de configuración del Space:

```yaml
---
title: Geovisor energético de Colombia
sdk: docker
app_port: 7860
---
```

### Azure App Service (pago, dominio institucional)

Construye la imagen con el `Dockerfile`, súbela a Azure Container Registry y crea un Web App for Containers. Define la variable `PORT=8000` en la configuración del Web App y en `WEBSITES_PORT`. Es el mismo flujo de Docker + GitHub Actions de un despliegue MLOps.

---

## Leer el Excel desde una URL (opcional)

Por defecto la app lee `data/geovisor_datos.xlsx`. Para que lea otro archivo sin tocar el código, define estas variables de entorno (en Render: **Environment**):

| Variable | Ejemplo |
|---|---|
| `GEOVISOR_DATOS` | `https://raw.githubusercontent.com/TU_USUARIO/geovisor-datos/main/geovisor_datos.xlsx` |
| `GEOVISOR_GEOJSON` | Ruta o URL del GeoJSON municipal |
| `GEOVISOR_URL_EXCEL` | Enlace para descargar el Excel que aparece en el encabezado |

Así los datos pueden vivir en un repositorio aparte, con sus propios permisos.

---

## Modelos

| Tecnología | Energía | Supuestos clave |
|---|---|---|
| Paneles FV | E = kWp × GHI × días × PR | PR = 0,80 |
| Colector térmico | E = A × GHI × η × días, con η = η0 − a1·(T_uso − T_amb)/G | η0 = 0,75; a1 = 3,5 W/m²·K |
| Eólica | E = N × ∫ P(v)·f(v) dv × horas × (1 − pérdidas) | Viento llevado al buje con la ley de potencia (α); distribución de Weibull; P(v) = ½·ρ·A·Cp·v³ hasta la nominal |
| Geotermia | E = P × (1 − aux) × FP × 8.760 | Generación de base; avisa si la temperatura no corresponde a la tecnología |
| Costos | LCOE = (CAPEX × CRF + OPEX) / E anual | CRF con la tasa de descuento de la hoja `Supuestos` |

El perfil de 8.760 horas es sintético: reparte la energía de cada mes según una curva diaria (solar), muestras de Weibull (eólica) o potencia constante (geotermia). Siempre suma exactamente la energía mensual del modelo.

## Siguientes pasos

1. Reemplazar `GHI_mensual` y `Viento_mensual` con NASA POWER (`ALLSKY_SFC_SW_DWN` y `WS50M`, climatología mensual por coordenada).
2. Validar la región natural de cada municipio con la lista oficial del IGAC.
3. Validar los costos de la hoja `Tecnologias` con IRENA, UPME o cotizaciones locales.
4. Reemplazar el índice geotérmico por datos de exploración del Servicio Geológico Colombiano.

## Fuentes

- Límites municipales: DANE, Marco Geoestadístico Nacional (MGN) 2018.
- Mapa base: © OpenStreetMap contributors, © CARTO.
