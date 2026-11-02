"""
Tests for reports API endpoints.
"""
import pytest

from mock_data import orders


class TestQuarterlyReports:
    """Test suite for the quarterly performance report."""

    def test_unfiltered_covers_every_order(self, client):
        """Test that quarter totals add up to every 2025 order."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert [q["quarter"] for q in data] == sorted(q["quarter"] for q in data)
        assert sum(q["total_orders"] for q in data) == len(
            [o for o in orders if o["order_date"].startswith("2025")]
        )

    def test_warehouse_filter_limits_orders(self, client):
        """Test that the warehouse filter matches the orders endpoint."""
        expected = client.get("/api/orders?warehouse=San Francisco").json()
        data = client.get("/api/reports/quarterly?warehouse=San Francisco").json()

        assert sum(q["total_orders"] for q in data) == len(expected)

    def test_quarter_month_filter_returns_one_quarter(self, client):
        """Test that a quarter filter returns only that quarter."""
        data = client.get("/api/reports/quarterly?month=Q2-2025").json()

        assert [q["quarter"] for q in data] == ["Q2-2025"]

    def test_delivered_filter_gives_full_fulfillment(self, client):
        """Test that filtering to delivered orders yields a 100% fulfillment rate."""
        data = client.get("/api/reports/quarterly?status=delivered").json()

        assert data
        for q in data:
            assert q["fulfillment_rate"] == 100.0


class TestMonthlyTrends:
    """Test suite for month-over-month trends."""

    @pytest.mark.parametrize("params", [
        "",
        "?warehouse=Tokyo",
        "?category=Sensors",
        "?status=shipped",
    ])
    def test_filters_match_orders_endpoint(self, client, params):
        """Test that each filter yields the same order count as /api/orders."""
        expected = client.get(f"/api/orders{params}").json()
        data = client.get(f"/api/reports/monthly-trends{params}").json()

        assert sum(m["order_count"] for m in data) == len(expected)
        assert round(sum(m["revenue"] for m in data), 2) == round(
            sum(o["total_value"] for o in expected), 2
        )

    def test_month_filter_returns_single_month(self, client):
        """Test that a month filter returns only that month."""
        data = client.get("/api/reports/monthly-trends?month=2025-01").json()

        assert [m["month"] for m in data] == ["2025-01"]

    def test_unmatched_filter_returns_empty_list(self, client):
        """Test that filters matching nothing return an empty list."""
        response = client.get("/api/reports/monthly-trends?warehouse=Nowhere")
        assert response.status_code == 200
        assert response.json() == []
