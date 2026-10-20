"""Carga del Excel y de la geometría municipal.

El Excel es la única fuente de datos del dashboard. Las columnas calculadas (zona central,
promedios anuales) se recalculan aquí desde los datos de entrada, así el dashboard no depende
de que el archivo tenga los valores de las fórmulas guardados.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from urllib.request import urlopen

import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union

from . import config

COLUMNAS_OBLIGATORIAS = ["cod_dane", "departamento", "municipio", "latitud", "longitud",
                         "region_natural", "densidad_aire_kg_m3", "weibull_k", "indice_geotermico",
                         "volcan_cercano", "dist_volcan_km"]


def _leer_json(ruta: str) -> dict:
    if ruta.startswith(("http://", "https://")):
        with urlopen(ruta, timeout=60) as r:
            return json.load(r)
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def _mensual(xls: pd.ExcelFile, hoja: str) -> pd.DataFrame:
    df = pd.read_excel(xls, hoja, dtype={"cod_dane": str}).set_index("cod_dane")
    if df.shape[1] != 12:
        raise ValueError(f"La hoja {hoja} debe tener cod_dane y 12 columnas mensuales.")
    df.columns = range(12)
    return df.astype(float)


@dataclass
class Datos:
    municipios: pd.DataFrame        # una fila por municipio, índice cod_dane
    ghi_mensual: pd.DataFrame       # 12 columnas, kWh/m²·día
    viento_mensual: pd.DataFrame    # 12 columnas, m/s a 50 m
    tecnologias: pd.DataFrame       # índice tecnologia_id
    supuestos: dict
    geojson: dict

    # ------------------------------------------------------
    @classmethod
    def cargar(cls, ruta_excel: str = config.RUTA_DATOS, ruta_geojson: str = config.RUTA_GEOJSON) -> "Datos":
        xls = pd.ExcelFile(ruta_excel)
        mun = pd.read_excel(xls, "Municipios", dtype={"cod_dane": str})
        faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in mun.columns]
        if faltan:
            raise ValueError(f"Faltan columnas en la hoja Municipios: {faltan}")
        mun = mun.set_index("cod_dane")
        ghi, vie = _mensual(xls, "GHI_mensual"), _mensual(xls, "Viento_mensual")

        sup_df = pd.read_excel(xls, "Supuestos")
        supuestos = dict(zip(sup_df["clave"], sup_df["valor"].astype(float)))
        tec = pd.read_excel(xls, "Tecnologias").dropna(subset=["recurso"]).set_index("tecnologia_id")

        # Columnas derivadas, siempre desde los datos de entrada
        mun["zona_central"] = mun["region_natural"].eq("Andina")
        mun["ghi_kwh_m2_dia"] = ghi.reindex(mun.index).mean(axis=1).round(2)
        mun["viento_50m_m_s"] = vie.reindex(mun.index).mean(axis=1).round(2)
        mun["fv_kwh_kwp_anio"] = (mun["ghi_kwh_m2_dia"] * 365 * supuestos.get("pr_fv", 0.8)).round(0)
        mun["densidad_eolica_w_m2"] = (0.5 * mun["densidad_aire_kg_m3"] * mun["viento_50m_m_s"] ** 3).round(1)
        alto, medio = supuestos.get("umbral_geo_alto", 0.6), supuestos.get("umbral_geo_medio", 0.3)
        mun["potencial_geotermico"] = np.select(
            [~mun["zona_central"], mun["indice_geotermico"] >= alto, mun["indice_geotermico"] >= medio],
            ["No aplica", "Alto", "Medio"], default="Bajo")

        # Ranking nacional (1 = mejor); geotermia solo dentro de la zona central
        mun["rank_solar"] = mun["ghi_kwh_m2_dia"].rank(ascending=False, method="min").astype(int)
        mun["rank_viento"] = mun["viento_50m_m_s"].rank(ascending=False, method="min").astype(int)
        mun["rank_geo"] = mun["indice_geotermico"].where(mun["zona_central"]).rank(ascending=False, method="min")

        return cls(mun, ghi, vie, tec, supuestos, _leer_json(ruta_geojson))

    # ------------------------------------------------------
    @property
    def departamentos(self) -> list[str]:
        return sorted(self.municipios["departamento"].unique())

    def supuesto(self, clave: str, defecto: float) -> float:
        return float(self.supuestos.get(clave, defecto))

    @cached_property
    def poligonos(self) -> dict:
        """cod_dane → Feature GeoJSON del municipio."""
        return {f["properties"]["cod"]: f for f in self.geojson["features"]}

    @cached_property
    def limites_departamento(self) -> dict:
        """Nombre del departamento → [[lat_min, lon_min], [lat_max, lon_max]]."""
        cod_a_dpto = self.municipios["departamento"].to_dict()
        cajas: dict[str, list] = {}
        for cod, feat in self.poligonos.items():
            dpto = cod_a_dpto.get(cod)
            if dpto is None:
                continue
            x0, y0, x1, y1 = shape(feat["geometry"]).bounds
            c = cajas.setdefault(dpto, [y0, x0, y1, x1])
            cajas[dpto] = [min(c[0], y0), min(c[1], x0), max(c[2], y1), max(c[3], x1)]
        return {k: [[v[0], v[1]], [v[2], v[3]]] for k, v in cajas.items()}

    @cached_property
    def contorno_zona_central(self) -> dict:
        cods = set(self.municipios.index[self.municipios["zona_central"]])
        geoms = [shape(f["geometry"]).buffer(0.01) for c, f in self.poligonos.items() if c in cods]
        # el buffer cierra las rendijas que deja la simplificación entre municipios vecinos;
        # luego se conservan solo los contornos exteriores (sin huecos interiores)
        union = unary_union(geoms).buffer(-0.01)
        partes = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
        union = MultiPolygon([Polygon(p.exterior) for p in partes if p.area > 0.01]).simplify(0.01)
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                                                             "geometry": mapping(union)}]}

    def departamento_geojson(self, dpto: str) -> dict:
        cods = set(self.municipios.index[self.municipios["departamento"] == dpto])
        return {"type": "FeatureCollection",
                "features": [f for c, f in self.poligonos.items() if c in cods]}
