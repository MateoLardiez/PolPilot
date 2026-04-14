"""Cargador de datos mock para agentes — Hackathon MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "mock_companies.json"

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return _cache


def get_company_data(company_id: str) -> dict | None:
    """
    Devuelve los datos completos de una empresa por su id.
    Si no se encuentra, devuelve la primera empresa como fallback (demo).
    """
    data = _load()
    for empresa in data.get("empresas", []):
        if empresa.get("id") == company_id:
            return empresa
    # Fallback: empresa demo principal
    empresas = data.get("empresas", [])
    return empresas[0] if empresas else None


def get_macro_context() -> dict:
    """Devuelve el contexto macroeconómico actual."""
    data = _load()
    return data.get("contexto_macroeconomico_argentina_abril_2026", {})


def build_finanzas_context(company_id: str) -> str:
    """
    Construye el bloque de contexto financiero para inyectar al agente.
    Incluye todos los datos internos de la empresa relevantes para análisis financiero.
    """
    empresa = get_company_data(company_id)
    if not empresa:
        return "No se encontraron datos para esta empresa."

    finanzas = empresa.get("finanzas", {})
    equipo = empresa.get("equipo", {})

    context = f"""
=== DATOS INTERNOS DE LA EMPRESA ===

PERFIL:
- Nombre: {empresa.get('nombre')}
- CUIT: {empresa.get('cuit')}
- Rubro: {empresa.get('rubro')}
- Localidad: {empresa.get('localidad')}
- Antigüedad: {empresa.get('antiguedad_años')} años
- Régimen AFIP: {empresa.get('categoria_afip')}
- Empleados: {empresa.get('equipo', {}).get('total_empleados')}
- Período de los datos: {finanzas.get('periodo')}

INGRESOS MENSUALES (ARS):
- Ventas mostrador: ${finanzas.get('ingresos_mensuales', {}).get('ventas_mostrador', 0):,.0f}
- Ventas mayoristas: ${finanzas.get('ingresos_mensuales', {}).get('ventas_mayoristas', 0):,.0f}
- Ventas MercadoLibre: ${finanzas.get('ingresos_mensuales', {}).get('ventas_online_ml', 0):,.0f}
- Servicios instalación: ${finanzas.get('ingresos_mensuales', {}).get('servicios_instalacion', 0):,.0f}
- TOTAL FACTURADO: ${finanzas.get('ingresos_mensuales', {}).get('total_facturado', 0):,.0f}

COSTOS DE MERCADERÍA:
- Compras proveedores nacionales: ${finanzas.get('costos_mercaderia', {}).get('compras_proveedores_nacionales', 0):,.0f}
- Importación directa: ${finanzas.get('costos_mercaderia', {}).get('compras_importacion_directa', 0):,.0f}
- Flete y logística: ${finanzas.get('costos_mercaderia', {}).get('flete_y_logistica', 0):,.0f}
- TOTAL COSTO MERCADERÍA: ${finanzas.get('costos_mercaderia', {}).get('total_costo_mercaderia', 0):,.0f}

RESULTADO MENSUAL:
- Margen bruto: ${finanzas.get('resultado_mensual', {}).get('margen_bruto', 0):,.0f} ({finanzas.get('indicadores_financieros', {}).get('margen_bruto', 0)*100:.1f}%)
- Gastos operativos: ${finanzas.get('resultado_mensual', {}).get('gastos_operativos', 0):,.0f}
- Resultado operativo: ${finanzas.get('resultado_mensual', {}).get('resultado_operativo', 0):,.0f}
- Margen operativo: {finanzas.get('resultado_mensual', {}).get('margen_operativo_porcentaje', 0)*100:.1f}%

FLUJO DE CAJA:
- Saldo inicial mes: ${finanzas.get('flujo_de_caja', {}).get('saldo_inicial_mes', 0):,.0f}
- Total cobros del mes: ${finanzas.get('flujo_de_caja', {}).get('cobros_del_mes', {}).get('total_cobros', 0):,.0f}
- Total pagos del mes: ${finanzas.get('flujo_de_caja', {}).get('pagos_del_mes', {}).get('total_pagos', 0):,.0f}
- Flujo neto: ${finanzas.get('flujo_de_caja', {}).get('flujo_neto_mes', 0):,.0f}
- Saldo final: ${finanzas.get('flujo_de_caja', {}).get('saldo_final_mes', 0):,.0f}
- Días de cobertura: {finanzas.get('flujo_de_caja', {}).get('dias_de_cobertura_gastos', 0):.2f} días

CUENTAS POR COBRAR:
- Total: ${finanzas.get('cuentas_por_cobrar', {}).get('total', 0):,.0f}
- A 30 días: ${finanzas.get('cuentas_por_cobrar', {}).get('a_30_dias', 0):,.0f}
- A 60 días: ${finanzas.get('cuentas_por_cobrar', {}).get('a_60_dias', 0):,.0f}
- Morosos +90 días: ${finanzas.get('cuentas_por_cobrar', {}).get('morosos_mas_90_dias', 0):,.0f}
- Clientes morosos: {json.dumps(finanzas.get('cuentas_por_cobrar', {}).get('clientes_morosos', []), ensure_ascii=False)}

CUENTAS POR PAGAR:
- Total: ${finanzas.get('cuentas_por_pagar', {}).get('total', 0):,.0f}
- A proveedores 30 días: ${finanzas.get('cuentas_por_pagar', {}).get('a_proveedores_30_dias', 0):,.0f}
- Impuestos pendientes: ${finanzas.get('cuentas_por_pagar', {}).get('impuestos_pendientes', 0):,.0f}

STOCK:
- Valor total stock: ${finanzas.get('stock', {}).get('valor_total_stock', 0):,.0f}
- Rotación promedio: {finanzas.get('stock', {}).get('rotacion_stock_dias')} días
- Productos sin movimiento 90d: {finanzas.get('stock', {}).get('productos_sin_movimiento_90_dias')} ítems (${finanzas.get('stock', {}).get('valor_stock_sin_movimiento', 0):,.0f})

INDICADORES CLAVE:
- Liquidez corriente: {finanzas.get('indicadores_financieros', {}).get('liquidez_corriente')}
- Endeudamiento: {finanzas.get('indicadores_financieros', {}).get('endeudamiento')}
- Ciclo de caja: {finanzas.get('indicadores_financieros', {}).get('ciclo_de_caja_dias')} días
- Punto de equilibrio mensual: ${finanzas.get('indicadores_financieros', {}).get('punto_equilibrio_mensual', 0):,.0f}
- ROI anual estimado: {finanzas.get('indicadores_financieros', {}).get('roi_anual_estimado', 0)*100:.1f}%

BALANCE:
- Total activos: ${finanzas.get('activos', {}).get('total_activos', 0):,.0f}
- Total pasivos: ${finanzas.get('pasivos', {}).get('total_pasivos', 0):,.0f}
- Patrimonio neto: ${finanzas.get('patrimonio_neto', 0):,.0f}
- Deuda bancaria: ${finanzas.get('pasivos', {}).get('deuda_bancaria_corto_plazo', 0):,.0f}

HISTORIAL VENTAS 6 MESES:
{json.dumps(finanzas.get('historial_ventas_6_meses', []), ensure_ascii=False, indent=2)}

PROVEEDORES PRINCIPALES:
{json.dumps(empresa.get('proveedores', []), ensure_ascii=False, indent=2)}

CLIENTES PRINCIPALES:
{json.dumps(empresa.get('clientes_principales', []), ensure_ascii=False, indent=2)}
"""
    return context.strip()


def build_economia_context() -> str:
    """
    Construye el bloque de contexto macroeconómico para inyectar al agente de economía.
    Incluye créditos disponibles, tasas y regulaciones vigentes.
    """
    macro = get_macro_context()
    if not macro:
        return "No hay contexto macroeconómico disponible."

    creditos = macro.get("creditos_pyme_vigentes", [])
    creditos_text = ""
    for i, c in enumerate(creditos, 1):
        req = ", ".join(c.get("requisitos", []))
        monto = f"ARS {c.get('monto_maximo_ars'):,.0f}" if c.get("monto_maximo_ars") else f"USD {c.get('monto_maximo_usd'):,.0f}"
        creditos_text += f"""
  [{i}] {c.get('nombre')}
      Tasa anual: {c.get('tasa_anual', 0)*100:.0f}%
      Plazo máximo: {c.get('plazo_maximo_meses')} meses
      Monto máximo: {monto}
      Destino: {c.get('destino')}
      Garantía: {c.get('garantia')}
      Requisitos: {req}
      Tiempo aprobación: {c.get('tiempo_aprobacion_dias')} días
"""

    regulaciones = "\n".join(f"  - {r}" for r in macro.get("regulaciones_relevantes", []))

    context = f"""
=== CONTEXTO MACROECONÓMICO — ARGENTINA ABRIL 2026 ===

INDICADORES MACRO:
- Inflación mensual (marzo 2026): {macro.get('inflacion_mensual_marzo', 0)*100:.1f}%
- Inflación interanual: {macro.get('inflacion_interanual', 0)*100:.0f}%
- Tipo de cambio oficial: ARS {macro.get('tipo_cambio_oficial')}/USD
- Tipo de cambio blue: ARS {macro.get('tipo_cambio_blue')}/USD
- Tasa BADLAR: {macro.get('tasa_badlar', 0)*100:.0f}% anual
- Tasa plazo fijo 30 días: {macro.get('tasa_plazo_fijo_30_dias', 0)*100:.0f}% anual
- Riesgo país: {macro.get('riesgo_pais')} puntos básicos
- PBI variación anual: +{macro.get('pbi_variacion_anual', 0)*100:.1f}%
- Desempleo: {macro.get('desempleo', 0)*100:.1f}%

POLÍTICA DE IMPORTACIONES:
{macro.get('politica_importaciones')}

CRÉDITOS PyME VIGENTES ({len(creditos)} opciones disponibles):
{creditos_text}

REGULACIONES RELEVANTES:
{regulaciones}
"""
    return context.strip()
