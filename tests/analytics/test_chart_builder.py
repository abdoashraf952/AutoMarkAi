"""Unit tests for the analytics chart builder and id scoping.

These cover regressions found by running the pipeline end to end:

  * the recommender does not put the measure in a predictable axis — it
    commonly returns the measure in `x_axis` for horizontal bars, which made
    the builder group by the measure and sum a string column;
  * "card"/"table" recommendations are not plottable series and used to
    consume the chart budget, leaving nothing to draw;
  * KPI/insight ids repeat across analyses ("kpi_01", …), so using them as a
    table primary key collided on a user's second analysis.

No database or LLM is involved.
"""

import pandas as pd
import pytest

from src.analytics.api import _build_charts
from src.analytics.database.repository import _scoped_id


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-03"],
            "region": ["North", "South", "North", "East"],
            "product": ["Villa", "Apartment", "Villa", "Townhouse"],
            "units_sold": [3, 5, 2, 8],
            "revenue_egp": [300.0, 500.0, 200.0, 800.0],
        }
    )


@pytest.fixture
def patched(monkeypatch, df):
    monkeypatch.setattr(
        "src.analytics.agents.data_loader.get_cached_dataframe", lambda _k: df
    )


# ── Axis resolution ──────────────────────────────────────────────────────────

def test_measure_in_x_axis_is_resolved(patched):
    """The recommender puts the measure in x_axis for horizontal bars."""
    charts = _build_charts(
        "k",
        [{"title": "Top Regions", "chart_type": "bar",
          "x_axis": "revenue_egp", "y_axis": "region"}],
    )
    assert len(charts) == 1
    c = charts[0]
    assert c["x"] == "region", "dimension must be the categorical column"
    assert c["y"] == "revenue_egp", "measure must be the numeric column"
    assert {p["label"] for p in c["points"]} == {"North", "South", "East"}
    north = next(p for p in c["points"] if p["label"] == "North")
    assert north["value"] == 500.0, "values must be summed per dimension"


def test_conventional_axis_order_also_works(patched):
    charts = _build_charts(
        "k",
        [{"title": "By Product", "chart_type": "bar",
          "x_axis": "product", "y_axis": "units_sold"}],
    )
    assert charts[0]["x"] == "product"
    assert charts[0]["y"] == "units_sold"


def test_points_sorted_descending_for_bar(patched):
    charts = _build_charts(
        "k", [{"chart_type": "bar", "x_axis": "region", "y_axis": "revenue_egp"}]
    )
    values = [p["value"] for p in charts[0]["points"]]
    assert values == sorted(values, reverse=True)


def test_line_sorted_by_dimension(patched):
    charts = _build_charts(
        "k", [{"chart_type": "line", "x_axis": "date", "y_axis": "revenue_egp"}]
    )
    labels = [p["label"] for p in charts[0]["points"]]
    assert labels == sorted(labels), "a time series must run in time order"


# ── Non-plottable and unknown types ──────────────────────────────────────────

@pytest.mark.parametrize("kind", ["card", "kpi", "table", "matrix", "gauge"])
def test_non_plottable_types_skipped(patched, kind):
    assert _build_charts("k", [{"chart_type": kind, "x_axis": None, "y_axis": None}]) == []


def test_cards_do_not_consume_the_chart_budget(patched):
    """Leading cards must not crowd out the real charts behind them."""
    recs = [{"chart_type": "card", "x_axis": None, "y_axis": None} for _ in range(8)]
    recs.append({"chart_type": "bar", "x_axis": "revenue_egp", "y_axis": "region"})
    charts = _build_charts("k", recs)
    assert len(charts) == 1 and charts[0]["type"] == "bar"


def test_unknown_columns_skipped(patched):
    assert _build_charts(
        "k", [{"chart_type": "bar", "x_axis": "nope", "y_axis": "also_nope"}]
    ) == []


def test_missing_dataframe_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "src.analytics.agents.data_loader.get_cached_dataframe", lambda _k: None
    )
    assert _build_charts("k", [{"chart_type": "bar", "x_axis": "region"}]) == []


# ── Type mapping and shape ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [("bar", "bar"), ("column", "bar"), ("clustered", "bar"), ("combo", "bar"),
     ("waterfall", "bar"), ("line", "line"), ("area", "line"),
     ("pie", "pie"), ("donut", "donut")],
)
def test_type_mapping(patched, raw, expected):
    charts = _build_charts(
        "k", [{"chart_type": raw, "x_axis": "region", "y_axis": "revenue_egp"}]
    )
    assert charts and charts[0]["type"] == expected


def test_scatter_needs_two_numeric_columns(patched):
    charts = _build_charts(
        "k", [{"chart_type": "scatter", "x_axis": "units_sold", "y_axis": "revenue_egp"}]
    )
    assert charts[0]["type"] == "scatter"
    assert all("x" in p and "y" in p for p in charts[0]["points"])


def test_dimension_only_falls_back_to_counts(patched):
    charts = _build_charts("k", [{"chart_type": "bar", "x_axis": "region"}])
    assert charts[0]["y"] == "count"
    assert sum(p["value"] for p in charts[0]["points"]) == 4


def test_chart_budget_capped(patched):
    recs = [{"chart_type": "bar", "x_axis": "region", "y_axis": "revenue_egp"}] * 20
    assert len(_build_charts("k", recs)) == 6


def test_values_are_json_safe_floats(patched):
    charts = _build_charts(
        "k", [{"chart_type": "bar", "x_axis": "region", "y_axis": "units_sold"}]
    )
    assert all(type(p["value"]) is float for p in charts[0]["points"])
    assert all(type(p["label"]) is str for p in charts[0]["points"])


# ── Id scoping ───────────────────────────────────────────────────────────────

def test_scoped_id_unique_across_analyses():
    """The same model id under two analyses must not collide."""
    assert _scoped_id("analysis-a", "kpi_01") != _scoped_id("analysis-b", "kpi_01")


def test_scoped_id_stable():
    assert _scoped_id("a", "kpi_01") == _scoped_id("a", "kpi_01")


def test_scoped_id_distinguishes_models_within_one_analysis():
    assert _scoped_id("a", "kpi_01") != _scoped_id("a", "kpi_02")


@pytest.mark.parametrize(
    "analysis_id,model_id",
    [("3f81d8ef-7c4d-4d11-9f5a-c5ac37d8c8d2", "kpi_01"),
     ("3f81d8ef-7c4d-4d11-9f5a-c5ac37d8c8d2", "insight_10"),
     ("a", "b"),
     ("x" * 40, "y" * 40)],
)
def test_scoped_id_fits_column_width(analysis_id, model_id):
    """The id column is String(36) — a longer value would be truncated."""
    assert len(_scoped_id(analysis_id, model_id)) <= 36


def test_scoped_id_long_inputs_still_unique():
    """Long ids must not collide after being cut to the column width."""
    a = "3f81d8ef-7c4d-4d11-9f5a-c5ac37d8c8d2"
    assert _scoped_id(a, "kpi_" + "x" * 40) != _scoped_id(a, "kpi_" + "y" * 40)
