"""InGame Studio - Automated Tests for Azure MCP Server & Foundry Adapter.

Validates Part 5 (R5) compliance:
- Model Context Protocol (MCP) JSON-RPC 2.0 protocol specifications and error handling
- All 7 registered tactical, kinematic, and recap tools
- Microsoft AI Foundry / Azure OpenAI adapter with guaranteed zero-cost local fallback
- Containerization and Infrastructure-as-Code artifacts (Dockerfile, Bicep IaC, CI/CD)
"""

import json
import os
import unittest
from unittest.mock import patch, MagicMock

import pytest

from backend.mcp_server import InGameMCPServer
from backend.agents.foundry_adapter import AzureFoundryAdapter
from backend.agents.models import FactPack, DraftNarrative
from backend.agents.verifier_agent import VerifierAgent


@pytest.fixture(scope="module")
def mcp_server():
    """Provides a initialized InGameMCPServer instance for testing."""
    return InGameMCPServer()


@pytest.fixture(scope="module")
def sample_fact_pack():
    """Provides a standard verified FactPack for narrative testing."""
    return FactPack(
        event_id="EVT_TEST_001",
        match_minute="28:14",
        period=1,
        team_name="Northbridge Lions",
        opponent_name="Harbourside City",
        event_type="pass",
        passer_id="NBL_07",
        passer_name="Kofi Sarpong",
        receiver_id="NBL_29",
        receiver_name="Kai Halvorsen",
        pass_distance_m=28.4,
        ball_speed_kmh=48.2,
        pass_difficulty=64.8,
        defenders_in_corridor=2,
        defenders_in_cone=1,
        xt_gained=0.18,
        chaos_index=42.5,
        tactical_context="Right-halfspace vertical penetration breaking midfield defensive line",
    )


class TestMCPServerProtocol:
    """Verifies JSON-RPC 2.0 protocol compliance for the Azure MCP Server."""

    def test_initialize_handshake(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-runner", "version": "1.0"},
            },
        }
        res = mcp_server.handle_request(req)
        assert res["jsonrpc"] == "2.0"
        assert res["id"] == 1
        assert "result" in res
        assert res["result"]["protocolVersion"] == "2024-11-05"
        assert res["result"]["serverInfo"]["name"] == "ingame-azure-mcp-server"
        assert "tools" in res["result"]["capabilities"]

    def test_ping_and_notifications(self, mcp_server):
        ping_req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
        ping_res = mcp_server.handle_request(ping_req)
        assert ping_res["jsonrpc"] == "2.0"
        assert ping_res["id"] == 2
        assert ping_res["result"] == {}

        init_req = {"jsonrpc": "2.0", "id": 3, "method": "initialized"}
        init_res = mcp_server.handle_request(init_req)
        assert init_res["result"] == {}

    def test_tools_list_registers_all_seven_tools(self, mcp_server):
        req = {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}
        res = mcp_server.handle_request(req)
        assert "result" in res
        tools = res["result"]["tools"]
        assert len(tools) == 7

        tool_names = {t["name"] for t in tools}
        expected_tools = {
            "get_live_telemetry",
            "calculate_pass_difficulty",
            "calculate_chaos_control_index",
            "get_player_metrics",
            "get_match_analytics_overview",
            "get_match_recap",
            "verify_narrative_grounding",
        }
        assert expected_tools == tool_names

        for tool in tools:
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_invalid_jsonrpc_request_returns_error(self, mcp_server):
        bad_req = {"foo": "bar"}
        res = mcp_server.handle_request(bad_req)
        assert "error" in res
        assert res["error"]["code"] == -32600

    def test_unknown_method_returns_error_32601(self, mcp_server):
        req = {"jsonrpc": "2.0", "id": 5, "method": "non_existent_method"}
        res = mcp_server.handle_request(req)
        assert "error" in res
        assert res["error"]["code"] == -32601

    def test_unknown_tool_call_returns_error_32601(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "ghost_tool", "arguments": {}},
        }
        res = mcp_server.handle_request(req)
        assert "error" in res
        assert res["error"]["code"] == -32601

    def test_missing_required_tool_arguments_returns_error_32602(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "calculate_pass_difficulty", "arguments": {}},
        }
        res = mcp_server.handle_request(req)
        assert "error" in res
        assert res["error"]["code"] == -32602


class TestMCPToolsExecution:
    """Verifies functional execution and data accuracy for each of the 7 MCP tools."""

    def test_tool_get_live_telemetry(self, mcp_server):
        frame = mcp_server.call_tool("get_live_telemetry", {"frame_index": 5})
        assert "ball" in frame
        assert "players" in frame
        assert len(frame["players"]) == 22
        assert "period" in frame
        assert "timestamp" in frame

    def test_tool_calculate_pass_difficulty(self, mcp_server):
        args = {
            "distance_m": 35.0,
            "defenders_in_cone": 2,
            "defenders_in_corridor": 3,
            "ball_speed_kmh": 50.0,
        }
        result = mcp_server.call_tool("calculate_pass_difficulty", args)
        assert "pass_difficulty_rating" in result
        pdr = result["pass_difficulty_rating"]
        assert 0.0 <= pdr <= 100.0
        assert result["distance_m"] == 35.0
        assert result["unit"] == "percent"

    def test_tool_calculate_chaos_control_index(self, mcp_server):
        args = {
            "recent_turnovers": 4,
            "ball_speed_variance": 45.0,
            "defensive_line_displacement_m": 12.0,
        }
        result = mcp_server.call_tool("calculate_chaos_control_index", args)
        assert "chaos_control_index" in result
        cci = result["chaos_control_index"]
        assert 0.0 <= cci <= 100.0
        assert result["tactical_zone"] in ("High Control", "Balanced Contest", "Chaos / High Transition")

    def test_tool_get_player_metrics_valid_and_invalid(self, mcp_server):
        sarpong = mcp_server.call_tool("get_player_metrics", {"player_id": "NBL_07"})
        assert sarpong["player_id"] == "NBL_07"
        assert sarpong["name"] == "Kofi Sarpong"
        assert sarpong["team"] == "home"
        assert sarpong["role"] == "FW"
        assert "rating" in sarpong
        assert "top_speed_kmh" in sarpong

        hagen = mcp_server.call_tool("get_player_metrics", {"player_id": "HSC_09"})
        assert hagen["player_id"] == "HSC_09"
        assert hagen["name"] == "Anders Hagen"

        with pytest.raises(ValueError):
            mcp_server.call_tool("get_player_metrics", {"player_id": "INVALID_999"})

    def test_tool_get_match_analytics_overview(self, mcp_server):
        overview = mcp_server.call_tool("get_match_analytics_overview", {})
        assert "score" in overview
        assert "possession" in overview
        assert "xg" in overview
        assert "shots" in overview
        assert "passes" in overview

    def test_tool_get_match_recap(self, mcp_server):
        recap = mcp_server.call_tool("get_match_recap", {})
        assert recap["match_id"] == "IGS_2026_NBL_HSC"
        assert recap["status"] == "FT"
        assert "match_story" in recap
        assert len(recap["turning_points"]) >= 4
        assert "xg_balance" in recap
        assert recap["man_of_the_match"]["name"] != "Not available"
        assert 0.0 <= recap["man_of_the_match"]["rating"] <= 10.0
        assert len(recap["tactical_entropy_shifts"]) == 4
        assert "localized_summaries" in recap
        for lang in ("en", "es"):
            assert lang in recap["localized_summaries"]

    def test_tool_verify_narrative_grounding(self, mcp_server, sample_fact_pack):
        # Grounded narrative
        grounded_text = (
            f"In minute {sample_fact_pack.match_minute}, {sample_fact_pack.passer_name} completed a "
            f"{sample_fact_pack.pass_distance_m:.1f}m pass to {sample_fact_pack.receiver_name} at "
            f"{sample_fact_pack.ball_speed_kmh:.1f} km/h with a {sample_fact_pack.pass_difficulty:.1f}% difficulty rating."
        )
        res = mcp_server.call_tool(
            "verify_narrative_grounding",
            {"fact_pack": sample_fact_pack.model_dump(), "draft_narrative": grounded_text},
        )
        assert res["is_valid"] is True
        assert res["grounding_score"] >= 0.99

        # Corrupted narrative (altered metrics)
        corrupted_text = (
            f"In minute {sample_fact_pack.match_minute}, {sample_fact_pack.passer_name} completed a "
            f"99.0m pass to {sample_fact_pack.receiver_name} at 120.0 km/h with a 10.0% difficulty rating."
        )
        res_bad = mcp_server.call_tool(
            "verify_narrative_grounding",
            {"fact_pack": sample_fact_pack.model_dump(), "draft_narrative": corrupted_text},
        )
        assert res_bad["is_valid"] is False
        assert len(res_bad["discrepancies"]) > 0


class TestAzureFoundryAdapter:
    """Verifies Microsoft AI Foundry adapter behavior and zero-cost local fallback."""

    def test_default_initialization_activates_local_fallback(self):
        # Ensure no Azure env vars interfere
        with patch.dict(os.environ, {}, clear=True):
            adapter = AzureFoundryAdapter()
            assert adapter.is_cloud_connected() is False
            status = adapter.get_status()
            assert status["mode"] == "local_fallback"
            assert status["connected"] is False

    def test_generate_narrative_in_fallback_passes_verifier(self, sample_fact_pack):
        adapter = AzureFoundryAdapter()
        draft = adapter.generate_narrative(sample_fact_pack)
        assert isinstance(draft, DraftNarrative)
        assert draft.model_used == "deterministic-foundry-fallback"

        # Verify against VerifierAgent
        verifier = VerifierAgent()
        result = verifier.verify(sample_fact_pack, draft)
        assert result.is_valid is True
        assert result.grounding_score >= 0.99

    def test_evaluate_grounding(self, sample_fact_pack):
        adapter = AzureFoundryAdapter()
        valid_text = (
            f"At {sample_fact_pack.match_minute}, {sample_fact_pack.passer_name} passed "
            f"{sample_fact_pack.pass_distance_m:.1f}m to {sample_fact_pack.receiver_name} at "
            f"{sample_fact_pack.ball_speed_kmh:.1f} km/h with {sample_fact_pack.pass_difficulty:.1f}% difficulty."
        )
        res = adapter.evaluate_grounding(sample_fact_pack, valid_text)
        assert res.is_valid is True

    def test_generate_recap_story(self):
        adapter = AzureFoundryAdapter()
        stats = {
            "score": {"home": 2, "away": 2},
            "xg": {"home": 1.84, "away": 1.72},
        }
        story = adapter.generate_recap_story(stats)
        assert "Northbridge Lions" in story
        assert "Harbourside City" in story
        assert "2-2" in story
        assert "1.84" in story

    def test_mocked_cloud_connection_success(self, sample_fact_pack):
        adapter = AzureFoundryAdapter(
            endpoint="https://fake-ingame-foundry.openai.azure.com",
            api_key="sk-fake-azure-openai-key-12345678",
            deployment="gpt-4o",
        )
        assert adapter.is_cloud_connected() is True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            f"At {sample_fact_pack.match_minute}, {sample_fact_pack.passer_name} hit a "
                            f"{sample_fact_pack.pass_distance_m:.1f}m pass to {sample_fact_pack.receiver_name} clocked at "
                            f"{sample_fact_pack.ball_speed_kmh:.1f} km/h with {sample_fact_pack.pass_difficulty:.1f}% difficulty."
                        )
                    }
                }
            ]
        }

        with patch("httpx.Client.post", return_value=mock_response):
            draft = adapter.generate_narrative(sample_fact_pack)
            assert "azure-foundry-gpt-4o" in draft.model_used
            assert sample_fact_pack.passer_name in draft.narrative

    def test_mocked_cloud_connection_failure_falls_back_cleanly(self, sample_fact_pack):
        adapter = AzureFoundryAdapter(
            endpoint="https://fake-ingame-foundry.openai.azure.com",
            api_key="sk-fake-azure-openai-key-12345678",
            deployment="gpt-4o",
        )
        assert adapter.is_cloud_connected() is True

        # Simulate network failure
        with patch("httpx.Client.post", side_effect=Exception("Network connection timeout")):
            draft = adapter.generate_narrative(sample_fact_pack)
            assert draft.model_used == "deterministic-foundry-fallback"
            assert sample_fact_pack.passer_name in draft.narrative


class TestInfrastructureAndContainerArtifacts:
    """Verifies syntax and required specifications of container and IaC files."""

    def test_dockerfile_contents(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        dockerfile_path = os.path.join(repo_root, "Dockerfile")
        assert os.path.exists(dockerfile_path), "Dockerfile must exist at repository root."

        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Multi-stage validation
        assert "FROM node:20-alpine AS frontend-builder" in content
        assert "FROM python:3.12-slim AS runner" in content
        assert "COPY --from=frontend-builder" in content
        # Security: Non-root user
        assert "useradd -r" in content
        assert "USER ingame" in content
        # Healthcheck & port
        assert "HEALTHCHECK" in content
        assert "EXPOSE 8000" in content
        assert "uvicorn" in content

    def test_dockerignore_contents(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        dockerignore_path = os.path.join(repo_root, ".dockerignore")
        assert os.path.exists(dockerignore_path)
        with open(dockerignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert ".venv" in content
        assert "node_modules" in content

    def test_azure_bicep_and_parameters(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        bicep_path = os.path.join(repo_root, "infra", "main.bicep")
        params_path = os.path.join(repo_root, "infra", "main.parameters.json")

        assert os.path.exists(bicep_path), "infra/main.bicep must exist."
        assert os.path.exists(params_path), "infra/main.parameters.json must exist."

        with open(bicep_path, "r", encoding="utf-8") as f:
            bicep = f.read()

        # Verify key cloud resources are declared
        assert "Microsoft.OperationalInsights/workspaces" in bicep
        assert "Microsoft.ContainerRegistry/registries" in bicep
        assert "Microsoft.App/managedEnvironments" in bicep
        assert "Microsoft.SignalRService" not in bicep, "Web PubSub is not used by the app and must not be provisioned."
        assert "maxReplicas: 1" in bicep, "match state and cache are in memory: one replica only"
        assert "AZURE_OPENAI_API_KEY" in bicep and "secretRef" in bicep, "Foundry key must reach the app as a secret"
        assert "registries:" in bicep, "the container app must be able to pull from the registry"
        assert "Microsoft.App/containerApps" in bicep
        assert "output containerAppFqdn" in bicep

        # Verify parameters JSON is valid JSON with required parameter values
        with open(params_path, "r", encoding="utf-8") as f:
            params = json.load(f)
        assert "$schema" in params
        assert "parameters" in params
        p = params["parameters"]
        assert "location" in p
        assert "environmentName" in p
        assert "foundryApiKey" not in p, "secrets must not be stored in the parameters file"
        assert "targetPort" in p

    def test_github_actions_workflow(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        workflow_path = os.path.join(repo_root, ".github", "workflows", "deploy-azure.yml")
        assert os.path.exists(workflow_path), ".github/workflows/deploy-azure.yml must exist."

        with open(workflow_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "name: Build, Verify and Deploy InGame Studio to Azure" in content
        assert "jobs:" in content
        assert "verify:" in content
        assert "deploy:" in content
        assert "python run_all_tests.py" in content
        assert "npm run build" in content
