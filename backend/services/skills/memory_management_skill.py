"""
Memory Management Skill — Gestión avanzada y persistente de memoria.

Extiende la memoria conversacional (que vive en RAM en shared_memory.py)
con persistencia a disco en JSON. El agente puede llamar este skill
para leer contexto histórico, escribir hechos clave y consultar el
perfil acumulado de la empresa.

Acciones disponibles:
  - read       : Lee hechos recientes y perfil de empresa
  - write      : Persiste un hecho o dato importante
  - get_facts  : Devuelve la lista completa de hechos clave
  - clear      : Limpia hechos conversacionales (preserva perfil)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Directorio de persistencia (backend/data/memory/)
_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "memory"


def _ensure_dir() -> None:
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _get_path(company_id: str) -> Path:
    return _MEMORY_DIR / f"{company_id}_memory.json"


def _load(company_id: str) -> dict:
    _ensure_dir()
    path = _get_path(company_id)
    if not path.exists():
        return {
            "company_id": company_id,
            "facts": [],
            "profile": {},
            "updated_at": None,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("memory_management: error cargando %s: %s", company_id, e)
        return {"company_id": company_id, "facts": [], "profile": {}, "updated_at": None}


def _save(company_id: str, data: dict) -> bool:
    _ensure_dir()
    try:
        data["updated_at"] = datetime.now().isoformat()
        _get_path(company_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception as e:
        logger.error("memory_management: error guardando %s: %s", company_id, e)
        return False


def execute(
    action: str,
    company_id: str,
    conversation_id: Optional[str] = None,
    content: Optional[str] = None,
) -> dict:
    """
    Gestión de memoria persistente por empresa.

    Args:
        action: "read" | "write" | "get_facts" | "clear"
        company_id: ID de la empresa
        conversation_id: ID de la conversación (para trazabilidad)
        content: Hecho o dato a guardar (solo action=write)

    Returns:
        dict con resultados según la acción
    """
    memory = _load(company_id)

    if action == "read":
        facts = memory.get("facts", [])
        return {
            "company_id": company_id,
            "facts_count": len(facts),
            "recent_facts": facts[-5:],
            "profile": memory.get("profile", {}),
            "updated_at": memory.get("updated_at"),
            "has_persistent_memory": bool(facts or memory.get("profile")),
        }

    elif action == "write":
        if not content:
            return {"success": False, "message": "content requerido para action=write"}

        fact = {
            "content": content,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
        }
        memory.setdefault("facts", []).append(fact)
        # Retener solo los últimos 50 hechos
        memory["facts"] = memory["facts"][-50:]

        saved = _save(company_id, memory)
        return {
            "success": saved,
            "message": f"Hecho guardado para {company_id}." if saved else "Error al guardar.",
            "facts_count": len(memory["facts"]),
        }

    elif action == "get_facts":
        facts = memory.get("facts", [])
        return {
            "company_id": company_id,
            "facts": facts[-10:],
            "total_facts": len(facts),
            "profile": memory.get("profile", {}),
        }

    elif action == "clear":
        profile = memory.get("profile", {})
        new_memory = {
            "company_id": company_id,
            "facts": [],
            "profile": profile,
        }
        saved = _save(company_id, new_memory)
        return {
            "success": saved,
            "message": (
                f"Memoria conversacional limpiada para {company_id}. "
                "Perfil preservado."
            ),
        }

    else:
        return {
            "error": f"Action desconocida: '{action}'. Opciones: read | write | get_facts | clear"
        }
