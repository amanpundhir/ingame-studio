"""InGame Studio - Multi-Agent Models.

Defines Pydantic data models for the 4-agent causal reasoning and verification workflow:
- FactPack (Agent 1: Tactician output)
- DraftNarrative (Agent 2: Pundit output)
- VerificationResult (Agent 3: Verifier output)
- PersonaOutputs (Agent 4: Director output)
- TelestratorVectors (Spatial telestrator data)
- VerifiedInsight (Final orchestrated broadcast artifact conforming to data/schema.json)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class FactPack(BaseModel):
    """Structured, verified tactical facts extracted from match telemetry."""

    event_id: str = Field(..., description="Unique event identifier, e.g. EVT_1001")
    match_minute: str = Field(..., description="Match clock display, e.g. '42:18'")
    period: int = Field(default=1, description="Match period: 1 or 2")
    frame_index: Optional[int] = Field(default=None, description="Tracking frame (25 Hz) the event happened on")
    event_type: str = Field(default="pass", description="Event type: pass, shot, tackle, turnover, pressure")
    passer_name: str = Field(..., description="Name of player initiating action")
    receiver_name: str = Field(..., description="Name of targeted teammate or recipient")
    team_name: str = Field(default="Northbridge Lions", description="Attacking / acting team")
    opponent_name: str = Field(default="Harbourside City", description="Defending team")
    start_x: float = Field(default=0.0, ge=0.0, le=105.0, description="Action start X coordinate (meters)")
    start_y: float = Field(default=0.0, ge=0.0, le=68.0, description="Action start Y coordinate (meters)")
    end_x: float = Field(default=0.0, ge=0.0, le=105.0, description="Action end X coordinate (meters)")
    end_y: float = Field(default=0.0, ge=0.0, le=68.0, description="Action end Y coordinate (meters)")
    pass_distance_m: float = Field(..., ge=0.0, le=105.0, description="Calculated Euclidean distance in meters")
    pass_difficulty: float = Field(..., ge=0.0, le=100.0, description="Pass Difficulty Rating (PDR) [0.0, 100.0]")
    ball_speed_kmh: float = Field(..., ge=0.0, le=150.0, description="Instantaneous ball velocity in km/h")
    chaos_index: float = Field(..., ge=0.0, le=100.0, description="Chaos vs Control Index (CCI) [0.0, 100.0]")
    xt_gained: float = Field(..., description="Expected Threat change Delta xT [-1.0, 1.0]")
    defenders_in_corridor: int = Field(default=0, ge=0, description="Opponents within 4.0m lateral passing corridor")
    defenders_in_cone: int = Field(default=0, ge=0, description="Opponents within 20-degree intercept angle cone")
    tactical_context: str = Field(default="Open play progression", description="Tactical description of phase of play")
    sub_type: Optional[str] = Field(default=None, description="Event sub type, e.g. curled_shot, standing_tackle")
    outcome: Optional[str] = Field(default=None, description="Event outcome, e.g. goal, won, saved")
    milestone: Optional[str] = Field(default=None, description="Optional milestone triggered by this event")

    @property
    def primary_actor(self) -> str:
        """Name of player initiating action (passer, shooter, tackler)."""
        return self.passer_name

    @property
    def secondary_actor(self) -> str:
        """Name of secondary player involved (receiver, goalkeeper, tackled opponent)."""
        return self.receiver_name


class DraftNarrative(BaseModel):
    """Draft causal narrative produced by Agent 2 (The Pundit)."""

    event_id: str
    narrative: str
    generation_attempt: int = 0
    model_used: str = "deterministic-heuristic"
    critique_addressed: Optional[str] = None
    from_cache: bool = False


class VerificationResult(BaseModel):
    """Grounding and consistency evaluation emitted by Agent 3 (The Ref).

    Supports both is_valid / is_grounded, grounding_score / score,
    and discrepancies / unsupported_claims for complete interoperability.
    """

    is_valid: bool = Field(default=True, description="True if draft passes all factual and numerical checks")
    grounding_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Grounding score between 0.0 and 1.0")
    critique: str = Field(default="", description="Detailed feedback if verification fails")
    discrepancies: List[str] = Field(default_factory=list, description="Specific factual contradictions or issues found")
    checked_citations: Dict[str, bool] = Field(default_factory=dict, description="Audit log of checked data citations")

    @model_validator(mode="before")
    @classmethod
    def _remap_legacy_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Map is_grounded -> is_valid
            if "is_grounded" in values and "is_valid" not in values:
                values["is_valid"] = values["is_grounded"]
            # Map score -> grounding_score
            if "score" in values and "grounding_score" not in values:
                values["grounding_score"] = values["score"]
            # Map unsupported_claims -> discrepancies
            if "unsupported_claims" in values and "discrepancies" not in values:
                values["discrepancies"] = values["unsupported_claims"]
        return values

    @property
    def is_grounded(self) -> bool:
        """Alias for is_valid."""
        return self.is_valid

    @property
    def score(self) -> float:
        """Alias for grounding_score."""
        return self.grounding_score

    @property
    def unsupported_claims(self) -> List[str]:
        """Alias for discrepancies."""
        return self.discrepancies


class TelestratorVectors(BaseModel):
    """Spatial telestrator vector annotations for broadcast graphics."""

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    distance_m: float
    corridor_width_m: float = 4.0
    cone_angle_deg: float = 20.0
    target_ring_radius_m: float = 2.5
    color_hex: str = "#00ff87"
    line_style: str = "solid"
    pressure_polygon: List[Dict[str, float]] = Field(default_factory=list)


class PersonaOutputs(BaseModel):
    """Four distinct audience persona narratives produced by Agent 4 (The Studio Director)."""

    casual_story: str
    tactical_analysis: str
    club_loyalist_story: str
    player_lock_story: str
    lower_third_ticker: str


class VerifiedInsight(BaseModel):
    """Final broadcast insight payload conforming to data/schema.json."""

    event_id: str
    grounding_score: float = Field(..., ge=0.0, le=1.0)
    verification_status: str = Field(..., description="'VERIFIED' or 'FALLBACK_APPLIED'")
    retries_attempted: int = Field(default=0, ge=0)
    agent_trace: Optional[List[str]] = Field(
        default=None,
        description="Ordered agent hand-offs, e.g. tactician, pundit#0, verifier:rejected, pundit#1, verifier:accepted, director",
    )
    frame_index: Optional[int] = Field(default=None, description="Tracking frame (25 Hz) of the moment the insight explains")
    match_clock: Optional[str] = Field(default=None, description="Match clock of the moment, e.g. '42:18'")
    period: Optional[int] = Field(default=None, description="Match period: 1 or 2")
    display_from_frame: Optional[int] = Field(default=None, description="First tracking frame the overlay should show")
    display_until_frame: Optional[int] = Field(default=None, description="Last tracking frame the overlay should show")
    display_duration_sec: Optional[float] = Field(default=None, description="How long the overlay stays on screen")
    casual_story: str
    tactical_analysis: str
    club_loyalist_story: str
    player_lock_story: str
    lower_third_ticker: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    telestrator_vectors: Dict[str, Any] = Field(default_factory=dict)
    translations: Optional[Dict[str, Dict[str, str]]] = None
    narrative_source: Optional[str] = Field(
        default=None,
        description="azure_foundry_live | azure_foundry_cache | local_template | fallback_template",
    )
