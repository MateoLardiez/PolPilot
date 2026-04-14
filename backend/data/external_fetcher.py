"""
PolPilot — External Data Fetcher.

Funciones para obtener datos en tiempo real de APIs públicas argentinas
y sincronizarlos con external.sqlite + ChromaDB.

APIs utilizadas (todas gratuitas, sin auth):
  1. BCRA Estadísticas Monetarias v4.0 — variables macro (tasas, inflación, reservas)
  2. BCRA Estadísticas Cambiarias v1.0  — tipos de cambio oficiales
  3. BCRA Central de Deudores v1.0      — perfil crediticio por CUIT
  4. BCRA Régimen de Transparencia v1.0  — catálogo de préstamos de TODOS los bancos
  5. BCRA Cheques Denunciados v1.0       — verificación de cheques
  6. DolarAPI.com                        — todos los tipos de dólar (oficial, blue, MEP, CCL, cripto, tarjeta, mayorista)

Uso:
    from polpilot.backend.data.external_fetcher import sync_all_external_data
    sync_all_external_data("empresa_demo")
"""

import json
import logging
from datetime import datetime, date
from typing import Any

import requests

from .db import get_external_db, insert_row, insert_many, query
from .vector_store import VectorStore
from .data_service import get_company_profile

logger = logging.getLogger(__name__)

BCRA_BASE = "https://api.bcra.gob.ar"
REQUEST_TIMEOUT = 15  # segundos
HEADERS = {
    "Accept-Language": "es-AR",
    "Accept": "application/json",
}


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _clean_cuit(cuit: str) -> str:
    """Remueve guiones del CUIT: '30-71584923-4' → '30715849234'."""
    return cuit.replace("-", "").replace(" ", "")


def _get(url: str, params: dict | None = None) -> dict | None:
    """GET request con manejo de errores. Retorna None si falla."""
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"Error fetching {url}: {e}")
        return None


def _today() -> str:
    return date.today().isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# 1. BCRA ESTADÍSTICAS MONETARIAS v4.0
#    Variables macro: tasas, inflación, reservas, base monetaria, UVA, CER
# ═══════════════════════════════════════════════════════════════════════════

# IDs de variables clave para PyMEs
BCRA_VARIABLES = {
    1:  "reservas_internacionales",     # USD millones, diaria
    4:  "usd_minorista",                # Tipo de cambio minorista vendedor, diaria
    5:  "usd_mayorista",                # Tipo de cambio mayorista referencia, diaria
    7:  "tasa_badlar",                  # BADLAR bancos privados, diaria
    8:  "tasa_tm20",                    # TM20 bancos privados, diaria
    13: "tasa_adelantos_cta_cte",       # Tasa adelantos en cuenta corriente, diaria
    14: "tasa_prestamos_personales",    # Tasa préstamos personales, diaria
    15: "base_monetaria",              # Base monetaria, diaria
    26: "prestamos_sector_privado",     # Préstamos al sector privado, diaria
    27: "inflacion_mensual",            # Variación mensual IPC, mensual
    28: "inflacion_interanual",         # Variación interanual IPC, mensual
    30: "cer",                          # Coeficiente Estabilización Referencia, diaria
    31: "uva",                          # Unidad de Valor Adquisitivo, diaria
}


def fetch_principales_variables() -> list[dict]:
    """Obtiene la lista completa de variables monetarias del BCRA con su último valor.

    Retorna lista de dicts con: idVariable, descripcion, categoria,
    periodicidad, ultFechaInformada, ultValorInformado.
    """
    data = _get(f"{BCRA_BASE}/estadisticas/v4.0/Monetarias", params={"limit": 1000})
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def fetch_variable_data(
    id_variable: int,
    desde: str | None = None,
    hasta: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Obtiene la serie temporal de una variable BCRA específica.

    Args:
        id_variable: ID numérico (ver BCRA_VARIABLES).
        desde/hasta: Fechas en formato 'yyyy-MM-dd'.
        limit: Máximo de registros (default 30).

    Retorna lista de dicts con: fecha, valor.
    """
    params: dict[str, Any] = {"limit": limit}
    if desde:
        params["desde"] = desde
    if hasta:
        params["hasta"] = hasta

    data = _get(f"{BCRA_BASE}/estadisticas/v4.0/Monetarias/{id_variable}", params=params)
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def fetch_key_macro_variables() -> dict[str, dict]:
    """Obtiene el último valor de todas las variables clave para PyMEs.

    Retorna dict mapeando nombre_indicador → {valor, fecha, descripcion}.
    """
    all_vars = fetch_principales_variables()
    if not all_vars:
        return {}

    result = {}
    var_by_id = {v["idVariable"]: v for v in all_vars}
    for var_id, name in BCRA_VARIABLES.items():
        if var_id in var_by_id:
            v = var_by_id[var_id]
            result[name] = {
                "value": v.get("ultValorInformado"),
                "date": v.get("ultFechaInformada", _today()),
                "description": v.get("descripcion", ""),
            }
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. BCRA ESTADÍSTICAS CAMBIARIAS v1.0
#    Tipos de cambio: oficial, mayorista, todas las monedas
# ═══════════════════════════════════════════════════════════════════════════

def fetch_exchange_rates(fecha: str | None = None) -> list[dict]:
    """Obtiene cotizaciones de todas las monedas del BCRA.

    Args:
        fecha: Fecha en formato 'yyyy-MM-dd'. Si es None, trae la última.

    Retorna lista de dicts con: codigoMoneda, descripcion, tipoCotizacion.
    """
    params = {"fecha": fecha} if fecha else None
    data = _get(f"{BCRA_BASE}/estadisticascambiarias/v1.0/Cotizaciones", params=params)
    if not data or data.get("status") != 200:
        return []
    results = data.get("results", {})
    return results.get("detalle", [])


def fetch_usd_rate(fecha: str | None = None) -> dict | None:
    """Obtiene la cotización del dólar USD. Atajo rápido."""
    rates = fetch_exchange_rates(fecha)
    for r in rates:
        if r.get("codigoMoneda") == "USD":
            return r
    return None


def fetch_exchange_rate_history(
    moneda: str = "USD",
    desde: str | None = None,
    hasta: str | None = None,
) -> list[dict]:
    """Obtiene la evolución histórica de una moneda.

    Retorna lista de dicts con: fecha, tipoCotizacion.
    """
    params: dict[str, Any] = {}
    if desde:
        params["fechadesde"] = desde
    if hasta:
        params["fechahasta"] = hasta

    data = _get(f"{BCRA_BASE}/estadisticascambiarias/v1.0/Cotizaciones/{moneda}", params=params)
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


# ═══════════════════════════════════════════════════════════════════════════
# 2b. DOLARAPI.COM — Todos los tipos de dólar argentino
#     Oficial, Blue, MEP (Bolsa), CCL, Cripto, Tarjeta, Mayorista
# ═══════════════════════════════════════════════════════════════════════════

DOLARAPI_BASE = "https://dolarapi.com/v1"


def fetch_all_dollar_rates() -> list[dict]:
    """Obtiene TODOS los tipos de dólar de Argentina.

    Retorna lista de dicts con:
      - casa: 'oficial', 'blue', 'bolsa' (MEP), 'contadoconliqui', 'cripto', 'tarjeta', 'mayorista'
      - nombre: nombre legible ('Oficial', 'Blue', 'Bolsa', etc.)
      - compra: precio de compra en ARS
      - venta: precio de venta en ARS
      - fechaActualizacion: timestamp ISO
    """
    data = _get(f"{DOLARAPI_BASE}/dolares")
    if not data:
        return []
    # dolarapi.com retorna directamente un array JSON (no envuelto en {status, results})
    if isinstance(data, list):
        return data
    return []


def fetch_dollar_rate(tipo: str) -> dict | None:
    """Obtiene un tipo de dólar específico.

    Args:
        tipo: 'oficial', 'blue', 'bolsa' (MEP), 'contadoconliqui', 'cripto', 'tarjeta', 'mayorista'.
    """
    data = _get(f"{DOLARAPI_BASE}/dolares/{tipo}")
    if not data or not isinstance(data, dict) or "compra" not in data:
        return None
    return data


def fetch_dollar_snapshot() -> dict[str, dict]:
    """Retorna un snapshot completo de todos los dólares como dict.

    Ejemplo:
        {
            "oficial":         {"compra": 1330, "venta": 1380},
            "blue":            {"compra": 1385, "venta": 1405},
            "mep":             {"compra": 1404, "venta": 1407},
            "ccl":             {"compra": 1463, "venta": 1464},
            "cripto":          {"compra": 1462, "venta": 1462},
            "tarjeta":         {"compra": 1729, "venta": 1794},
            "mayorista":       {"compra": 1351, "venta": 1360},
        }
    """
    rates = fetch_all_dollar_rates()
    if not rates:
        return {}

    # Mapear casa → nombre corto para nuestras tablas
    casa_map = {
        "oficial": "oficial",
        "blue": "blue",
        "bolsa": "mep",
        "contadoconliqui": "ccl",
        "cripto": "cripto",
        "tarjeta": "tarjeta",
        "mayorista": "mayorista",
    }

    snapshot = {}
    for r in rates:
        casa = r.get("casa", "")
        key = casa_map.get(casa, casa)
        snapshot[key] = {
            "compra": r.get("compra"),
            "venta": r.get("venta"),
            "fecha": r.get("fechaActualizacion", ""),
        }
    return snapshot


# ═══════════════════════════════════════════════════════════════════════════
# 3. BCRA CENTRAL DE DEUDORES v1.0
#    Perfil crediticio: deudas actuales, históricas, cheques rechazados
# ═══════════════════════════════════════════════════════════════════════════

def fetch_deudas(cuit: str) -> dict | None:
    """Consulta las deudas actuales de un CUIT en el sistema financiero.

    Retorna dict con: identificacion, denominacion, periodos[{periodo, entidades[...]}].
    Cada entidad tiene: situacion (1-5), monto, diasAtrasoPago, etc.
    """
    clean = _clean_cuit(cuit)
    data = _get(f"{BCRA_BASE}/centraldedeudores/v1.0/Deudas/{clean}")
    if not data or data.get("status") != 200:
        return None
    return data.get("results")


def fetch_deudas_historicas(cuit: str) -> dict | None:
    """Consulta el historial de deudas de un CUIT (últimos 24 meses)."""
    clean = _clean_cuit(cuit)
    data = _get(f"{BCRA_BASE}/centraldedeudores/v1.0/Deudas/Historicas/{clean}")
    if not data or data.get("status") != 200:
        return None
    return data.get("results")


def fetch_cheques_rechazados(cuit: str) -> dict | None:
    """Consulta cheques rechazados de un CUIT."""
    clean = _clean_cuit(cuit)
    data = _get(f"{BCRA_BASE}/centraldedeudores/v1.0/Deudas/ChequesRechazados/{clean}")
    if not data or data.get("status") != 200:
        return None
    return data.get("results")


def build_credit_profile_from_bcra(cuit: str) -> dict | None:
    """Construye un perfil crediticio completo a partir de las 3 consultas BCRA.

    Retorna dict compatible con la tabla credit_profile de external.sqlite.
    """
    deudas = fetch_deudas(cuit)
    historicas = fetch_deudas_historicas(cuit)
    cheques = fetch_cheques_rechazados(cuit)

    if deudas is None and historicas is None:
        return None

    # Determinar situación actual (peor situación entre todas las entidades)
    situation = 1
    total_debt = 0.0
    max_days_overdue = 0

    if deudas and deudas.get("periodos"):
        latest_period = deudas["periodos"][0]
        for entidad in latest_period.get("entidades", []):
            sit = entidad.get("situacion", 1)
            if sit > situation:
                situation = sit
            total_debt += entidad.get("monto", 0)
            days = entidad.get("diasAtrasoPago", 0)
            if days > max_days_overdue:
                max_days_overdue = days

    # Historial 24 meses: extraer la peor situación de cada mes
    last_24 = []
    if historicas and historicas.get("periodos"):
        for periodo in historicas["periodos"][:24]:
            worst = 1
            for ent in periodo.get("entidades", []):
                s = ent.get("situacion", 1)
                if s > worst:
                    worst = s
            last_24.append(worst)

    # Cheques rechazados
    rejected = []
    if cheques and cheques.get("periodos"):
        for periodo in cheques["periodos"]:
            for ch in periodo.get("entidades", []):
                rejected.append({
                    "entidad": ch.get("descripcionEntidad", ""),
                    "monto": ch.get("monto", 0),
                    "causal": ch.get("causal", ""),
                })

    return {
        "cuit": cuit,
        "situation": situation,
        "total_debt": total_debt,
        "days_overdue": max_days_overdue,
        "last_24_months": json.dumps(last_24 if last_24 else [situation] * 24),
        "rejected_checks": json.dumps(rejected),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. BCRA RÉGIMEN DE TRANSPARENCIA v1.0
#    Catálogo de préstamos de TODOS los bancos con criterios de elegibilidad
#    ** FUENTE MÁS VALIOSA para detección automática de préstamos **
# ═══════════════════════════════════════════════════════════════════════════

def fetch_prestamos_personales(codigo_entidad: int | None = None) -> list[dict]:
    """Obtiene préstamos personales de todos los bancos (o uno específico).

    Cada préstamo incluye: nombreCompleto, descripcionEntidad,
    tasaEfectivaAnualMaxima, montoMaximoOtorgable, plazoMaximoOtorgable,
    ingresoMinimoMensual, beneficiario, tipoTasa, denominacion, etc.
    """
    params = {"codigoEntidad": codigo_entidad} if codigo_entidad else None
    data = _get(f"{BCRA_BASE}/transparencia/v1.0/Prestamos/Personales", params=params)
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def fetch_prestamos_prendarios(codigo_entidad: int | None = None) -> list[dict]:
    """Obtiene préstamos prendarios (con garantía) de todos los bancos.
    Acá aparecen muchas líneas PyME con garantía SGR o prendaria."""
    params = {"codigoEntidad": codigo_entidad} if codigo_entidad else None
    data = _get(f"{BCRA_BASE}/transparencia/v1.0/Prestamos/Prendarios", params=params)
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def fetch_prestamos_hipotecarios(codigo_entidad: int | None = None) -> list[dict]:
    """Obtiene préstamos hipotecarios de todos los bancos."""
    params = {"codigoEntidad": codigo_entidad} if codigo_entidad else None
    data = _get(f"{BCRA_BASE}/transparencia/v1.0/Prestamos/Hipotecarios", params=params)
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def fetch_plazos_fijos(codigo_entidad: int | None = None) -> list[dict]:
    """Obtiene tasas de plazos fijos de todos los bancos.
    Útil para comparar contra la tasa de crédito y calcular costo de oportunidad."""
    params = {"codigoEntidad": codigo_entidad} if codigo_entidad else None
    data = _get(f"{BCRA_BASE}/transparencia/v1.0/PlazosFijos", params=params)
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def _parse_loan_to_credit(loan: dict, credit_type: str) -> dict | None:
    """Convierte un préstamo de la API de Transparencia al formato de available_credits.
    Retorna None si faltan campos críticos (bank_name o credit_name)."""
    bank_name = loan.get("descripcionEntidad") or ""
    credit_name = loan.get("nombreCompleto") or ""
    if not bank_name or not credit_name:
        return None

    # Construir requisitos desde los campos disponibles
    requirements = []
    if loan.get("beneficiario"):
        requirements.append(f"Beneficiario: {loan['beneficiario']}")
    if loan.get("ingresoMinimoMensual"):
        requirements.append(f"Ingreso mínimo mensual: ${loan['ingresoMinimoMensual']:,.0f}")
    if loan.get("antiguedadLaboralMinimaMeses"):
        requirements.append(f"Antigüedad laboral mínima: {loan['antiguedadLaboralMinimaMeses']} meses")
    if loan.get("edadMaximaSolicitada"):
        requirements.append(f"Edad máxima: {loan['edadMaximaSolicitada']} años")
    if loan.get("relacionCuotaIngreso"):
        requirements.append(f"Relación cuota/ingreso máxima: {loan['relacionCuotaIngreso']}%")

    # Determinar si requiere MiPyME
    beneficiario = (loan.get("beneficiario") or "").lower()
    requires_mipyme = "mipyme" in beneficiario or "pyme" in beneficiario

    # Tasa: la API devuelve TEA (tasa efectiva anual) en porcentaje
    tea_max = loan.get("tasaEfectivaAnualMaxima", 0) or 0
    annual_rate = tea_max / 100 if tea_max > 1 else tea_max

    # Moneda
    denominacion = loan.get("denominacion") or "Pesos"
    if "dolar" in denominacion.lower() or "usd" in denominacion.lower():
        credit_type_suffix = f"{credit_type}_usd"
    else:
        credit_type_suffix = credit_type

    return {
        "bank_name": bank_name,
        "credit_name": credit_name,
        "credit_type": credit_type_suffix,
        "annual_rate": annual_rate,
        "max_amount": loan.get("montoMaximoOtorgable"),
        "min_amount": loan.get("montoMinimoOtorgable"),
        "max_term_months": loan.get("plazoMaximoOtorgable"),
        "requirements": json.dumps(requirements, ensure_ascii=False),
        "requires_mipyme_cert": requires_mipyme,
        "url": None,
        "source": "bcra_transparencia",
        "last_verified": _today(),
    }


def fetch_all_loan_products() -> list[dict]:
    """Obtiene TODOS los préstamos de todos los bancos y los convierte
    al formato de available_credits.

    Combina personales + prendarios + hipotecarios.
    """
    credits = []

    personales = fetch_prestamos_personales()
    for loan in personales:
        parsed = _parse_loan_to_credit(loan, "personal")
        if parsed:
            credits.append(parsed)

    prendarios = fetch_prestamos_prendarios()
    for loan in prendarios:
        parsed = _parse_loan_to_credit(loan, "prendario")
        if parsed:
            credits.append(parsed)

    hipotecarios = fetch_prestamos_hipotecarios()
    for loan in hipotecarios:
        parsed = _parse_loan_to_credit(loan, "hipotecario")
        if parsed:
            credits.append(parsed)

    return credits


def fetch_pyme_eligible_loans() -> list[dict]:
    """Filtra préstamos que mencionan PyME/MiPyME en el beneficiario.
    Estos son los más relevantes para el feature de detección automática."""
    all_loans = fetch_all_loan_products()
    return [c for c in all_loans if c.get("requires_mipyme_cert")]


# ═══════════════════════════════════════════════════════════════════════════
# 5. BCRA CHEQUES DENUNCIADOS v1.0
#    Verificación de cheques robados/extraviados/adulterados
# ═══════════════════════════════════════════════════════════════════════════

def fetch_entidades_bancarias() -> list[dict]:
    """Obtiene la lista de entidades bancarias con sus códigos."""
    data = _get(f"{BCRA_BASE}/cheques/v1.0/entidades")
    if not data or data.get("status") != 200:
        return []
    return data.get("results", [])


def fetch_cheque_denunciado(codigo_entidad: int, numero_cheque: int) -> dict | None:
    """Verifica si un cheque específico está denunciado."""
    data = _get(f"{BCRA_BASE}/cheques/v1.0/denunciados/{codigo_entidad}/{numero_cheque}")
    if not data or data.get("status") != 200:
        return None
    return data.get("results")


# ═══════════════════════════════════════════════════════════════════════════
# 6. SYNC FUNCTIONS — Fetch + Write to external.sqlite + ChromaDB
#    Estas son las que llaman los agentes para actualizar la base de datos
# ═══════════════════════════════════════════════════════════════════════════

def sync_macro_indicators(empresa_id: str) -> int:
    """Descarga variables macro del BCRA y las escribe en macro_indicators.

    Incluye: tasas (BADLAR, TM20, adelantos, personales), inflación
    (mensual, interanual), tipo de cambio (minorista, mayorista),
    reservas, base monetaria, UVA, CER.

    Retorna cantidad de indicadores actualizados.
    """
    variables = fetch_key_macro_variables()
    if not variables:
        logger.warning("No se pudieron obtener variables macro del BCRA")
        return 0

    rows = []
    for name, data in variables.items():
        if data.get("value") is not None:
            # Convertir tasas de porcentaje a decimal si corresponde
            value = data["value"]
            if "tasa" in name and value > 1:
                value = value / 100

            rows.append({
                "indicator_name": name,
                "value": value,
                "date": data["date"],
                "source": "bcra_api",
            })

    # Agregar tipos de cambio desde la API cambiaria del BCRA (EUR, BRL, etc.)
    rates = fetch_exchange_rates()
    for rate in rates:
        code = rate.get("codigoMoneda", "")
        cotizacion = rate.get("tipoCotizacion", 0)
        if code in ("EUR", "BRL") and cotizacion:
            rows.append({
                "indicator_name": f"tc_{code.lower()}",
                "value": cotizacion,
                "date": _today(),
                "source": "bcra_api",
            })

    # Agregar TODOS los tipos de dólar desde DolarAPI.com
    dollar_snapshot = fetch_dollar_snapshot()
    for tipo, data in dollar_snapshot.items():
        venta = data.get("venta")
        compra = data.get("compra")
        fecha = data.get("fecha", _today())
        # Normalizar fecha ISO a solo date si viene con timestamp
        if isinstance(fecha, str) and "T" in fecha:
            fecha = fecha.split("T")[0]

        if venta is not None:
            rows.append({
                "indicator_name": f"usd_{tipo}_venta",
                "value": venta,
                "date": fecha,
                "source": "dolarapi",
            })
        if compra is not None:
            rows.append({
                "indicator_name": f"usd_{tipo}_compra",
                "value": compra,
                "date": fecha,
                "source": "dolarapi",
            })

    if not rows:
        return 0

    conn = get_external_db(empresa_id)
    count = insert_many(conn, "macro_indicators", rows)
    conn.close()

    logger.info(f"sync_macro_indicators: {count} indicadores actualizados")
    return count


def sync_credit_profile(empresa_id: str) -> dict | None:
    """Consulta el perfil crediticio BCRA del CUIT de la empresa
    y lo escribe en la tabla credit_profile.

    Retorna el perfil construido o None si no se pudo consultar.
    """
    profile = get_company_profile(empresa_id)
    if not profile or not profile.get("cuit"):
        logger.warning(f"sync_credit_profile: empresa {empresa_id} sin CUIT")
        return None

    cuit = profile["cuit"]
    credit_data = build_credit_profile_from_bcra(cuit)
    if not credit_data:
        logger.warning(f"sync_credit_profile: no se encontraron datos BCRA para CUIT {cuit}")
        return None

    conn = get_external_db(empresa_id)
    insert_row(conn, "credit_profile", credit_data)
    conn.close()

    logger.info(f"sync_credit_profile: perfil actualizado para CUIT {cuit}")
    return credit_data


def sync_available_credits(
    empresa_id: str,
    pyme_only: bool = False,
) -> int:
    """Descarga el catálogo completo de préstamos bancarios desde BCRA Transparencia
    y los escribe en available_credits.

    Args:
        pyme_only: Si True, solo trae préstamos que mencionan PyME/MiPyME.

    Retorna cantidad de créditos cargados.
    """
    if pyme_only:
        credits = fetch_pyme_eligible_loans()
    else:
        credits = fetch_all_loan_products()

    if not credits:
        logger.warning("sync_available_credits: no se obtuvieron préstamos del BCRA")
        return 0

    # Limpiar la tabla antes de recargar (es un catálogo completo)
    conn = get_external_db(empresa_id)
    conn.execute("DELETE FROM available_credits WHERE source = 'bcra_transparencia'")
    conn.commit()

    count = insert_many(conn, "available_credits", credits)
    conn.close()

    # Actualizar embeddings en ChromaDB
    vs = VectorStore(empresa_id)
    docs, metas, ids = [], [], []
    for i, c in enumerate(credits):
        text = (
            f"Crédito: {c['credit_name']} de {c['bank_name']}. "
            f"Tipo: {c['credit_type']}. "
            f"Tasa anual: {c['annual_rate']*100:.1f}%. "
            f"Monto: ${c.get('min_amount') or 0:,.0f} - ${c.get('max_amount') or 0:,.0f}. "
            f"Plazo: {c.get('max_term_months') or 'N/A'} meses. "
            f"Requisitos: {c.get('requirements', '[]')}. "
            f"Requiere MiPyME: {'Sí' if c.get('requires_mipyme_cert') else 'No'}."
        )
        docs.append(text)
        metas.append({"type": "credit", "bank": c["bank_name"], "source": "bcra_transparencia"})
        ids.append(f"bcra_credit_{i:04d}")

    if docs:
        # Limpiar embeddings anteriores de BCRA y recargar
        try:
            col = vs._get_collection("external_research")
            existing = col.get(where={"source": "bcra_transparencia"})
            if existing and existing.get("ids"):
                col.delete(ids=existing["ids"])
        except Exception:
            pass  # Si falla el delete, simplemente agregamos

        vs.add_documents("external_research", docs, metas, ids)

    logger.info(f"sync_available_credits: {count} créditos cargados")
    return count


def sync_all_external_data(empresa_id: str) -> dict:
    """Sincronización completa: descarga todo de las APIs BCRA y actualiza external.sqlite.

    Retorna dict con contadores de cada sync.
    """
    logger.info(f"=== sync_all_external_data para {empresa_id} ===")

    results = {
        "macro_indicators": sync_macro_indicators(empresa_id),
        "credit_profile": "ok" if sync_credit_profile(empresa_id) else "no_data",
        "available_credits": sync_available_credits(empresa_id),
    }

    logger.info(f"=== Sync completado: {results} ===")
    return results
