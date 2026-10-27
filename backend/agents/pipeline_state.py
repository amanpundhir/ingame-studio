"""State passed between the agents of the match-intelligence pipeline."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.agents.models import FactPack, VerificationResult


@dataclass
class PipelineState:
    """Everything the four agents share while one event is processed.

    The Tactician fills ``fact_pack``; the Pundit and Verifier loop on ``draft`` and
    ``critique`` until the narrative is accepted or the retries are used up
    (``finished``); the Director turns the result into the final insight.
    """

    allow_live: bool = False
    # Input: either a raw event (the Tactician extracts the facts) or ready facts.
    event: Optional[Dict[str, Any]] = None
    telemetry_frame: Optional[Dict[str, Any]] = None
    defenders: Optional[List[Dict[str, Any]]] = None
    fact_pack: Optional[FactPack] = None
    # Pundit / Verifier loop.
    attempt: int = 0
    max_retries: int = 2
    critique: Optional[str] = None
    draft: Optional[Any] = None
    verification: Optional[VerificationResult] = None
    verified_narrative: Optional[str] = None
    final_draft: Optional[Any] = None
    retries_attempted: int = 0
    finished: bool = False
    # Ordered record of every hand-off, for transparency, e.g.
    # ["tactician", "pundit#0", "verifier:rejected", "pundit#1", "verifier:accepted", "director"].
    trace: List[str] = field(default_factory=list)
