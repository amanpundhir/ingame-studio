"""InGame Studio - the four-agent pipeline as a Microsoft Agent Framework workflow.

The Tactician, Pundit, Verifier and Director are Agent Framework executors wired into one
workflow graph:

    Tactician -> Pundit -> Verifier --(accepted, or retries used up)--> Director -> output
                    ^          |
                    +--(rejected, critique attached)--+

The shared state travels between the executors as a ``PipelineState`` message, so every
hand-off is explicit, the retry loop is an edge of the graph (not a Python ``for`` loop)
and the order of hand-offs is recorded in ``PipelineState.trace``.

The executors only call the same step methods as the plain-Python path in
``MatchIntelligenceOrchestrator``; the workflow adds orchestration, not new behaviour.
"""

import asyncio
import threading
from typing import Any, Dict, Optional

from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from backend.agents.models import VerifiedInsight
from backend.agents.pipeline_state import PipelineState


class TacticianExecutor(Executor):
    """Agent 1: turns a raw event into the verified fact pack (skipped when facts are given)."""

    def __init__(self, orchestrator: Any):
        super().__init__(id="tactician")
        self._orch = orchestrator

    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._orch.tactician_step(state)
        await ctx.send_message(state)


class PunditExecutor(Executor):
    """Agent 2: writes (or retrieves from the cache) the narrative, using any critique."""

    def __init__(self, orchestrator: Any):
        super().__init__(id="pundit")
        self._orch = orchestrator

    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._orch.pundit_step(state)
        await ctx.send_message(state)


class VerifierExecutor(Executor):
    """Agent 3: checks every name and number against the facts and either accepts or rejects."""

    def __init__(self, orchestrator: Any):
        super().__init__(id="verifier")
        self._orch = orchestrator

    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._orch.verifier_step(state)
        await ctx.send_message(state)


class DirectorExecutor(Executor):
    """Agent 4: adapts the verified text into personas, languages and overlays."""

    def __init__(self, orchestrator: Any):
        super().__init__(id="director")
        self._orch = orchestrator

    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[Never, VerifiedInsight]) -> None:
        await ctx.yield_output(self._orch.director_step(state))


def build_workflow(orchestrator: Any):
    """Builds the workflow graph for one orchestrator."""
    tactician = TacticianExecutor(orchestrator)
    pundit = PunditExecutor(orchestrator)
    verifier = VerifierExecutor(orchestrator)
    director = DirectorExecutor(orchestrator)
    return (
        WorkflowBuilder(start_executor=tactician, max_iterations=100, name="ingame-match-intelligence")
        .add_edge(tactician, pundit)
        .add_edge(pundit, verifier)
        # Rejected and retries left: back to the Pundit with the critique.
        .add_edge(verifier, pundit, condition=lambda s: not s.finished)
        # Accepted, or the retries are used up (the Director applies the deterministic fallback).
        .add_edge(verifier, director, condition=lambda s: s.finished)
        .build()
    )


def _run_blocking(coro_factory) -> Any:
    """Runs a coroutine to completion from synchronous code, even inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    box: Dict[str, Any] = {}

    def target() -> None:
        try:
            box["result"] = asyncio.run(coro_factory())
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["result"]


def run_pipeline(orchestrator: Any, state: PipelineState) -> VerifiedInsight:
    """Runs one event through the Agent Framework workflow and returns the verified insight."""

    async def go() -> VerifiedInsight:
        # A fresh workflow per run: the executors are stateless, and a workflow instance
        # cannot be run concurrently.
        workflow = build_workflow(orchestrator)
        result = await workflow.run(state)
        outputs = result.get_outputs()
        if not outputs:
            raise RuntimeError("Agent Framework workflow produced no output")
        return outputs[0]

    return _run_blocking(go)
