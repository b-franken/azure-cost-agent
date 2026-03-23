"""Tests for advisor agent tools."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.advisor import (
    _classify,
    _extract_recommendation,
    get_prioritized_recommendations,
    get_reservation_recommendations,
)


def _make_ctx(recs: list[object]) -> MagicMock:
    clients = MagicMock()
    clients.subscription_ids = ["test-sub"]
    advisor_mock = MagicMock()
    advisor_mock.recommendations.list.return_value = recs
    clients.advisor_for.return_value = advisor_mock
    ctx = MagicMock()
    ctx.kwargs = {"azure_clients": clients}
    return ctx


def _make_recommendation(
    impact: str,
    problem: str,
    solution: str,
    resource_id: str,
) -> MagicMock:
    rec = MagicMock()
    rec.impact = impact
    rec.short_description.problem = problem
    rec.short_description.solution = solution
    rec.resource_metadata.resource_id = resource_id
    return rec


class TestClassify:
    def test_rightsizing(self) -> None:
        assert _classify("Right-size your VM") == "Rightsizing"

    def test_reservations(self) -> None:
        assert _classify("Buy reserved instance") == "Reservations"

    def test_unused(self) -> None:
        assert _classify("Shutdown unused VM") == "Unused resources"

    def test_other(self) -> None:
        assert _classify("Enable diagnostics") == "Other"


class TestExtractRecommendation:
    def test_extracts_fields(self) -> None:
        rec = _make_recommendation(
            "High",
            "Right-size VM",
            "Downsize to D2s_v5",
            "/sub/rg/providers/compute/vm-oversized",
        )
        result = _extract_recommendation(rec)
        assert result["impact"] == "High"
        assert result["resource"] == "vm-oversized"
        assert result["category"] == "Rightsizing"


class TestGetPrioritizedRecommendations:
    def test_sorts_by_impact(self) -> None:
        recs = [
            _make_recommendation("Low", "Minor fix", "Do X", "/sub/low"),
            _make_recommendation("High", "Right-size VM", "Downsize", "/sub/high"),
            _make_recommendation("Medium", "Review cost", "Check Y", "/sub/med"),
        ]
        result = get_prioritized_recommendations(ctx=_make_ctx(recs))
        high_pos = result.index("HIGH")
        low_pos = result.index("LOW")
        assert high_pos < low_pos

    def test_groups_by_category(self) -> None:
        recs = [
            _make_recommendation("High", "Right-size VM", "Downsize", "/sub/vm"),
            _make_recommendation(
                "Medium", "Buy reserved instance", "Purchase RI", "/sub/ri"
            ),
        ]
        result = get_prioritized_recommendations(ctx=_make_ctx(recs))
        assert "Rightsizing" in result
        assert "Reservations" in result

    def test_shows_high_impact_count(self) -> None:
        recs = [
            _make_recommendation("High", "Fix A", "Do A", "/sub/a"),
            _make_recommendation("High", "Fix B", "Do B", "/sub/b"),
        ]
        result = get_prioritized_recommendations(ctx=_make_ctx(recs))
        assert "2 high-impact" in result

    def test_empty(self) -> None:
        result = get_prioritized_recommendations(ctx=_make_ctx([]))
        assert "No cost optimization" in result


class TestGetReservationRecommendations:
    def test_filters_reservation_recs(self) -> None:
        recs = [
            _make_recommendation(
                "Medium",
                "Buy reserved instance for VM",
                "Purchase 1-year RI",
                "/sub/rg/providers/compute/vm-prod",
            ),
            _make_recommendation(
                "High",
                "Right-size VM",
                "Downsize to D2s_v5",
                "/sub/rg/providers/compute/vm-oversized",
            ),
        ]
        result = get_reservation_recommendations(ctx=_make_ctx(recs))
        assert "reserved" in result.lower()
        assert "Right-size" not in result

    def test_no_reservations(self) -> None:
        recs = [
            _make_recommendation("High", "Right-size VM", "Downsize", "/sub/rg/vm"),
        ]
        result = get_reservation_recommendations(ctx=_make_ctx(recs))
        assert "No reservation" in result
