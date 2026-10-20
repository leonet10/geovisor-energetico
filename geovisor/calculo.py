"""Ejecuta el modelo de la tecnología elegida para un municipio, con datos del Excel."""

from __future__ import annotations

from . import modelos
from .datos import Datos


def calcular(datos: Datos, cod: str, tecnologia: str, p: dict) -> modelos.Resultado:
    """`p` son los parámetros del panel, por clave (ver config.PARAMETROS)."""
    mun = datos.municipios.loc[cod]
    tec = datos.tecnologias.loc[tecnologia]
    tasa = datos.supuesto("tasa_descuento", 0.10)
    vida = int(tec["vida_util_anios"])
    capex, opex = float(tec["capex"]), float(tec["opex_anual"])
    horas_sol = datos.supuesto("horas_sol", 12.0)

    if tecnologia == "fv":
        kwp = p["n_paneles"] * p["wp_panel"] / 1000
        r = modelos.solar_fv(datos.ghi_mensual.loc[cod], kwp, p["pr"], capex, opex, vida, tasa,
                             semilla=cod, horas_sol=horas_sol)
        r.detalle.update(area_m2=p["n_paneles"] * p["area_panel"], kwp=kwp)
        return r

    if tecnologia == "colector":
        return modelos.colector_termico(datos.ghi_mensual.loc[cod], p["area"], p["t_uso"], p["eta0"], p["a1"],
                                        datos.supuesto("t_ambiente", 22.0), capex, opex, vida, tasa,
                                        semilla=cod, horas_sol=horas_sol)

    if tecnologia in ("eolico_grande", "eolico_pequeno"):
        return modelos.eolica(
            datos.viento_mensual.loc[cod], int(p["n_turbinas"]), p["p_nominal"], p["buje"], p["rotor"],
            p["alfa"], float(mun["weibull_k"]), float(mun["densidad_aire_kg_m3"]), datos.supuesto("cp", 0.45),
            p["perdidas"] / 100, datos.supuesto("v_arranque", 3.0), datos.supuesto("v_corte", 25.0),
            capex, opex, vida, tasa, semilla=cod)

    if tecnologia in ("geo_binaria", "geo_flash"):
        if not bool(mun["zona_central"]):
            raise ValueError("La geotermia solo se evalúa en municipios de la zona central.")
        return modelos.geotermia(p["p_mwe"], p["fp"] / 100, p["aux"] / 100, p["t_recurso"], tecnologia,
                                 capex, opex, vida, tasa)

    raise ValueError(f"Tecnología desconocida: {tecnologia}")


def resumen_supuestos(datos: Datos, tecnologia: str) -> str:
    """Línea de texto con los costos y supuestos usados, para mostrar bajo el LCOE."""
    t = datos.tecnologias.loc[tecnologia]
    tasa = datos.supuesto("tasa_descuento", 0.10) * 100
    num = lambda v: f"{v:,.0f}".replace(",", ".") if float(v).is_integer() else f"{v:,.1f}".replace(".", "X").replace(",", ".").replace("X", ",")
    return (f"CAPEX {num(t['capex'])} {t['unidad_capex']} · OPEX {num(t['opex_anual'])} {t['unidad_opex']} · "
            f"tasa {tasa:.0f} % · {int(t['vida_util_anios'])} años · fuente: hoja Tecnologias")
