"""
Tests for restocking API endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_restock_orders():
    """Clear submitted restocking orders before and after each test."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


class TestRestockRecommendations:
    """Test suite for budget-based restock recommendations."""

    def test_zero_budget_returns_no_items(self, client):
        """Test that a zero budget recommends nothing."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["remaining_budget"] == 0
        assert data["max_budget"] > 0

    def test_full_budget_includes_all_non_decreasing_items(self, client):
        """Test that the max budget covers every item without falling demand."""
        max_budget = client.get("/api/restocking/recommendations?budget=0").json()["max_budget"]

        data = client.get(f"/api/restocking/recommendations?budget={max_budget}").json()
        expected = [f for f in main.demand_forecasts if f["trend"] != "decreasing"]

        assert len(data["items"]) == len(expected)
        assert all(item["trend"] != "decreasing" for item in data["items"])
        assert data["total_cost"] == pytest.approx(max_budget)

    def test_items_cover_forecasted_demand(self, client):
        """Test that each item is restocked to its forecasted demand."""
        data = client.get("/api/restocking/recommendations?budget=1000000").json()
        forecasts = {f["item_sku"]: f for f in main.demand_forecasts}

        for item in data["items"]:
            forecast = forecasts[item["sku"]]
            assert item["quantity"] == forecast["forecasted_demand"]
            assert item["line_total"] == pytest.approx(item["quantity"] * item["unit_cost"])

    @pytest.mark.parametrize("budget", [500, 5000, 15000, 30000, 60000])
    def test_never_exceeds_budget(self, client, budget):
        """Test that recommendations always fit within the budget."""
        data = client.get(f"/api/restocking/recommendations?budget={budget}").json()

        assert data["total_cost"] <= budget
        assert data["total_cost"] == pytest.approx(sum(i["line_total"] for i in data["items"]))
        assert data["remaining_budget"] == pytest.approx(budget - data["total_cost"])

    def test_ranked_by_trend_then_demand_gap(self, client):
        """Test that increasing items come first, then the largest demand gap."""
        data = client.get("/api/restocking/recommendations?budget=1000000").json()
        trend_rank = {"increasing": 0, "stable": 1}
        keys = [(trend_rank[i["trend"]], -i["demand_gap"]) for i in data["items"]]

        assert keys == sorted(keys)

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget returns 422."""
        response = client.get("/api/restocking/recommendations?budget=-1")
        assert response.status_code == 422

    def test_missing_budget_rejected(self, client):
        """Test that the budget parameter is required."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 422


class TestRestockOrders:
    """Test suite for submitting and listing restocking orders."""

    def test_no_orders_initially(self, client):
        """Test that the order list starts empty."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_order(self, client):
        """Test that an order is priced on the server and uses the slowest lead time."""
        forecasts = {f["item_sku"]: f for f in main.demand_forecasts}
        payload = {"items": [{"sku": "WDG-001", "quantity": 10}, {"sku": "FLT-405", "quantity": 4}]}

        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        expected_total = 10 * forecasts["WDG-001"]["unit_cost"] + 4 * forecasts["FLT-405"]["unit_cost"]
        assert order["total_cost"] == pytest.approx(expected_total)
        assert order["lead_time_days"] == max(
            forecasts["WDG-001"]["lead_time_days"], forecasts["FLT-405"]["lead_time_days"]
        )
        assert order["status"] == "Submitted"
        assert order["order_number"] == "RST-0001"
        assert order["expected_delivery"] > order["order_date"]

    def test_created_orders_listed_newest_first(self, client):
        """Test that submitted orders are returned newest first."""
        client.post("/api/restocking/orders", json={"items": [{"sku": "WDG-001", "quantity": 1}]})
        client.post("/api/restocking/orders", json={"items": [{"sku": "GSK-203", "quantity": 1}]})

        orders = client.get("/api/restocking/orders").json()
        assert [o["order_number"] for o in orders] == ["RST-0002", "RST-0001"]

    def test_unknown_sku_rejected(self, client):
        """Test that an unknown SKU returns 400 and creates nothing."""
        response = client.post("/api/restocking/orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}]})
        assert response.status_code == 400
        assert "NOPE-999" in response.json()["detail"]
        assert client.get("/api/restocking/orders").json() == []

    def test_empty_order_rejected(self, client):
        """Test that an order with no items returns 400."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

    def test_non_positive_quantity_rejected(self, client):
        """Test that a zero quantity returns 400."""
        response = client.post("/api/restocking/orders", json={"items": [{"sku": "WDG-001", "quantity": 0}]})
        assert response.status_code == 400
