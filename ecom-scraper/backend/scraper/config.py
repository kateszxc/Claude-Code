import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is optional
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    brave_api_key: str = os.getenv("BRAVE_API_KEY", "")
    serpapi_key: str = os.getenv("SERPAPI_KEY", "")
    hunter_api_key: str = os.getenv("HUNTER_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    concurrency: int = _int("SCRAPER_CONCURRENCY", 6)
    timeout_seconds: int = _int("SCRAPER_TIMEOUT_SECONDS", 15)
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        ]
    )
    output_dir: Path = Path(__file__).resolve().parent.parent / "output"
    user_agent: str = (
        "Mozilla/5.0 (compatible; EcomBrandResearchBot/1.0; +https://example.com/bot)"
    )

    @property
    def search_provider(self) -> str:
        if self.brave_api_key:
            return "brave"
        if self.serpapi_key:
            return "serpapi"
        return "duckduckgo"


settings = Settings()
