"""Piezas de la interfaz: formato de números, layout y bloques de resultados."""

from __future__ import annotations

import dash_leaflet as dl
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html

from . import config
from .datos import Datos
from .modelos import Resultado

LIMITES_COLOMBIA = [[-4.3, -79.1], [12.5, -66.8]]


# ----------------------------------------------------------
# Formato (separador de miles con punto y decimales con coma)
# ----------------------------------------------------------
def num(v, dec: int = 0) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def energia(kwh: float) -> tuple[float, str]:
    """Elige la unidad legible: kWh, MWh o GWh."""
    if kwh >= 1e6:
        return kwh / 1e6, "GWh"
    if kwh >= 1e4:
        return kwh / 1e3, "MWh"
    return kwh, "kWh"


def ico(nombre: str):
    return html.Span(className=f"ico ico-{nombre}", **{"aria-hidden": "true"})


# ----------------------------------------------------------
# Ventana del pin (HTML que dibuja Leaflet)
# ----------------------------------------------------------
def ventana_html(r) -> str:
    def fila(valor_ico, nombre, valor, color, sec=None):
        base = (f"<div class='vt-fila'><span class='vt-rec' style='color:{color}'><span class='ico ico-{valor_ico}'></span>"
                f"<span style='color:#1D2733'>{nombre}</span></span><b>{valor}</b></div>")
        if sec:
            base += f"<div class='vt-fila sec'><span>{sec[0]}</span><b>{sec[1]}</b></div>"
        return base

    partes = [
        f"<div class='vt'><div><div class='vt-nombre'>{r.municipio}</div>"
        f"<div class='vt-sub'>{r.departamento} · {r.region_natural} · DANE {r.Index}</div></div>",
        fila("sol", "Irradiación", f"{num(r.ghi_kwh_m2_dia, 2)} kWh/m²·día", config.COLOR["Solar"],
             ("Producción FV", f"{num(r.fv_kwh_kwp_anio)} kWh/kWp·año")),
        fila("viento", "Viento a 50 m", f"{num(r.viento_50m_m_s, 2)} m/s", config.COLOR["Viento"],
             ("Densidad eólica", f"{num(r.densidad_eolica_w_m2, 1)} W/m²")),
    ]
    if r.zona_central:
        partes.append(fila("llama", "Geotermia", f"{r.potencial_geotermico} · índice {num(r.indice_geotermico, 2)}",
                           config.COLOR["Geotermia"],
                           ("Volcán cercano", f"{r.volcan_cercano}, {num(r.dist_volcan_km)} km")))
    else:
        partes.append(f"<div class='vt-fila vt-na'><span class='vt-rec'><span class='ico ico-llama'></span>Geotermia</span>"
                      f"<span>No aplica</span></div><div class='vt-fila sec vt-na'><span>Fuera de la zona central</span></div>")
    partes.append(f"<div class='vt-pie'>{num(r.latitud, 4)}, {num(r.longitud, 4)} · clic para seleccionar</div></div>")
    return "".join(partes)


def puntos_geojson(df, seleccionado: str | None = None) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.longitud, r.latitud]},
         "properties": {"cod": r.Index, "nombre": r.municipio, "ventana": ventana_html(r),
                        "seleccionado": r.Index == seleccionado}}
        for r in df.itertuples()]}


# ----------------------------------------------------------
# Panel izquierdo
# ----------------------------------------------------------
def opciones_recurso():
    return [{"label": html.Span([ico(config.ICONO[k]), k], style={"display": "inline-flex", "gap": "8px",
                                                                  "alignItems": "center"}),
             "value": k} for k in config.RECURSOS]


def opciones_tecnologia(datos: Datos, recurso: str, zona_central: bool | None):
    tec = datos.tecnologias
    if recurso != "Todos":
        tec = tec[tec["recurso"] == recurso]
    opciones = []
    for tid, t in tec.iterrows():
        bloqueada = t["recurso"] == "Geotermia" and zona_central is False
        etiqueta = [html.Span(t["nombre"])]
        if recurso == "Todos":
            etiqueta.append(html.Span(t["recurso"], className="tec-recurso"))
        if bloqueada:
            etiqueta.append(html.Span("solo zona central", className="tec-recurso"))
        opciones.append({"label": html.Span(etiqueta, style={"display": "flex", "gap": "8px", "width": "100%"}),
                         "value": tid, "disabled": bloqueada})
    return opciones


def valores_por_defecto(datos: Datos, tecnologia: str) -> dict:
    """Valores iniciales: config, con los supuestos del Excel donde aplican."""
    p = {k: v for k, _, v, *_ in config.PARAMETROS[tecnologia]}
    if "pr" in p:
        p["pr"] = datos.supuesto("pr_fv", p["pr"])
    if "eta0" in p:
        p["eta0"] = datos.supuesto("eta0_colector", p["eta0"])
        p["a1"] = datos.supuesto("a1_colector", p["a1"])
    if tecnologia == "eolico_grande":
        p["alfa"] = datos.supuesto("alfa", p["alfa"])
        p["perdidas"] = round(datos.supuesto("perdidas_eolicas", p["perdidas"] / 100) * 100, 1)
    return p


def campos_parametros(datos: Datos, tecnologia: str):
    defectos = valores_por_defecto(datos, tecnologia)

    def campo(clave, etiqueta, unidad, mn, mx, paso):
        return html.Div(className="campo", children=[
            html.Label(etiqueta),
            html.Div(className="caja", children=[
                dcc.Input(id={"type": "param", "key": clave}, type="number", value=defectos[clave], min=mn, max=mx,
                          step=paso, debounce=True),
                html.Span(unidad) if unidad else None])])

    grupos = {"dim": [], "esp": []}
    for clave, etiqueta, _, unidad, mn, mx, paso, grupo in config.PARAMETROS[tecnologia]:
        grupos[grupo].append(campo(clave, etiqueta, unidad, mn, mx, paso))
    return [html.Span("4 · Dimensionamiento", className="rotulo"), html.Div(grupos["dim"], className="dos-col"),
            html.Span("5 · Especificaciones", className="rotulo"), html.Div(grupos["esp"], className="dos-col"),
            html.Div(id="derivado", className="derivado")]


def panel_izquierdo(datos: Datos):
    return html.Aside(className="col-izq", children=[
        html.Section(className="tarjeta", children=[
            html.Span("1 · Recurso", className="rotulo"),
            dcc.RadioItems(id="recurso", options=opciones_recurso(), value="Todos", className="segmentado"),
            html.P("Geotermia solo se muestra en la zona central (línea punteada). Solar y viento cubren todo el país.",
                   className="nota")]),
        html.Section(className="tarjeta", children=[
            html.Span("2 · Ubicación", className="rotulo"),
            html.Div(style={"display": "flex", "flexDirection": "column", "gap": "10px"}, children=[
                html.Div(className="campo", children=[html.Label("Departamento", htmlFor="dpto"),
                         dcc.Dropdown(id="dpto", options=["Todos"] + datos.departamentos, value="Todos",
                                      clearable=False)]),
                html.Div(className="campo", children=[html.Label("Municipio", htmlFor="mpio"),
                         dcc.Dropdown(id="mpio", placeholder="Escribe para buscar…", clearable=True)])])]),
        html.Section(className="tarjeta", children=[
            html.Span("3 · Tecnología", className="rotulo"),
            dcc.RadioItems(id="tecnologia", className="tecnologias", value="fv",
                           options=opciones_tecnologia(datos, "Todos", None))]),
        html.Section(id="parametros", className="tarjeta", children=campos_parametros(datos, "fv")),
        html.Button("Calcular energía útil", id="calcular", n_clicks=0, className="boton-calcular"),
    ])


# ----------------------------------------------------------
# Mapa (columna central)
# ----------------------------------------------------------
def panel_mapa(datos: Datos):
    return html.Main(className="col-centro", children=html.Section(className="tarjeta", children=[
        html.Div(className="mapa-cabecera", children=[
            html.Div([html.H2("Mapa de recursos por municipio", className="titulo-tarjeta"),
                      html.Span(id="conteo", className="subtitulo")])]),
        html.Div(id="filtros", className="filtros-activos"),
        dl.Map(id="mapa", className="mapa", center=[4.1, -72.9], zoom=6, maxBounds=[[-8, -85], [16, -62]],
               minZoom=5, children=[
                   dl.TileLayer(url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
             attribution="© OpenStreetMap contributors", maxZoom=19),
                   dl.GeoJSON(id="capa-zona", data=datos.contorno_zona_central, interactive=False),
                   dl.GeoJSON(id="capa-dpto", interactive=False,
                              style={"color": "#5E6B79", "weight": 1, "fillColor": "#FFFFFF", "fillOpacity": 0.35}),
                   dl.GeoJSON(id="capa-sel", interactive=False,
                              style={"color": "#C5221F", "weight": 2, "fillColor": "#EA4335", "fillOpacity": 0.15}),
                   dl.GeoJSON(id="puntos", cluster=True, zoomToBoundsOnClick=True,
                              superClusterOptions={"radius": 60, "maxZoom": 8},
                              pointToLayer={"variable": "geovisor.pin"},
                              clusterToLayer={"variable": "geovisor.grupo"},
                              hideout={"color": config.COLOR["Todos"]}),
                   dl.ScaleControl(position="bottomleft", imperial=False),
               ]),
        html.Div(id="leyenda", className="leyenda"),
        html.Div(id="comparativo"),
    ]))


# ----------------------------------------------------------
# Bloques de resultados (columna derecha)
# ----------------------------------------------------------
def fila(a, b):
    return html.Div([html.Span(a), html.Span(b)], className="ficha-fila")


def kpi(etiqueta, valor, unidad, color=None):
    return html.Div(className="kpi", children=[
        html.Span(etiqueta), html.B([valor, " ", html.Small(unidad)], style={"color": color} if color else None)])


def ficha(datos: Datos, cod: str | None):
    if not cod:
        return html.Section(className="tarjeta", children=[
            html.Span("Ficha del punto", className="rotulo"),
            html.P("Selecciona un municipio en el panel o haz clic en un pin del mapa.", className="vacio")])
    r = datos.municipios.loc[cod]
    filas = [fila("Región natural", r["region_natural"]),
             fila("Zona central", "Sí, aplica geotermia" if r["zona_central"] else "No, sin geotermia"),
             fila("Latitud, longitud", f"{num(r['latitud'], 4)}, {num(r['longitud'], 4)}")]
    if r["zona_central"]:
        filas.append(fila("Volcán más cercano", f"{r['volcan_cercano']}, {num(r['dist_volcan_km'])} km"))
    return html.Section(className="tarjeta", children=[
        html.Span("Ficha del punto", className="rotulo"),
        html.Div([html.Div(r["municipio"], style={"fontSize": "20px", "fontWeight": 700}),
                  html.Span(f"{r['departamento']} · código DANE {cod}", className="subtitulo")]),
        html.Div(filas)])


def _layout_fig(**kw):
    base = dict(margin=dict(l=40, r=8, t=8, b=28), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=11, color="#4F5B68"),
                showlegend=False, hovermode="x unified",
                xaxis=dict(showgrid=False, zeroline=False, fixedrange=True),
                yaxis=dict(gridcolor="#E7ECF1", zeroline=False, fixedrange=True, rangemode="tozero"))
    base.update(kw)
    return base


def figura_mensual(res: Resultado, color: str):
    _, unidad = energia(res.mensual_kwh.max())
    f = {"kWh": 1, "MWh": 1e3, "GWh": 1e6}[unidad]
    fig = go.Figure(go.Bar(x=list(range(12)), y=res.mensual_kwh / f, marker_color=color,
                           customdata=["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
                           hovertemplate="%{customdata}: %{y:,.1f} " + unidad + "<extra></extra>"))
    fig.update_layout(**_layout_fig(height=170, bargap=0.25,
                                    xaxis=dict(tickmode="array", tickvals=list(range(12)), ticktext=config.MESES,
                                               showgrid=False, fixedrange=True)))
    return fig, unidad


def figura_horaria(res: Resultado, color: str):
    """Perfil de 8.760 h suavizado con promedio móvil de 7 días (168 h)."""
    # el año se trata como circular para que los extremos no caigan a cero por el suavizado
    ext = np.concatenate([res.horario_kw[-84:], res.horario_kw, res.horario_kw[:83]])
    serie = np.convolve(ext, np.ones(168) / 168, mode="valid")
    unidad, f = ("MW", 1e3) if serie.max() >= 1e3 else ("kW", 1)
    x = np.arange(0, 8760, 24)
    fig = go.Figure(go.Scatter(x=x, y=serie[x] / f, mode="lines", line=dict(color=color, width=1.6),
                               fill="tozeroy", fillcolor=color + "2E",
                               hovertemplate="Hora %{x:,.0f}: %{y:,.2f} " + unidad + "<extra></extra>"))
    fig.update_layout(**_layout_fig(height=150, margin=dict(l=40, r=26, t=8, b=28), xaxis=dict(
        range=[0, 8760], tickmode="array", tickvals=[0, 2160, 4344, 6552, 8760], ticktext=["Ene", "Abr", "Jul", "Oct", "8.760 h"],
        showgrid=False, fixedrange=True)))
    return fig, unidad


def bloques_resultado(datos: Datos, res: Resultado, tecnologia: str, resumen: str):
    t = datos.tecnologias.loc[tecnologia]
    color = config.COLOR[t["recurso"]]
    val, uni = energia(res.anual_kwh)
    termico = res.tipo_energia == "térmica"
    fig_m, uni_m = figura_mensual(res, color)
    fig_h, uni_h = figura_horaria(res, color)
    if tecnologia == "fv":
        sub = f"{t['nombre']} · {num(res.detalle['kwp'], 1)} kWp"
    elif tecnologia == "colector":
        sub = f"{t['nombre']} · calor útil"
    elif tecnologia.startswith("eolico"):
        sub = f"{t['nombre']} · {num(res.capacidad_kw)} kW · viento en el buje {num(res.detalle['v_buje_media'], 1)} m/s"
    else:
        sub = f"{t['nombre']} · {num(res.detalle['potencia_bruta_kw'] / 1000, 1)} MWe brutos"
    segundo = (kpi("Eficiencia media", num(res.detalle["eficiencia_media"] * 100, 1), "%") if termico
               else kpi("Factor de planta", num(res.factor_planta * 100, 1), "%"))
    avisos = [html.Div([ico("alerta"), html.Span(a)], className="aviso") for a in res.avisos]
    energia_card = html.Section(className="tarjeta", children=[
        html.Div(className="cabecera-res", children=[
            html.Div([html.H2("Energía útil" + (" (calor)" if termico else ""), className="titulo-tarjeta"),
                      html.Span(sub, className="subtitulo")]),
            html.Span("Datos ilustrativos", className="etiqueta")]),
        *avisos,
        html.Div([kpi("Producción anual", num(val, 1 if val < 100 else 0), f"{uni}{' térmicos' if termico else ''}/año",
                      color), segundo], className="kpis"),
        html.Div([html.Span(["Producción mensual ", html.Small(f"({uni_m})")], className="graf-tit"),
                  dcc.Graph(figure=fig_m, config={"displayModeBar": False})]),
        html.Div([html.Span(["Perfil horario del año ", html.Small(f"({uni_h} · promedio móvil 7 días)")],
                            className="graf-tit"),
                  dcc.Graph(figure=fig_h, config={"displayModeBar": False})]),
    ])
    costos_card = html.Section(className="tarjeta", children=[
        html.H2("Costos", className="titulo-tarjeta"),
        html.Div([kpi("CAPEX", num(res.capex_usd), "USD"), kpi("OPEX", num(res.opex_usd_anio), "USD/año")],
                 className="kpis"),
        html.Div([kpi("Costo nivelado de calor (LCOH)" if termico else "LCOE", num(res.lcoe_usd_kwh, 3),
                      "USD/kWh", color)], className="kpis"),
        html.P(resumen, className="nota")])
    return [energia_card, costos_card]


def comparativo(datos: Datos, cod: str | None):
    if not cod:
        return None
    r = datos.municipios.loc[cod]
    total = len(datos.municipios)
    total_geo = int(datos.municipios["zona_central"].sum())
    med = datos.municipios[["ghi_kwh_m2_dia", "viento_50m_m_s"]].median()
    med_geo = datos.municipios.loc[datos.municipios["zona_central"], "indice_geotermico"].median()

    def tarjeta(icono, color, titulo, rank, n, valor, mediana, unidad):
        pos = round((1 - (rank - 1) / (n - 1)) * 100)
        if rank <= 10:
            texto = f"Entre los 10 mejores {'de la zona central' if n == total_geo else 'del país'}"
        elif pos >= 50:
            texto = "Por encima de la mediana"
        else:
            texto = "Por debajo de la mediana"
        return html.Div(className="comp", children=[
            html.Span([html.Span(className=f"ico ico-{icono}", style={"color": color}), titulo], className="comp-tit"),
            html.Span([f"#{num(rank)} ", html.Small(f"de {num(n)}")], className="comp-rank"),
            html.Div(html.Div(style={"width": f"{pos}%", "background": color}), className="barra"),
            html.Span(f"{valor} {unidad} · mediana {mediana}", className="subtitulo"),
            html.Span(texto, style={"fontSize": "12px"})])

    tarjetas = [
        tarjeta("sol", config.COLOR["Solar"], "Solar", int(r["rank_solar"]), total, num(r["ghi_kwh_m2_dia"], 2),
                num(med["ghi_kwh_m2_dia"], 2), "kWh/m²·día"),
        tarjeta("viento", config.COLOR["Viento"], "Viento", int(r["rank_viento"]), total, num(r["viento_50m_m_s"], 2),
                num(med["viento_50m_m_s"], 2), "m/s"),
    ]
    if r["zona_central"]:
        tarjetas.append(tarjeta("llama", config.COLOR["Geotermia"], "Geotermia", int(r["rank_geo"]), total_geo,
                                num(r["indice_geotermico"], 2), num(med_geo, 2), "índice"))
    else:
        tarjetas.append(html.Div(className="comp na", children=[
            html.Span([ico("llama"), "Geotermia"], className="comp-tit"),
            html.Span("No aplica", className="comp-rank"),
            html.Span(f"{r['municipio']} está fuera de la zona central, donde se evalúa la geotermia.",
                      style={"fontSize": "12px"})]))
    return html.Div([html.Span(f"Cómo se compara {r['municipio']} con el resto del país", className="graf-tit"),
                     html.Div(tarjetas, className="comparativo")], style={"display": "flex",
                                                                          "flexDirection": "column", "gap": "10px"})


# ----------------------------------------------------------
# Página
# ----------------------------------------------------------
def pagina(datos: Datos, url_datos: str | None = None):
    fuente = (html.A("geovisor_datos.xlsx", href=url_datos, target="_blank", rel="noopener") if url_datos
              else html.B("geovisor_datos.xlsx"))
    return html.Div(className="pagina", children=[
        html.Header(className="encabezado", children=[
            html.Div([html.H1("Geovisor de recursos energéticos de Colombia"),
                      html.P("Recurso solar, eólico y geotérmico por municipio, y energía útil por tecnología")]),
            html.Span(["Datos: ", fuente, f" · {num(len(datos.municipios))} municipios · límites DANE MGN 2018"],
                      className="fuente-datos")]),
        html.Div(className="cuerpo", children=[
            panel_izquierdo(datos),
            panel_mapa(datos),
            html.Aside(className="col-der", children=[
                html.Div(id="ficha", children=ficha(datos, None)),
                html.Div(id="resultados", style={"display": "flex", "flexDirection": "column", "gap": "12px"}),
            ]),
        ]),
    ])
