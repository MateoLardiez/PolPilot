import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "PolPilot API"
    VERSION: str = "3.0.0"

    # Anthropic — Agent SDK
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ORCHESTRATOR_MODEL: str = os.getenv("ORCHESTRATOR_MODEL", "claude-sonnet-4-6")

    # Limits
    MAX_QUESTIONS_PER_TOPIC: int = 5
    RELEVANCE_THRESHOLD: float = 0.2

    # Empresa por defecto (demo)
    DEFAULT_EMPRESA_ID: str = os.getenv("DEFAULT_EMPRESA_ID", "emp_001")

    # Paths
    PROMPTS_DIR: str = os.path.join(os.path.dirname(__file__), "prompts")

    @property
    def has_api_key(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)


settings = Settings()
