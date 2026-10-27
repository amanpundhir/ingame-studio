"""Tests for InGame Studio Frontend Build & Architecture Integrity.

Validates that:
- Frontend configuration files exist and are valid.
- Core components exist and conform to specifications.
- Build command executes cleanly and generates distribution assets.
"""

import json
import os
import subprocess
import shutil
from pathlib import Path
import pytest


@pytest.fixture
def frontend_dir():
    return Path(__file__).resolve().parents[1] / "frontend"


class TestFrontendArchitecture:
    """Verifies that all frontend components and configuration files exist."""

    def test_package_json_valid(self, frontend_dir):
        pkg_file = frontend_dir / "package.json"
        assert pkg_file.exists()
        with open(pkg_file, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        assert pkg["name"] == "ingame-studio-frontend"
        assert "react" in pkg["dependencies"]
        assert "typescript" in pkg["devDependencies"]
        assert "vite" in pkg["devDependencies"]

    def test_core_components_exist(self, frontend_dir):
        src = frontend_dir / "src"
        assert (src / "App.tsx").exists()
        assert (src / "main.tsx").exists()
        assert (src / "types.ts").exists()
        assert (src / "index.css").exists()

        components = src / "components"
        assert (components / "PitchVisualizer.tsx").exists()
        assert (components / "BroadcastOverlay.tsx").exists()
        assert (components / "PersonaToggle.tsx").exists()
        assert (components / "MetricsStrip.tsx").exists()
        assert (components / "ChaosRhythmBar.tsx").exists()
        assert (components / "LanguageSelector.tsx").exists()
        assert (components / "ProgressiveTimeline.tsx").exists()
        assert (components / "MatchStatsOverview.tsx").exists()
        assert (components / "PlayerPerformanceTable.tsx").exists()
        assert (components / "PlayerRatingsFantasy.tsx").exists()
        assert (components / "MatchRecapModal.tsx").exists()

    def test_high_contrast_kits_and_3d_ball(self, frontend_dir):
        pv_content = (frontend_dir / "src" / "components" / "PitchVisualizer.tsx").read_text(encoding="utf-8")
        # Northbridge Lions vibrant red and white
        assert "#EF0107" in pv_content
        assert "#FFFFFF" in pv_content
        # Harbourside signature sky blue and navy
        assert "#6CABDD" in pv_content
        assert "#1C2C5B" in pv_content
        # Daniel Roark neon yellow and Enzo Barreto neon orange
        assert "#CCFF00" in pv_content
        assert "#FF5500" in pv_content
        # 3D Ball physics rendering elements
        assert "altitudeScale" in pv_content
        assert "shadowAlpha" in pv_content
        assert "setLineDash" in pv_content

    def test_speed_controls_and_scrollable_analytics(self, frontend_dir):
        app_content = (frontend_dir / "src" / "App.tsx").read_text(encoding="utf-8")
        assert "speedMultiplier" in app_content
        assert "simulate_full" in app_content
        assert "ProgressiveTimeline" in app_content
        assert "MatchStatsOverview" in app_content
        assert "PlayerPerformanceTable" in app_content
        assert "PlayerRatingsFantasy" in app_content
        assert "overflowY" in app_content


    def test_services_exist(self, frontend_dir):
        services = frontend_dir / "src" / "services"
        assert (services / "websocket.ts").exists()
        ws_content = (services / "websocket.ts").read_text(encoding="utf-8")
        assert "metric_alert" in ws_content
        assert "onMetricAlert" in ws_content

    def test_r3_broadcast_studio_personalization_enhancements(self, frontend_dir):
        """Verifies Part 3 (R3) compliance across types and components."""
        src = frontend_dir / "src"
        types_content = (src / "types.ts").read_text(encoding="utf-8")
        assert "SpotlightMetric" in types_content
        assert "ClubPerspective" in types_content
        assert "MatchRecapData" in types_content
        assert "MetricAlert" in types_content

        modal_content = (src / "components" / "MatchRecapModal.tsx").read_text(encoding="utf-8")
        assert "Match Story" in modal_content
        assert "Tactical & xG Balance" in modal_content
        assert "MOTM & Fantasy Honours" in modal_content
        assert 'role="dialog"' in modal_content
        assert 'aria-modal="true"' in modal_content

        metrics_content = (src / "components" / "MetricsStrip.tsx").read_text(encoding="utf-8")
        assert "spotlightMetric" in metrics_content
        assert "SPOTLIGHT HERO KPI" in metrics_content

        persona_content = (src / "components" / "PersonaToggle.tsx").read_text(encoding="utf-8")
        assert "favoriteClub" in persona_content
        assert "selectedPlayerId" in persona_content
        # The persona and club are chosen once, in the header switcher, and apply to every tab.
        switcher_content = (src / "components" / "PersonaSwitcher.tsx").read_text(encoding="utf-8")
        assert "Northbridge Lions" in switcher_content and "Harbourside" in switcher_content
        assert "PersonaSwitcher" in (src / "App.tsx").read_text(encoding="utf-8")
        assert "LOCKED" in persona_content

        broadcast_content = (src / "components" / "BroadcastOverlay.tsx").read_text(encoding="utf-8")
        assert "metricAlert" in broadcast_content
        assert "DEFAULT_TICKERS" in broadcast_content
        assert 'dir={isRtl ? \'rtl\' : \'ltr\'}' in broadcast_content


class TestFrontendBuildVerification:
    """Verifies that the frontend TypeScript code compiles cleanly to distribution bundle."""

    def test_frontend_compiles_cleanly(self, frontend_dir):
        # Check if node_modules exists
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            pytest.skip("node_modules not yet installed; skipping compilation test")

        node = shutil.which("node")
        assert node, "Node.js is required to compile the frontend"
        typecheck = subprocess.run(
            [node, str(frontend_dir / "node_modules" / "typescript" / "bin" / "tsc"), "--noEmit"],
            cwd=str(frontend_dir), capture_output=True, text=True,
        )
        assert typecheck.returncode == 0, f"Frontend TypeScript check failed:\n{typecheck.stderr}\n{typecheck.stdout}"

        # Load Vite through its API without bundling vite.config.ts. The
        # sandboxed test runner cannot traverse above the workspace root while
        # esbuild bundles that config, so pass the equivalent local build
        # configuration directly.
        build_script = (
            "import { build } from 'vite'; "
            "import react from '@vitejs/plugin-react'; "
            "await build({ configFile: false, root: process.cwd(), plugins: [react()], "
            "build: { outDir: 'dist', sourcemap: true } });"
        )
        result = subprocess.run(
            [node, "--input-type=module", "-e", build_script],
            cwd=str(frontend_dir), capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Frontend build failed:\n{result.stderr}\n{result.stdout}"
        dist_dir = frontend_dir / "dist"
        assert dist_dir.exists()
        assert (dist_dir / "index.html").exists()
