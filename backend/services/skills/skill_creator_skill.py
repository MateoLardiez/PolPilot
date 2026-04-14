"""
Skill Creator — Crea nuevas skills dinámicamente.

El agente puede llamar este skill cuando necesita una capacidad
que ninguna skill existente provee. Genera el archivo .py desde
un template y lo deja listo para que un dev implemente la lógica.

Uso: El agente llama execute() con nombre, descripción y caso de uso.
     El archivo queda en services/skills/ para que el dev lo complete.
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent

_SKILL_TEMPLATE = '''\
"""
{description}

Skill creada automáticamente por skill_creator_skill.
Caso de uso: {use_case}
Creada: {created_at}

TODO: Implementar lógica en execute()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class {class_name}Result:
    """Resultado de {full_skill_name}."""
    success: bool = True
    data: Optional[dict] = None
    message: str = ""

    def as_prompt_block(self) -> str:
        if not self.success or not self.data:
            return "[{upper_name}] Sin datos disponibles."
        return f"[{upper_name}]\\n{{self.message}}"


def execute(**kwargs) -> {class_name}Result:
    """
    {description}

    Caso de uso: {use_case}

    Args:
        **kwargs: Parámetros específicos — definir según el caso de uso.

    Returns:
        {class_name}Result
    """
    logger.info("{full_skill_name}: ejecutando (MVP mock)")

    # TODO: Implementar lógica real para: {use_case}
    return {class_name}Result(
        success=True,
        data={{"use_case": "{use_case}", "status": "mock"}},
        message="Skill en desarrollo. Caso de uso: {use_case}",
    )
'''


def execute(
    skill_name: str,
    description: str,
    use_case: str,
) -> dict:
    """
    Crea una nueva skill en el directorio de skills.

    Args:
        skill_name: Nombre de la skill sin sufijo _skill (ej: "alertas")
        description: Qué hace la skill
        use_case: Caso de uso específico que resuelve

    Returns:
        dict con success, file_path y message
    """
    # Normalizar nombre
    skill_name = skill_name.lower().strip().replace(" ", "_").replace("-", "_")
    if skill_name.endswith("_skill"):
        skill_name = skill_name[:-6]

    full_skill_name = f"{skill_name}_skill"
    file_name = f"{full_skill_name}.py"
    file_path = _SKILLS_DIR / file_name

    if file_path.exists():
        return {
            "success": False,
            "skill_name": full_skill_name,
            "file_path": str(file_path),
            "message": (
                f"La skill '{full_skill_name}' ya existe. "
                "Modificá el archivo directamente."
            ),
        }

    # CamelCase para el dataclass
    class_name = "".join(part.capitalize() for part in skill_name.split("_"))

    content = _SKILL_TEMPLATE.format(
        description=description,
        use_case=use_case,
        created_at=datetime.now().isoformat(),
        full_skill_name=full_skill_name,
        upper_name=full_skill_name.upper(),
        class_name=class_name,
    )

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info("skill_creator: creada %s", file_name)
        return {
            "success": True,
            "skill_name": full_skill_name,
            "file_path": str(file_path),
            "message": (
                f"Skill '{full_skill_name}' creada en {file_name}. "
                "Próximos pasos: 1) implementar execute(), "
                "2) registrar en services/skills/__init__.py, "
                "3) agregar la tool definition en super_agent.py."
            ),
        }
    except Exception as e:
        logger.error("skill_creator: error escribiendo %s: %s", file_name, e)
        return {
            "success": False,
            "skill_name": full_skill_name,
            "file_path": str(file_path),
            "message": f"Error al crear la skill: {e}",
        }
