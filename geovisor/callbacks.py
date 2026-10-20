"""Interacciones del dashboard."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, html, no_update

from . import componentes as C
from . import config
from .calculo import calcular, resumen_supuestos
from .datos import Datos
from .modelos import velocidad_nominal


def registrar(app, datos: Datos):
    mun = datos.municipios

    # ------------------------------------------------------
    # Ubicación: opciones de municipio según el departamento
    # ------------------------------------------------------
    @app.callback(Output("mpio", "options"), Input("dpto", "value"))
    def opciones_municipio(dpto):
        d = mun if dpto in (None, "Todos") else mun[mun["departamento"] == dpto]
        etiqueta = (lambda r: r.municipio) if dpto not in (None, "Todos") else (lambda r: f"{r.municipio} ({r.departamento})")
        return [{"label": etiqueta(r), "value": r.Index} for r in d.sort_values("municipio").itertuples()]

    # ------------------------------------------------------
    # Filtros de ubicación sincronizados: listas, clic en pin y chips
    # ------------------------------------------------------
    @app.callback(Output("dpto", "value"), Output("mpio", "value"),
                  Input("dpto", "value"), Input("mpio", "value"), Input("puntos", "clickData"),
                  Input({"type": "quitar", "que": ALL}, "n_clicks"),
                  prevent_initial_call=True)
    def sincronizar(dpto, cod, clic, _quitar):
        disparo = ctx.triggered_id
        if isinstance(disparo, dict):
            if not any(t["value"] for t in ctx.triggered):            # el chip apenas se creó
                return no_update, no_update
            que = disparo["que"]
            if que == "mpio":
                return no_update, None
            return "Todos", None                                      # "dpto" o "todos"
        if disparo == "puntos":
            if not clic or clic["properties"].get("cluster"):
                return no_update, no_update
            cod = clic["properties"]["cod"]
            return mun.at[cod, "departamento"], cod
        if disparo == "mpio" and cod:
            return mun.at[cod, "departamento"], cod
        if disparo == "dpto" and cod and mun.at[cod, "departamento"] != dpto:
            return no_update, None
        return no_update, no_update

    # ------------------------------------------------------
    # Mapa: puntos visibles, encuadre, capas y chips
    # ------------------------------------------------------
    @app.callback(Output("puntos", "data"), Output("puntos", "hideout"), Output("conteo", "children"),
                  Output("capa-zona", "style"), Output("capa-dpto", "data"), Output("capa-sel", "data"),
                  Output("mapa", "viewport"), Output("filtros", "children"), Output("leyenda", "children"),
                  Input("recurso", "value"), Input("dpto", "value"), Input("mpio", "value"))
    def actualizar_mapa(recurso, dpto, cod):
        dpto = dpto or "Todos"
        if cod:
            visibles = mun.loc[[cod]]
        else:
            visibles = mun if recurso != "Geotermia" else mun[mun["zona_central"]]
            if dpto != "Todos":
                visibles = visibles[visibles["departamento"] == dpto]

        zona_visible = recurso in ("Todos", "Geotermia") and not cod   # con un municipio elegido estorba
        estilo_zona = {"color": config.COLOR["Geotermia"], "weight": 2 if zona_visible else 0, "dashArray": "6 5",
                       "fillColor": config.COLOR["Geotermia"], "fillOpacity": 0.05 if zona_visible else 0}
        capa_dpto = datos.departamento_geojson(dpto) if dpto != "Todos" else None
        capa_sel = ({"type": "FeatureCollection", "features": [datos.poligonos[cod]]}
                    if cod and cod in datos.poligonos else None)
        limites = datos.limites_departamento.get(dpto, C.LIMITES_COLOMBIA) if dpto != "Todos" else C.LIMITES_COLOMBIA
        # dash-leaflet compara el centro anterior al actualizar, así que se envían centro y zoom además
        # de los límites (los límites tienen prioridad para el encuadre)
        centro = [(limites[0][0] + limites[1][0]) / 2, (limites[0][1] + limites[1][1]) / 2]
        viewport = ({"bounds": limites, "center": centro, "zoom": 7, "transition": "flyToBounds"} if dpto != "Todos"
                    else {"center": [4.1, -72.9], "zoom": 6, "transition": "flyTo"})

        # Chips de filtro activo
        chips = []
        if cod:
            r = mun.loc[cod]
            chips.append(html.Span([f"Municipio: {r['municipio']}, {r['departamento']}",
                                    html.Button(C.ico("cerrar"), id={"type": "quitar", "que": "mpio"},
                                                title="Quitar filtro de municipio")], className="chip"))
        elif dpto != "Todos":
            chips.append(html.Span([f"Departamento: {dpto}",
                                    html.Button(C.ico("cerrar"), id={"type": "quitar", "que": "dpto"},
                                                title="Quitar filtro de departamento")], className="chip"))
        if chips:
            chips.append(html.Button("Ver todos los municipios", id={"type": "quitar", "que": "todos"},
                                     className="enlace"))

        if cod:
            conteo = f"Mostrando 1 de {C.num(len(mun))} puntos · filtrado por municipio"
            leyenda = [html.Span([html.Span(className="ley-pin"), "Punto del municipio (pasa el cursor)"]),
                       html.Span([html.Span(className="ley-sel"), "Límite del municipio filtrado"])]
        else:
            conteo = f"Mostrando {C.num(len(visibles))} de {C.num(len(mun))} puntos"
            if recurso == "Geotermia":
                conteo += " · solo zona central"
            leyenda = [html.Span([html.Span(className="ley-pin"), "Municipio (pasa el cursor)"]),
                       html.Span([html.Span("12", className="ley-grupo"), "Grupo de municipios (clic para acercar)"])]
        if zona_visible:
            leyenda.append(html.Span([html.Span(className="ley-zona"), "Zona central · geotermia"]))

        return (C.puntos_geojson(visibles, cod), {"color": config.COLOR[recurso]}, conteo, estilo_zona,
                capa_dpto, capa_sel, viewport, chips, leyenda)

    # ------------------------------------------------------
    # Tecnologías disponibles según recurso y municipio
    # ------------------------------------------------------
    @app.callback(Output("tecnologia", "options"), Output("tecnologia", "value"),
                  Input("recurso", "value"), Input("mpio", "value"), State("tecnologia", "value"))
    def tecnologias(recurso, cod, actual):
        zona = bool(mun.at[cod, "zona_central"]) if cod else None
        opciones = C.opciones_tecnologia(datos, recurso, zona)
        validas = [o["value"] for o in opciones if not o["disabled"]]
        return opciones, (actual if actual in validas else (validas[0] if validas else None))

    @app.callback(Output("parametros", "children"), Input("tecnologia", "value"))
    def parametros(tecnologia):
        return C.campos_parametros(datos, tecnologia) if tecnologia else []

    # ------------------------------------------------------
    # Valores derivados del dimensionamiento (se ven al escribir)
    # ------------------------------------------------------
    @app.callback(Output("derivado", "children"),
                  Input({"type": "param", "key": ALL}, "value"),
                  State({"type": "param", "key": ALL}, "id"), State("tecnologia", "value"), State("mpio", "value"))
    def derivado(valores, ids, tecnologia, cod):
        p = {i["key"]: v for i, v in zip(ids, valores)}
        if not tecnologia or any(v is None for v in p.values()) or set(p) != {k for k, *_ in config.PARAMETROS[tecnologia]}:
            return "Completa los campos para ver el tamaño del sistema."
        if tecnologia == "fv":
            return (f"Potencia instalada {C.num(p['n_paneles'] * p['wp_panel'] / 1000, 1)} kWp · "
                    f"área {C.num(p['n_paneles'] * p['area_panel'])} m²")
        if tecnologia.startswith("eolico"):
            rho = float(mun.at[cod, "densidad_aire_kg_m3"]) if cod else 1.17
            vn = velocidad_nominal(p["p_nominal"], p["rotor"], rho, datos.supuesto("cp", 0.45))
            area = 3.14159 * p["rotor"] ** 2 / 4
            return (f"Potencia total {C.num(p['n_turbinas'] * p['p_nominal'])} kW · área barrida {C.num(area)} m² · "
                    f"alcanza la nominal con {C.num(vn, 1)} m/s")
        if tecnologia == "colector":
            return f"Calor para agua o procesos a {C.num(p['t_uso'])} °C con {C.num(p['area'])} m² de colectores"
        neta = p["p_mwe"] * (1 - p["aux"] / 100)
        return f"Potencia neta {C.num(neta, 2)} MWe después del consumo auxiliar"

    # ------------------------------------------------------
    # Ficha, comparativo y cálculo
    # ------------------------------------------------------
    @app.callback(Output("ficha", "children"), Output("comparativo", "children"), Input("mpio", "value"))
    def ficha(cod):
        return C.ficha(datos, cod), C.comparativo(datos, cod)

    @app.callback(Output("resultados", "children"),
                  Input("calcular", "n_clicks"), Input("mpio", "value"), Input("tecnologia", "value"),
                  State({"type": "param", "key": ALL}, "value"), State({"type": "param", "key": ALL}, "id"))
    def resultados(_, cod, tecnologia, valores, ids):
        if not cod or not tecnologia:
            return html.Section(className="tarjeta", children=[
                html.H2("Energía útil", className="titulo-tarjeta"),
                html.P("Elige un municipio y una tecnología. Luego ajusta el tamaño del sistema y presiona "
                       "«Calcular energía útil».", className="vacio")])
        esperadas = {k for k, *_ in config.PARAMETROS[tecnologia]}
        p = {i["key"]: v for i, v in zip(ids, valores)}
        if set(p) != esperadas:                      # el panel aún muestra la tecnología anterior
            p = C.valores_por_defecto(datos, tecnologia)
        if any(v is None for v in p.values()):
            return html.Section(className="tarjeta", children=[
                html.Div([C.ico("alerta"), html.Span("Hay campos vacíos o fuera de rango en el dimensionamiento.")],
                         className="aviso")])
        try:
            res = calcular(datos, cod, tecnologia, p)
        except ValueError as e:
            return html.Section(className="tarjeta", children=[
                html.Div([C.ico("alerta"), html.Span(str(e))], className="aviso")])
        return C.bloques_resultado(datos, res, tecnologia, resumen_supuestos(datos, tecnologia))
