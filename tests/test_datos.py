"""Pruebas de la carga del Excel: estructura y columnas derivadas."""
import pytest

from geovisor import config
from geovisor.calculo import calcular
from geovisor.componentes import valores_por_defecto
from geovisor.datos import Datos


@pytest.fixture(scope="module")
def datos():
    return Datos.cargar(config.RUTA_DATOS, config.RUTA_GEOJSON)


def test_estructura(datos):
    m = datos.municipios
    assert len(m) == 1122 and m.index.is_unique
    assert m["latitud"].between(-4.5, 13.5).all() and m["longitud"].between(-82, -66).all()
    assert datos.ghi_mensual.shape == (1122, 12) and datos.viento_mensual.shape == (1122, 12)
    assert set(datos.tecnologias.index) == set(config.PARAMETROS)
    assert len(datos.poligonos) == 1122


def test_geotermia_solo_zona_central(datos):
    m = datos.municipios
    assert (m.loc[~m["zona_central"], "potencial_geotermico"] == "No aplica").all()
    assert m.loc[m["zona_central"], "potencial_geotermico"].isin(["Alto", "Medio", "Bajo"]).all()
    fuera = m.index[~m["zona_central"]][0]
    with pytest.raises(ValueError):
        calcular(datos, fuera, "geo_binaria", valores_por_defecto(datos, "geo_binaria"))


def test_promedio_anual_desde_mensual(datos):
    cod = datos.municipios.index[0]
    assert datos.municipios.at[cod, "ghi_kwh_m2_dia"] == pytest.approx(datos.ghi_mensual.loc[cod].mean(), abs=0.006)


@pytest.mark.parametrize("tec", list(config.PARAMETROS))
def test_todas_las_tecnologias_calculan(datos, tec):
    m = datos.municipios
    cod = m.index[m["zona_central"]][0]
    r = calcular(datos, cod, tec, valores_por_defecto(datos, tec))
    assert r.anual_kwh > 0 and r.lcoe_usd_kwh > 0 and len(r.horario_kw) == 8760
