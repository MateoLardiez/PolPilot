"""
System Prompt Skill — Lee y actualiza los system prompts del agente.

Permite al agente acceder y modificar su propio system prompt
sin necesidad de redeploy. Útil para ajustar tono, agregar nuevas
instrucciones o registrar qué skills están disponibles.

Prompts conocidos:
  - super_agent_system   : Prompt principal de Angela (síntesis + tool use)
  - orchestrator_system  : Prompt legacy (solo lectura, no modificar)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

_KNOWN_PROMPTS: dict[str, str] = {
    "super_agent_system": "super_agent_system.md",
    "orchestrator_system": "orchestrator_system.md",  # legacy — no modificar
}

_READ_ONLY = {"orchestrator_system"}


def execute(
    action: str,
    prompt_name: str,
    content: Optional[str] = None,
) -> dict:
    """
    Gestión de system prompts del agente.

    Args:
        action: "read" | "update" | "reset" | "list"
        prompt_name: Clave del prompt (super_agent_system, orchestrator_system)
        content: Nuevo contenido (solo action=update)

    Returns:
        dict con resultado de la operación
    """
    if action == "list":
        return {
            "available_prompts": list(_KNOWN_PROMPTS.keys()),
            "read_only": list(_READ_ONLY),
            "prompts_dir": str(_PROMPTS_DIR),
        }

    if prompt_name not in _KNOWN_PROMPTS:
        return {
            "error": (
                f"Prompt '{prompt_name}' no encontrado. "
                f"Disponibles: {list(_KNOWN_PROMPTS.keys())}"
            )
        }

    prompt_file = _PROMPTS_DIR / _KNOWN_PROMPTS[prompt_name]

    # ── READ ──────────────────────────────────────────────
    if action == "read":
        if not prompt_file.exists():
            return {
                "error": f"Archivo {prompt_file.name} no existe",
                "prompt_name": prompt_name,
            }
        try:
            text = prompt_file.read_text(encoding="utf-8")
            return {
                "prompt_name": prompt_name,
                "file": prompt_file.name,
                "char_count": len(text),
                "content": text[:2000],
                "truncated": len(text) > 2000,
            }
        except Exception as e:
            return {"error": str(e), "prompt_name": prompt_name}

    # ── UPDATE ────────────────────────────────────────────
    elif action == "update":
        if prompt_name in _READ_ONLY:
            return {
                "error": f"El prompt '{prompt_name}' es de solo lectura (legacy)."
            }
        if not content:
            return {"error": "content requerido para action=update"}

        backup_file = prompt_file.with_suffix(".md.bak")
        try:
            # Backup del original
            if prompt_file.exists():
                backup_file.write_text(
                    prompt_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
            prompt_file.write_text(content, encoding="utf-8")
            logger.info("system_prompt: actualizado %s", prompt_file.name)
            return {
                "success": True,
                "prompt_name": prompt_name,
                "new_char_count": len(content),
                "message": (
                    f"Prompt '{prompt_name}' actualizado. "
                    f"Backup en {backup_file.name}. "
                    "Nota: el cambio aplica en la próxima llamada al agente."
                ),
            }
        except Exception as e:
            logger.error("system_prompt: error actualizando %s: %s", prompt_file.name, e)
            return {"success": False, "error": str(e)}

    # ── RESET ─────────────────────────────────────────────
    elif action == "reset":
        if prompt_name in _READ_ONLY:
            return {"error": f"El prompt '{prompt_name}' es de solo lectura."}

        backup_file = prompt_file.with_suffix(".md.bak")
        if not backup_file.exists():
            return {"error": f"No hay backup disponible para '{prompt_name}'."}
        try:
            original = backup_file.read_text(encoding="utf-8")
            prompt_file.write_text(original, encoding="utf-8")
            logger.info("system_prompt: restaurado %s desde backup", prompt_file.name)
            return {
                "success": True,
                "message": f"Prompt '{prompt_name}' restaurado desde backup.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    else:
        return {
            "error": f"Action desconocida: '{action}'. Opciones: read | update | reset | list"
        }
