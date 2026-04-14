import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "PolPilot Orchestrator API"
    VERSION: str = "0.1.0"

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ORCHESTRATOR_MODEL: str = os.getenv("ORCHESTRATOR_MODEL", "claude-sonnet-4-6")
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")

    # Agent endpoints (si corren como servicios separados)
    AGENT_FINANZAS_URL: str = os.getenv("AGENT_FINANZAS_URL", "http://localhost:8000/agents/finanzas/query")
    AGENT_ECONOMIA_URL: str = os.getenv("AGENT_ECONOMIA_URL", "http://localhost:8000/agents/economia/query")

    # Limits
    MAX_REASK_ITERATIONS: int = 3
    MAX_QUESTIONS_PER_TOPIC: int = 5
    RELEVANCE_THRESHOLD: float = 0.2

    # Inter-agent collaboration
    MAX_INTER_CALLS_PER_THREAD: int = int(os.getenv("MAX_INTER_CALLS_PER_THREAD", "4"))
    MAX_CHAIN_DEPTH: int = int(os.getenv("MAX_CHAIN_DEPTH", "3"))

    # Paths
    PROMPTS_DIR: str = os.path.join(os.path.dirname(__file__), "prompts")


settings = Settings()
