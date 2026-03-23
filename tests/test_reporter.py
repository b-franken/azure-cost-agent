"""Tests for reporter agent — savings extraction and action plan."""

from __future__ import annotations

from src.agents.reporter import _build_action_plan, _count_findings, _extract_savings


class TestExtractSavings:
    def test_extracts_per_item_costs(self) -> None:
        text = (
            "  - vm-1 (Standard_D4s_v5) ~$140.16/mo\n  - vm-2 (Standard_B2s) ~$30.00/mo"
        )
        assert _extract_savings(text) == 170.16

    def test_prefers_total_over_per_item(self) -> None:
        text = (
            "  - vm-1 ~$100.00/mo\n"
            "  - vm-2 ~$50.00/mo\n"
            "Total idle resource cost: ~$150.00/mo"
        )
        assert _extract_savings(text) == 150.00

    def test_no_costs(self) -> None:
        text = "No idle resources found."
        assert _extract_savings(text) == 0.0

    def test_integer_cost(self) -> None:
        text = "  - disk-1 ~$18/mo"
        assert _extract_savings(text) == 18.0


class TestCountFindings:
    def test_counts_bullet_items(self) -> None:
        text = "\n  - item1\n  - item2\n  - item3"
        assert _count_findings(text) == 3

    def test_no_findings(self) -> None:
        text = "No resources found."
        assert _count_findings(text) == 0


class TestBuildActionPlan:
    def test_builds_sorted_plan(self) -> None:
        result = _build_action_plan(
            idle="\n  - vm-1\n  - vm-2",
            orphaned="\n  - disk-1",
            oversized="",
            recommendations="",
            idle_savings=200.0,
            orphaned_savings=50.0,
        )
        assert "200" in result
        assert "50" in result
        assert result.index("200") < result.index("50")

    def test_no_actions(self) -> None:
        result = _build_action_plan(
            idle="none found.",
            orphaned="none found.",
            oversized="none found.",
            recommendations="",
            idle_savings=0.0,
            orphaned_savings=0.0,
        )
        assert "no immediate" in result.lower()
