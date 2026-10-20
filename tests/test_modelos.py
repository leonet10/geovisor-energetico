"""Pruebas de los modelos de energía y costos."""
import math

import numpy as np
import pytest

from geovisor import modelos as m

GHI_PLANO = [5.0] * 12
V_PLANO = [7.0] * 12


def test_factor_recuperacion_valor_conocido():
    # 10 % a 25 años: 0,11017 (tabla financiera estándar)
    assert m.factor_recuperacion(0.10, 25) == pytest.approx(0.110168, abs=1e-6)
    assert m.factor_recuperacion(0.0, 20) == pytest.approx(0.05)


def test_lcoe_ejemplo_trabajado():
    # 100 kWp: CAPEX 90.000, OPEX 1.350, 124.700 kWh/año → 0,0903 USD/kWh
    assert m.lcoe(90_000, 1_350, 124_700, 0.10, 25) == pytest.approx(0.0903, abs=1e-4)
    assert m.lcoe(1, 1, 0, 0.1, 10) == math.inf


def test_fv_energia_y_perfil_cuadran():
    r = m.solar_fv(GHI_PLANO, kwp=100, pr=0.8, capex_kw=900, opex_kw=13.5, vida=25, tasa=0.1, semilla="44001")
    assert r.anual_kwh == pytest.approx(100 * 5 * 365 * 0.8)
    assert r.horario_kw.shape == (8760,)
    assert r.horario_kw.sum() == pytest.approx(r.anual_kwh, rel=1e-9)
    assert r.horario_kw[:6].sum() == 0                      # sin producción de noche
    assert r.factor_planta == pytest.approx(r.anual_kwh / (100 * 8760))


def test_perfil_reproducible_entre_llamadas():
    a = m.solar_fv(GHI_PLANO, 10, 0.8, 900, 13.5, 25, 0.1, semilla="17873").horario_kw
    b = m.solar_fv(GHI_PLANO, 10, 0.8, 900, 13.5, 25, 0.1, semilla="17873").horario_kw
    assert np.array_equal(a, b)


def test_colector_eficiencia_cae_con_temperatura():
    tibio = m.colector_termico(GHI_PLANO, 10, 40, 0.75, 3.5, 22, 350, 5, 20, 0.1)
    caliente = m.colector_termico(GHI_PLANO, 10, 80, 0.75, 3.5, 22, 350, 5, 20, 0.1)
    assert tibio.anual_kwh > caliente.anual_kwh > 0
    assert tibio.factor_planta is None and tibio.tipo_energia == "térmica"
    imposible = m.colector_termico(GHI_PLANO, 10, 300, 0.75, 3.5, 22, 350, 5, 20, 0.1)
    assert imposible.anual_kwh == 0 and imposible.avisos


def test_curva_potencia_limites():
    v = np.array([2.0, 8.0, 15.0, 26.0])
    p = m.curva_potencia(v, 2000, 90, 1.225, 0.45, 3, 25)
    assert p[0] == 0 and p[3] == 0                          # bajo arranque y sobre corte
    assert p[2] == 2000                                     # potencia nominal
    assert 0 < p[1] < 2000


def test_eolica_cuadra_y_responde_al_viento():
    base = dict(n_turbinas=1, p_nominal_kw=2000, buje_m=80, d_rotor_m=90, alfa=0.14, k=2.0, rho=1.17,
                cp=0.45, perdidas=0.12, v_arranque=3, v_corte=25, capex_kw=1500, opex_kw=40, vida=20,
                tasa=0.1, semilla="44847")
    fuerte = m.eolica(V_PLANO, **base)
    debil = m.eolica([3.0] * 12, **base)
    # con k = 2 hay ráfagas útiles aun con 3 m/s de media: la relación es ~8,6x, no infinita
    assert fuerte.anual_kwh > 5 * debil.anual_kwh
    assert fuerte.horario_kw.sum() == pytest.approx(fuerte.anual_kwh, rel=1e-3)
    assert 0 < fuerte.factor_planta < 0.6
    assert fuerte.horario_kw.max() <= 2000 * (1 - 0.12) + 1e-6


def test_eolica_dos_turbinas_duplican():
    kw = dict(p_nominal_kw=2000, buje_m=80, d_rotor_m=90, alfa=0.14, k=2.0, rho=1.17, cp=0.45,
              perdidas=0.12, v_arranque=3, v_corte=25, capex_kw=1500, opex_kw=40, vida=20, tasa=0.1)
    uno, dos = m.eolica(V_PLANO, n_turbinas=1, **kw), m.eolica(V_PLANO, n_turbinas=2, **kw)
    assert dos.anual_kwh == pytest.approx(2 * uno.anual_kwh)
    assert dos.lcoe_usd_kwh == pytest.approx(uno.lcoe_usd_kwh)


def test_geotermia_base_y_avisos():
    r = m.geotermia(5, 0.85, 0.08, 150, "geo_binaria", 4500, 120, 30, 0.1)
    assert r.anual_kwh == pytest.approx(5000 * 0.92 * 0.85 * 8760)
    assert np.ptp(r.horario_kw) == 0                       # potencia constante
    flash_frio = m.geotermia(5, 0.85, 0.08, 150, "geo_flash", 3800, 110, 30, 0.1)
    assert any("binaria" in a for a in flash_frio.avisos)
    tibio = m.geotermia(5, 0.85, 0.08, 80, "geo_binaria", 4500, 120, 30, 0.1)
    assert any("usos directos" in a for a in tibio.avisos)
