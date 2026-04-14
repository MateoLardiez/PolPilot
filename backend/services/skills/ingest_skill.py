"""
Ingest Skill — Normaliza y enriquece el input del usuario.

Responsabilidades:
  - Limpiar whitespace y caracteres de control
  - Detectar keywords financieros y de mercado
  - Identificar si la consulta menciona datos en tiempo real
  - Devolver un IngestResult listo para el siguiente stage

No hace llamadas LLM. Es una función pura y sincrónica.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Palabras clave que indican necesidad de datos de mercado en tiempo real
_LIVE_DATA_KEYWORDS: list[str] = [
    "dólar", "dolar", "cotización", "cotizacion", "tipo de cambio",
    "blue", "oficial", "mep", "ccl", "reservas",
    "tasa", "tasas", "badlar", "bcra",
    "inflación", "inflacion", "ipc",
    "hoy", "ahora", "actual", "vigente", "tiempo real",
    "precio actual", "dato fresco",
]

# Palabras clave de finanzas internas
_FINANCE_KEYWORDS: list[str] = [
    "caja", "flujo", "ingresos", "egresos", "facturación", "facturacion",
    "deuda", "crédito interno", "credito interno", "proveedor", "proveedores",
    "clientes", "moroso", "morosos", "stock", "inventario",
    "empleados", "sueldos", "nómina", "nomina",
    "balance", "liquidez", "margen", "ganancia", "pérdida", "perdida",
    "cobrar", "pagar", "cheque", "efectivo",
]

# Palabras clave de economía / créditos externos
_ECONOMY_KEYWORDS: list[str] = [
    "crédito", "credito", "préstamo", "prestamo", "financiamiento",
    "banco", "línea", "linea", "subsidio", "afip", "arba",
    "regulación", "regulacion", "ley", "decreto",
    "pyme", "mipyme", "monotributo", "impuesto",
    "macro", "sector", "benchmark",
]


@dataclass
class IngestResult:
    """Resultado de la skill de ingesta."""
    normalized_message: str
    original_message: str
    word_count: int
    has_numbers: bool
    requires_live_data: bool
    finance_keywords: list[str] = field(default_factory=list)
    economy_keywords: list[str] = field(default_factory=list)
    live_keywords: list[str] = field(default_factory=list)

    @property
    def all_detected_keywords(self) -> list[str]:
        return self.finance_keywords + self.economy_keywords + self.live_keywords


def execute(user_message: str, company_id: str) -> IngestResult:
    """
    Normaliza el mensaje del usuario y extrae señales para los stages siguientes.

    Args:
        user_message: Mensaje crudo del usuario.
        company_id: ID de la empresa (para futuras personalizaciones).

    Returns:
        IngestResult con el mensaje normalizado y keywords detectadas.
    """
    # 1. Limpieza básica
    normalized = user_message.strip()
    normalized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", normalized)  # control chars
    normalized = re.sub(r"\s+", " ", normalized)

    lower = normalized.lower()

    # 2. Detección de keywords
    fin_kws = [kw for kw in _FINANCE_KEYWORDS if kw in lower]
    eco_kws = [kw for kw in _ECONOMY_KEYWORDS if kw in lower]
    live_kws = [kw for kw in _LIVE_DATA_KEYWORDS if kw in lower]

    return IngestResult(
        normalized_message=normalized,
        original_message=user_message,
        word_count=len(normalized.split()),
        has_numbers=bool(re.search(r"\d", normalized)),
        requires_live_data=bool(live_kws),
        finance_keywords=fin_kws,
        economy_keywords=eco_kws,
        live_keywords=live_kws,
    )
