"""InGame Studio Multi-Agent Reasoning & Verification Package."""

from backend.agents.models import (
    FactPack,
    DraftNarrative,
    VerificationResult,
    PersonaOutputs,
    TelestratorVectors,
    VerifiedInsight,
)
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.pundit_agent import PunditAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.orchestrator import MatchIntelligenceOrchestrator
from backend.agents.foundry_adapter import AzureFoundryAdapter

__all__ = [
    "FactPack",
    "DraftNarrative",
    "VerificationResult",
    "PersonaOutputs",
    "TelestratorVectors",
    "VerifiedInsight",
    "TacticianAgent",
    "PunditAgent",
    "VerifierAgent",
    "StudioDirectorAgent",
    "MatchIntelligenceOrchestrator",
    "AzureFoundryAdapter",
]
