"""Tests for dataframe_table package.

Run with:  QT_QPA_PLATFORM=offscreen pytest tests/ -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dataframe_table import (
    ButtonDelegate,
    CheckBoxDelegate,
    ColumnDef,
    DataFrameTable,
    DropdownFilter,
    NumericFilter,
    TableStyle,
    TextFilter,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _sample_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    return pd.DataFrame({
        "id": np.arange(n),
        "name": [f"item_{i}" for i in range(n)],
        "value": rng.randint(0, 1000, size=n),
        "active": rng.choice([True, False], size=n),
        "category": rng.choice(["A", "B", "C"], size=n),
    })


def _basic_columns() -> list[ColumnDef]:
    return [
        ColumnDef(key="id", header="ID", stretch=0.5, sortable=True),
        ColumnDef(key="name", header="Name", stretch=2, sortable=True),
        ColumnDef(key="value", header="Value", stretch=1, sortable=True),
        ColumnDef(key="active", header="Active", stretch=0.5),
        ColumnDef(key="category", header="Cat", stretch=1, sortable=True),
    ]


@pytest.fixture
def sample_df():
    return _sample_df()


@pytest.fixture
def table(qtbot, sample_df):
    t = DataFrameTable(columns=_basic_columns())
    qtbot.addWidget(t)
    t.set_data(sample_df)
    t.show()
    t.resize(800, 400)
    QApplication.processEvents()
    return t


# ------------------------------------------------------------------
# Model basics
# ------------------------------------------------------------------

class TestModelBasics:
    def test_row_count(self, table, sample_df):
        assert table.table_model.rowCount() == len(sample_df)

    def test_column_count(self, table):
        assert table.table_model.columnCount() == 5

    def test_data_display(self, table):
        idx = table.table_model.index(0, 0)
        assert idx.data(Qt.ItemDataRole.DisplayRole) is not None

    def test_header_data(self, table):
        m = table.table_model
        assert m.headerData(0, Qt.Orientation.Horizontal) == "ID"
        assert m.headerData(1, Qt.Orientation.Horizontal) == "Name"

    def test_source_index_roundtrip(self, table):
        m = table.table_model
        for view_row in range(min(10, m.rowCount())):
            src = m.source_index(view_row)
            assert m.view_row_for_source(src) == view_row


# ------------------------------------------------------------------
# Sorting
# ------------------------------------------------------------------

class TestSorting:
    def test_sort_ascending(self, table):
        m = table.table_model
        m.set_sort(2, ascending=True)
        m.rebuild_view()
        values = [m.data(m.index(r, 2), Qt.ItemDataRole.UserRole) for r in range(m.rowCount())]
        assert values == sorted(values)

    def test_sort_descending(self, table):
        m = table.table_model
        m.set_sort(2, ascending=False)
        m.rebuild_view()
        values = [m.data(m.index(r, 2), Qt.ItemDataRole.UserRole) for r in range(m.rowCount())]
        assert values == sorted(values, reverse=True)

    def test_sort_preserves_row_count(self, table, sample_df):
        m = table.table_model
        m.set_sort(0, ascending=True)
        m.rebuild_view()
        assert m.rowCount() == len(sample_df)


# ------------------------------------------------------------------
# Filtering
# ------------------------------------------------------------------

class TestFiltering:
    def test_text_filter(self, qtbot, sample_df):
        tf = TextFilter()
        cols = _basic_columns()
        cols[1] = ColumnDef(key="name", header="Name", stretch=2, sortable=True, filter_widget=tf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        tf._edit.setText("item_5")
        QApplication.processEvents()

        m = t.table_model
        names = [m.data(m.index(r, 1), Qt.ItemDataRole.DisplayRole) for r in range(m.rowCount())]
        assert all("item_5" in n for n in names)
        assert m.rowCount() < len(sample_df)

    def test_numeric_filter(self, qtbot, sample_df):
        nf = NumericFilter()
        cols = _basic_columns()
        cols[2] = ColumnDef(key="value", header="Value", stretch=1, sortable=True, filter_widget=nf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        nf._op.setCurrentText(">")
        nf._edit.setText("500")
        QApplication.processEvents()

        m = t.table_model
        for r in range(m.rowCount()):
            assert m.data(m.index(r, 2), Qt.ItemDataRole.UserRole) > 500

    def test_dropdown_filter(self, qtbot, sample_df):
        df_filt = DropdownFilter()
        cols = _basic_columns()
        cols[4] = ColumnDef(key="category", header="Cat", stretch=1, filter_widget=df_filt)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        assert df_filt._combo.count() == 4  # (All) + A, B, C

        df_filt._combo.setCurrentText("A")
        QApplication.processEvents()

        m = t.table_model
        for r in range(m.rowCount()):
            assert m.data(m.index(r, 4), Qt.ItemDataRole.UserRole) == "A"

    def test_filter_reset(self, qtbot, sample_df):
        tf = TextFilter()
        cols = _basic_columns()
        cols[1] = ColumnDef(key="name", header="Name", stretch=2, filter_widget=tf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        tf._edit.setText("item_0")
        QApplication.processEvents()
        assert t.table_model.rowCount() < len(sample_df)

        t.reset_filters()
        QApplication.processEvents()
        assert t.table_model.rowCount() == len(sample_df)


# ------------------------------------------------------------------
# Selection
# ------------------------------------------------------------------

class TestSelection:
    def test_set_and_get_selection(self, table):
        table.set_selected_rows({0, 5, 10})
        assert table.get_selected_rows() == {0, 5, 10}

    def test_selection_changed_signal(self, qtbot, table):
        received = []
        table.selection_changed.connect(lambda s: received.append(s))
        table.set_selected_rows({3})
        QApplication.processEvents()
        assert len(received) > 0
        assert 3 in received[-1]

    def test_empty_selection(self, table):
        table.set_selected_rows(set())
        assert table.get_selected_rows() == set()

    def test_selection_after_sort(self, table):
        table.set_selected_rows({0, 1, 2})
        table.table_model.set_sort(2, ascending=True)
        table.table_model.rebuild_view()
        table.set_selected_rows({0, 1, 2})
        assert table.get_selected_rows() == {0, 1, 2}


# ------------------------------------------------------------------
# Column visibility
# ------------------------------------------------------------------

class TestColumnVisibility:
    def test_hide_column(self, table):
        table.set_column_visible("name", False)
        assert not table.is_column_visible("name")
        assert table.table_view.isColumnHidden(1)

    def test_show_column(self, table):
        table.set_column_visible("name", False)
        table.set_column_visible("name", True)
        assert table.is_column_visible("name")

    def test_hide_preserves_data(self, table):
        table.set_column_visible("value", False)
        idx = table.table_model.index(0, 2)
        assert idx.data(Qt.ItemDataRole.UserRole) is not None


# ------------------------------------------------------------------
# Data update
# ------------------------------------------------------------------

class TestDataUpdate:
    def test_update_cell(self, table):
        table.update_cell(0, "name", "CHANGED")
        assert table.get_data().at[0, "name"] == "CHANGED"
        idx = table.table_model.index(0, 1)
        assert idx.data(Qt.ItemDataRole.DisplayRole) == "CHANGED"

    def test_update_nonexistent_column(self, table):
        table.update_cell(0, "nonexistent", "x")  # should not raise

    def test_set_new_data(self, qtbot, table):
        table.set_data(_sample_df(50))
        assert table.table_model.rowCount() == 50


# ------------------------------------------------------------------
# Stretch ratios
# ------------------------------------------------------------------

class TestStretchRatios:
    def test_stretch_proportional(self, table):
        QApplication.processEvents()
        header = table.table_view.horizontalHeader()
        w0 = header.sectionSize(0)  # stretch=0.5
        w1 = header.sectionSize(1)  # stretch=2
        assert w1 > w0

    def test_resize_redistributes(self, qtbot, table):
        table.resize(1200, 400)
        QApplication.processEvents()
        table._do_stretch()  # force stretch since timer is debounced
        header = table.table_view.horizontalHeader()
        total = sum(header.sectionSize(i) for i in range(5))
        viewport_w = table.table_view.viewport().width()
        assert abs(total - viewport_w) < 10


# ------------------------------------------------------------------
# Delegates
# ------------------------------------------------------------------

class TestCheckBoxDelegate:
    def test_toggle_via_model(self, qtbot, sample_df):
        delegate = CheckBoxDelegate()
        cols = _basic_columns()
        cols[3] = ColumnDef(key="active", header="Active", stretch=0.5, delegate=delegate)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        m = t.table_model
        idx = m.index(0, 3)
        old_val = bool(idx.data(Qt.ItemDataRole.UserRole))
        m.setData(idx, not old_val, Qt.ItemDataRole.EditRole)
        assert bool(idx.data(Qt.ItemDataRole.UserRole)) == (not old_val)


class TestButtonDelegate:
    def test_callback_registration(self, qtbot, sample_df):
        clicked_rows = []
        delegate = ButtonDelegate(text="Go", on_click=lambda r: clicked_rows.append(r))
        cols = _basic_columns()
        cols.append(ColumnDef(key="btn", header="Action", delegate=delegate, stretch=1))
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.table_view.itemDelegateForColumn(5) is delegate


# ------------------------------------------------------------------
# Filter bar
# ------------------------------------------------------------------

class TestFilterBar:
    def test_hidden_by_default(self, table):
        assert not table.is_filter_bar_visible()

    def test_show_filter_bar(self, table):
        table.set_filter_bar_visible(True)
        assert table.is_filter_bar_visible()

    def test_toggle_filter_bar(self, table):
        table.set_filter_bar_visible(True)
        table.set_filter_bar_visible(False)
        assert not table.is_filter_bar_visible()


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_dataframe(self, qtbot):
        t = DataFrameTable(columns=_basic_columns())
        qtbot.addWidget(t)
        t.set_data(pd.DataFrame())
        assert t.table_model.rowCount() == 0

    def test_large_dataframe(self, qtbot):
        t = DataFrameTable(columns=_basic_columns())
        qtbot.addWidget(t)
        t.set_data(_sample_df(50_000))
        assert t.table_model.rowCount() == 50_000

    def test_superset_dataframe(self, qtbot):
        df = _sample_df()
        df["extra_col"] = 999
        t = DataFrameTable(columns=_basic_columns())
        qtbot.addWidget(t)
        t.set_data(df)
        assert t.table_model.rowCount() == len(df)
        assert "extra_col" in t.get_data().columns

    def test_formatter(self, qtbot, sample_df):
        cols = [ColumnDef(key="value", header="Value", stretch=1, formatter=lambda v: f"${v:,.0f}")]
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        idx = t.table_model.index(0, 0)
        assert idx.data(Qt.ItemDataRole.DisplayRole).startswith("$")

    def test_combined_sort_and_filter(self, qtbot, sample_df):
        nf = NumericFilter()
        cols = _basic_columns()
        cols[2] = ColumnDef(key="value", header="Value", stretch=1, sortable=True, filter_widget=nf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        nf._op.setCurrentText(">")
        nf._edit.setText("500")
        QApplication.processEvents()

        m = t.table_model
        m.set_sort(2, ascending=True)
        m.rebuild_view()

        values = [m.data(m.index(r, 2), Qt.ItemDataRole.UserRole) for r in range(m.rowCount())]
        assert all(v > 500 for v in values)
        assert values == sorted(values)

    def test_style_options(self, qtbot, sample_df):
        style = TableStyle(
            alternating_rows=False, grid_visible=False, row_height=40,
            show_row_numbers=True, font_size=14, header_font_size=16,
            selection_color="#3399ff",
        )
        t = DataFrameTable(columns=_basic_columns(), style=style)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        t.show()
        QApplication.processEvents()
        assert t.table_view.verticalHeader().isVisible()
        assert not t.table_view.alternatingRowColors()


# ------------------------------------------------------------------
# Regression tests for fixes
# ------------------------------------------------------------------

class TestRegressionColumnShowHide:
    """Fix: show/hide column must redistribute within viewport, not expand it."""

    def test_show_hidden_column_stays_within_viewport(self, table):
        QApplication.processEvents()
        header = table.table_view.horizontalHeader()
        viewport_w = table.table_view.viewport().width()

        table.set_column_visible("name", False)
        QApplication.processEvents()
        table.set_column_visible("name", True)
        QApplication.processEvents()

        total = sum(header.sectionSize(i) for i in range(5) if not table.table_view.isColumnHidden(i))
        assert total <= viewport_w + 5, f"columns total {total} exceeds viewport {viewport_w}"

    def test_hide_show_cycle_preserves_ratios(self, table):
        """After hide→show, stretch ratios should still hold."""
        QApplication.processEvents()
        header = table.table_view.horizontalHeader()

        w_before_id = header.sectionSize(0)
        w_before_name = header.sectionSize(1)

        table.set_column_visible("value", False)
        QApplication.processEvents()
        table.set_column_visible("value", True)
        QApplication.processEvents()

        # Ratios: ID=0.5, Name=2 → Name should be ~4x ID
        w_id = header.sectionSize(0)
        w_name = header.sectionSize(1)
        ratio = w_name / max(w_id, 1)
        assert 3.0 <= ratio <= 5.0, f"stretch ratio Name/ID = {ratio}, expected ~4"


class TestRegressionResizePerformance:
    """Fix: resizing debounces stretch via a restartable timer."""

    def test_debounced_stretch_coalesces(self, table):
        """Multiple resize events should result in only one _do_stretch call."""
        call_count = 0
        original = table._do_stretch

        def counting_stretch():
            nonlocal call_count
            call_count += 1
            original()

        table._do_stretch = counting_stretch
        # Simulate rapid resizes — timer restarts each time
        table.resize(600, 400)
        table.resize(700, 400)
        table.resize(800, 400)
        # Wait for the debounce timer to fire
        table._resize_timer.setInterval(1)  # speed up for test
        import time; time.sleep(0.05)
        QApplication.processEvents()
        assert call_count <= 2, f"_do_stretch called {call_count} times, expected <=2"

    def test_header_signals_blocked_during_stretch(self, table):
        """Verify filter bar sync is called once per stretch, not per-section."""
        sync_count = 0
        original_sync = table._filter_bar.sync_widths

        def counting_sync():
            nonlocal sync_count
            sync_count += 1
            original_sync()

        table._filter_bar.sync_widths = counting_sync
        table._do_stretch()
        assert sync_count == 1, f"sync_widths called {sync_count} times, expected 1"


class TestRegressionScrollbar:
    """Fix: horizontal scrollbar must never appear since stretch fills viewport."""

    def test_no_horizontal_scrollbar(self, table):
        from PyQt6.QtCore import Qt
        policy = table.table_view.horizontalScrollBarPolicy()
        assert policy == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    def test_columns_fit_viewport_after_resize(self, table):
        table.resize(600, 400)
        QApplication.processEvents()
        table._do_stretch()  # force stretch since timer is debounced
        header = table.table_view.horizontalHeader()
        viewport_w = table.table_view.viewport().width()
        total = sum(header.sectionSize(i) for i in range(5) if not table.table_view.isColumnHidden(i))
        assert total <= viewport_w, f"columns total {total} > viewport {viewport_w}"


class TestRegressionSelection:
    """Fix: programmatic selection must appear with the active (focused) palette."""

    def test_selection_gives_focus(self, table):
        """After set_selected_rows, the view should have focus."""
        table.set_selected_rows({0, 1})
        QApplication.processEvents()
        assert table.table_view.hasFocus()

    def test_selection_sets_current_index(self, table):
        """A current index must be set for the active highlight to appear."""
        table.set_selected_rows({3, 5})
        QApplication.processEvents()
        current = table.table_view.selectionModel().currentIndex()
        assert current.isValid(), "currentIndex should be set after programmatic selection"

    def test_selection_uses_clearandselect(self, table):
        """After set_selected_rows, exactly the requested rows are selected."""
        table.set_selected_rows({0, 1, 2})
        QApplication.processEvents()
        table.set_selected_rows({5, 6})
        QApplication.processEvents()
        assert table.get_selected_rows() == {5, 6}, "old selection should be fully cleared"

    def test_empty_selection_after_nonempty(self, table):
        table.set_selected_rows({0, 1})
        QApplication.processEvents()
        table.set_selected_rows(set())
        QApplication.processEvents()
        assert table.get_selected_rows() == set()


# ------------------------------------------------------------------
# Bulk update
# ------------------------------------------------------------------

class TestBulkUpdate:
    def test_bulk_update_changes_data(self, table):
        table.update_cells_bulk([
            (0, "name", "BULK_0"),
            (1, "name", "BULK_1"),
            (2, "value", 9999),
        ])
        df = table.get_data()
        assert df.at[0, "name"] == "BULK_0"
        assert df.at[1, "name"] == "BULK_1"
        assert df.at[2, "value"] == 9999

    def test_bulk_update_emits_once(self, table):
        signals = []
        table.table_model.layoutChanged.connect(lambda: signals.append(1))
        table.update_cells_bulk([
            (i, "name", f"ROW_{i}") for i in range(50)
        ])
        assert len(signals) == 1, f"layoutChanged emitted {len(signals)} times, expected 1"

    def test_bulk_update_skips_bad_columns(self, table):
        # Should not raise
        table.update_cells_bulk([
            (0, "nonexistent", "x"),
            (0, "name", "VALID"),
        ])
        assert table.get_data().at[0, "name"] == "VALID"


class TestRegressionFilterBarSizing:
    """Fix: filter bar must not impose a minimum width on the parent."""

    def test_filter_bar_minimum_size_hint_is_zero(self, qtbot, sample_df):
        """FilterBar.minimumSizeHint().width() must be 0."""
        tf = TextFilter()
        nf = NumericFilter()
        cols = _basic_columns()
        cols[1] = ColumnDef(key="name", header="Name", stretch=2, filter_widget=tf)
        cols[2] = ColumnDef(key="value", header="Value", stretch=1, filter_widget=nf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        t.set_filter_bar_visible(True)
        assert t._filter_bar.minimumSizeHint().width() == 0

    def test_show_hide_with_filter_bar_active(self, qtbot, sample_df):
        """Show/hide columns with filters active must not leave whitespace."""
        tf = TextFilter()
        cols = _basic_columns()
        cols[1] = ColumnDef(key="name", header="Name", stretch=2, filter_widget=tf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        t.show()
        t.resize(800, 400)
        t.set_filter_bar_visible(True)
        QApplication.processEvents()

        viewport_w = t.table_view.viewport().width()

        t.set_column_visible("name", False)
        QApplication.processEvents()
        t.set_column_visible("name", True)
        QApplication.processEvents()

        header = t.table_view.horizontalHeader()
        total = sum(
            header.sectionSize(i) for i in range(5)
            if not t.table_view.isColumnHidden(i)
        )
        assert total <= viewport_w + 5, (
            f"columns total {total} exceeds viewport {viewport_w} with filter bar active"
        )

    def test_table_shrinks_with_filter_bar_active(self, qtbot, sample_df):
        """Table must shrink freely even when filter bar is visible."""
        tf = TextFilter()
        nf = NumericFilter()
        cols = _basic_columns()
        cols[1] = ColumnDef(key="name", header="Name", stretch=2, filter_widget=tf)
        cols[2] = ColumnDef(key="value", header="Value", stretch=1, filter_widget=nf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        t.show()
        t.resize(800, 400)
        t.set_filter_bar_visible(True)
        QApplication.processEvents()

        # Shrink significantly
        t.resize(400, 400)
        QApplication.processEvents()
        # Force deferred stretch
        t._do_stretch()

        header = t.table_view.horizontalHeader()
        viewport_w = t.table_view.viewport().width()
        total = sum(
            header.sectionSize(i) for i in range(5)
            if not t.table_view.isColumnHidden(i)
        )
        assert total <= viewport_w + 5, (
            f"columns total {total} exceeds viewport {viewport_w} after shrink"
        )

class TestRegressionFilters:
    
    def test_filters_do_not_accept_parent(self):
        """Filter constructors should not accept a `parent` parameter."""
        import inspect
        for cls in (TextFilter, NumericFilter, DropdownFilter):
            params = inspect.signature(cls.__init__).parameters
            assert "parent" not in params, f"{cls.__name__} still accepts `parent`"
