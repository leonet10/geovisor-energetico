"""Modelos de energía útil y costos nivelados.

Funciones puras, sin dependencia de Dash, para poder probarlas y reutilizarlas.
Unidades: energía en kWh, potencia en kW, costos en USD.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field

import numpy as np

DIAS_MES = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
HORAS_MES = DIAS_MES * 24
HORAS_ANIO = 8760


@dataclass
class Resultado:
    """Salida común de todos los modelos."""
    anual_kwh: float
    mensual_kwh: np.ndarray            # 12 valores
    horario_kw: np.ndarray             # 8.760 valores
    capacidad_kw: float | None         # potencia nominal; None para calor (colector)
    capex_usd: float
    opex_usd_anio: float
    lcoe_usd_kwh: float
    tipo_energia: str = "eléctrica"    # "eléctrica" o "térmica"
    avisos: list[str] = field(default_factory=list)
    detalle: dict = field(default_factory=dict)

    @property
    def factor_planta(self) -> float | None:
        if not self.capacidad_kw:
            return None
        return self.anual_kwh / (self.capacidad_kw * HORAS_ANIO)


# ----------------------------------------------------------
# Economía
# ----------------------------------------------------------
def factor_recuperacion(tasa: float, anios: int) -> float:
    """CRF = r(1+r)^n / ((1+r)^n − 1). Con tasa 0 es 1/n."""
    if tasa == 0:
        return 1 / anios
    f = (1 + tasa) ** anios
    return tasa * f / (f - 1)


def lcoe(capex: float, opex_anual: float, energia_anual_kwh: float, tasa: float, anios: int) -> float:
    """Costo nivelado: (CAPEX·CRF + OPEX) / energía anual."""
    if energia_anual_kwh <= 0:
        return math.inf
    return (capex * factor_recuperacion(tasa, anios) + opex_anual) / energia_anual_kwh


# ----------------------------------------------------------
# Perfiles horarios
# ----------------------------------------------------------
def _rng(semilla: str) -> np.random.Generator:
    # crc32 es estable entre procesos (hash() de Python no lo es), así cada municipio
    # tiene siempre el mismo perfil en todos los workers del servidor
    return np.random.default_rng(zlib.crc32(str(semilla).encode()))


def _perfil_solar(mensual_kwh: np.ndarray, semilla: str, horas_sol: float = 12.0) -> np.ndarray:
    """Reparte la energía de cada mes en días (con nubosidad) y horas (campana de seno).

    La suma del perfil reproduce exactamente la energía mensual.
    """
    rng = _rng(semilla)
    h = np.arange(24) + 0.5
    inicio = 12 - horas_sol / 2
    campana = np.where((h > inicio) & (h < inicio + horas_sol), np.sin(np.pi * (h - inicio) / horas_sol), 0)
    campana = campana / campana.sum()
    serie = []
    for e_mes, dias in zip(mensual_kwh, DIAS_MES):
        f = np.clip(1 + 0.18 * rng.standard_normal(dias), 0.25, None)
        f = f / f.sum()
        serie.append((e_mes * f)[:, None] * campana[None, :])
    return np.concatenate(serie).ravel()


# ----------------------------------------------------------
# Solar fotovoltaica
# ----------------------------------------------------------
def solar_fv(ghi_mensual, kwp: float, pr: float, capex_kw: float, opex_kw: float,
             vida: int, tasa: float, semilla: str = "0", horas_sol: float = 12.0) -> Resultado:
    """E_mes = kWp × GHI (kWh/m²·día = horas solares pico) × días × PR."""
    ghi = np.asarray(ghi_mensual, float)
    mensual = kwp * ghi * DIAS_MES * pr
    anual = float(mensual.sum())
    capex, opex = capex_kw * kwp, opex_kw * kwp
    return Resultado(anual, mensual, _perfil_solar(mensual, semilla, horas_sol), kwp, capex, opex,
                     lcoe(capex, opex, anual, tasa, vida),
                     detalle={"rendimiento_kwh_kwp": anual / kwp if kwp else 0})


# ----------------------------------------------------------
# Solar térmica (colector plano)
# ----------------------------------------------------------
def colector_termico(ghi_mensual, area_m2: float, t_uso: float, eta0: float, a1: float, t_amb: float,
                     capex_m2: float, opex_m2: float, vida: int, tasa: float, semilla: str = "0",
                     horas_sol: float = 12.0) -> Resultado:
    """Eficiencia de primer orden: η = η0 − a1·(T_uso − T_amb)/G, con G la irradiancia media diurna."""
    ghi = np.asarray(ghi_mensual, float)
    g_media = ghi * 1000 / horas_sol                      # W/m² promedio durante las horas de sol
    eta = np.clip(eta0 - a1 * (t_uso - t_amb) / g_media, 0, None)
    mensual = area_m2 * ghi * eta * DIAS_MES
    anual = float(mensual.sum())
    capex, opex = capex_m2 * area_m2, opex_m2 * area_m2
    avisos = []
    if eta.min() == 0:
        avisos.append("La temperatura de uso es demasiado alta para un colector plano en algunos meses.")
    return Resultado(anual, mensual, _perfil_solar(mensual, semilla, horas_sol), None, capex, opex,
                     lcoe(capex, opex, anual, tasa, vida), tipo_energia="térmica", avisos=avisos,
                     detalle={"eficiencia_media": float(eta.mean())})


# ----------------------------------------------------------
# Eólica (Weibull + curva de potencia física)
# ----------------------------------------------------------
def curva_potencia(v, p_nominal_kw: float, d_rotor_m: float, rho: float, cp: float,
                   v_arranque: float, v_corte: float):
    """P(v) = ½·ρ·A·Cp·v³ limitada a la potencia nominal, entre arranque y corte (kW)."""
    area = math.pi * d_rotor_m**2 / 4
    p = 0.5 * rho * area * cp * np.asarray(v, float) ** 3 / 1000
    p = np.minimum(p, p_nominal_kw)
    return np.where((v >= v_arranque) & (v < v_corte), p, 0.0)


def velocidad_nominal(p_nominal_kw: float, d_rotor_m: float, rho: float, cp: float) -> float:
    """Velocidad a la que la turbina alcanza su potencia nominal."""
    area = math.pi * d_rotor_m**2 / 4
    return (p_nominal_kw * 1000 / (0.5 * rho * area * cp)) ** (1 / 3)


def eolica(v50_mensual, n_turbinas: int, p_nominal_kw: float, buje_m: float, d_rotor_m: float,
           alfa: float, k: float, rho: float, cp: float, perdidas: float, v_arranque: float,
           v_corte: float, capex_kw: float, opex_kw: float, vida: int, tasa: float,
           semilla: str = "0") -> Resultado:
    """Energía mensual = N × ∫ P(v)·f(v) dv × horas × (1 − pérdidas), con f de Weibull."""
    v50 = np.asarray(v50_mensual, float)
    v_buje = v50 * (buje_m / 50) ** alfa                   # ley de potencia
    malla = np.arange(0, 35, 0.05)
    pc = curva_potencia(malla, p_nominal_kw, d_rotor_m, rho, cp, v_arranque, v_corte)
    mensual = np.zeros(12)
    for i, vm in enumerate(v_buje):
        c = vm / math.gamma(1 + 1 / k)                   # escala de Weibull a partir de la media
        f = (k / c) * (malla / c) ** (k - 1) * np.exp(-(malla / c) ** k)
        mensual[i] = n_turbinas * (pc * f).sum() * 0.05 * HORAS_MES[i] * (1 - perdidas)
    anual = float(mensual.sum())

    # Perfil horario sintético: muestras de Weibull por hora, escaladas a la energía de cada mes
    rng = _rng(semilla)
    serie = []
    for i, vm in enumerate(v_buje):
        c = vm / math.gamma(1 + 1 / k)
        v = c * rng.weibull(k, HORAS_MES[i])
        p = n_turbinas * curva_potencia(v, p_nominal_kw, d_rotor_m, rho, cp, v_arranque, v_corte)
        p = p * (1 - perdidas)
        tope = n_turbinas * p_nominal_kw * (1 - perdidas)
        for _ in range(10):                      # escalar al total del mes sin superar la potencia nominal
            if p.sum() == 0:
                break
            p = np.minimum(p * (mensual[i] / p.sum()), tope)
        serie.append(p)
    horario = np.concatenate(serie)

    pot = n_turbinas * p_nominal_kw
    capex, opex = capex_kw * pot, opex_kw * pot
    avisos = ["Resultado preliminar: confirma el recurso con medición en sitio (torre meteorológica o "
              "LiDAR) antes de invertir."]
    if v_buje.mean() < v_arranque + 1:
        avisos.append("La velocidad media a la altura del buje está cerca de la velocidad de arranque: "
                      "la turbina pasará la mayor parte del tiempo detenida.")
    return Resultado(anual, mensual, horario, pot, capex, opex, lcoe(capex, opex, anual, tasa, vida),
                     avisos=avisos,
                     detalle={"v_buje_media": float(v_buje.mean()),
                              "v_nominal": velocidad_nominal(p_nominal_kw, d_rotor_m, rho, cp)})


# ----------------------------------------------------------
# Geotermia
# ----------------------------------------------------------
RANGO_TECNOLOGIA_GEO = {"geo_binaria": (100, 180), "geo_flash": (180, 350)}


def geotermia(p_mwe: float, factor_planta: float, consumo_aux: float, t_recurso: float, tecnologia: str,
              capex_kw: float, opex_kw: float, vida: int, tasa: float) -> Resultado:
    """Generación de base: potencia neta × factor de planta, constante a lo largo del año."""
    p_kw = p_mwe * 1000
    p_media = p_kw * (1 - consumo_aux) * factor_planta
    horario = np.full(HORAS_ANIO, p_media)
    mensual = p_media * HORAS_MES.astype(float)
    anual = float(mensual.sum())
    capex, opex = capex_kw * p_kw, opex_kw * p_kw
    avisos = []
    lo, hi = RANGO_TECNOLOGIA_GEO.get(tecnologia, (0, 1e9))
    if t_recurso < 100:
        avisos.append("Con menos de 100 °C el recurso sirve para usos directos de calor, no para generar electricidad.")
    elif t_recurso < lo:
        avisos.append(f"La planta flash necesita recursos sobre {lo:.0f} °C; con {t_recurso:.0f} °C conviene una planta binaria.")
    elif t_recurso > hi:
        avisos.append(f"Con {t_recurso:.0f} °C una planta flash suele ser más eficiente que una binaria.")
    avisos.append("La temperatura del recurso solo se confirma con pozos exploratorios.")
    # el factor de planta se informa sobre la potencia neta; los costos se aplican a la bruta
    return Resultado(anual, mensual, horario, p_kw * (1 - consumo_aux), capex, opex,
                     lcoe(capex, opex, anual, tasa, vida), avisos=avisos,
                     detalle={"potencia_bruta_kw": p_kw})
