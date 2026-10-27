"""InGame Studio Configuration."""

import os
from pydantic import BaseModel


def load_dotenv_file(path: str | None = None) -> None:
    """Loads KEY=VALUE pairs from a local .env into os.environ (real env vars win)."""
    path = path or os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


load_dotenv_file()


class Settings(BaseModel):
    """Application runtime settings."""

    app_name: str = "InGame Studio"
    version: str = "1.0.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    fps: int = int(os.getenv("STREAM_FPS", "25"))
    frame_interval_sec: float = 1.0 / float(os.getenv("STREAM_FPS", "25"))
    # The application generates its own seeded match by default. A fixture file
    # is an explicit override for replay/debugging, never the runtime source of
    # truth for the synthetic simulation.
    synthetic_events_file: str | None = os.getenv("SYNTHETIC_EVENTS_FILE") or None
    simulation_seed: int = int(os.getenv("SIMULATION_SEED", "2036"))
    schema_file: str = os.getenv(
        "SCHEMA_FILE",
        os.path.join(os.path.dirname(__file__), "..", "data", "schema.json"),
    )
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",
    ]


settings = Settings()
