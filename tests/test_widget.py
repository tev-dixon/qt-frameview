"""Tests for DataFrameTable widget — filter bar, edge cases, resize, scrollbar."""

from __future__ import annotations

import time

import pandas as pd
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QApplication

from dataframe_table import ColumnDef, DataFrameTable, NumericFilter, TableStyle, TextFilter, SelectionMode
from conftest import _basic_columns, _sample_df


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


class TestGetFilter:
    def test_returns_filter_widget(self, qtbot, sample_df):
        tf = TextFilter()
        cols = _basic_columns()
        cols[1] = ColumnDef(key="name", header="Name", stretch=2, filter_widget=tf)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.get_filter("name") is tf

    def test_returns_none_for_no_filter(self, table):
        assert table.get_filter("id") is None

    def test_returns_none_for_unknown_key(self, table):
        assert table.get_filter("nonexistent") is None


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


class TestRegressionResizePerformance:
    """Fix: resizing debounces stretch via a restartable timer."""

    def test_debounced_stretch_coalesces(self, table):
        call_count = 0
        original = table._do_stretch

        def counting_stretch():
            nonlocal call_count
            call_count += 1
            original()

        table._do_stretch = counting_stretch
        table.resize(600, 400)
        table.resize(700, 400)
        table.resize(800, 400)
        table._resize_timer.setInterval(1)
        time.sleep(0.05)
        QApplication.processEvents()
        assert call_count <= 2, f"_do_stretch called {call_count} times, expected <=2"

    def test_header_signals_blocked_during_stretch(self, table):
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
        policy = table.table_view.horizontalScrollBarPolicy()
        assert policy == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    def test_columns_fit_viewport_after_resize(self, table):
        table.resize(600, 400)
        QApplication.processEvents()
        table._do_stretch()
        header = table.table_view.horizontalHeader()
        viewport_w = table.table_view.viewport().width()
        total = sum(header.sectionSize(i) for i in range(5) if not table.table_view.isColumnHidden(i))
        assert total <= viewport_w, f"columns total {total} > viewport {viewport_w}"


class TestRegressionFilterBarSizing:
    """Fix: filter bar must not impose a minimum width on the parent."""

    def test_filter_bar_minimum_size_hint_is_zero(self, qtbot, sample_df):
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

        t.resize(400, 400)
        QApplication.processEvents()
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


class TestSelectionMode:
    """SelectionMode enum and backward-compatible string support."""

    def test_enum_single(self, qtbot, sample_df):
        t = DataFrameTable(columns=_basic_columns(), selection_mode=SelectionMode.Single)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.table_view.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection

    def test_enum_multi(self, qtbot, sample_df):
        t = DataFrameTable(columns=_basic_columns(), selection_mode=SelectionMode.Multi)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.table_view.selectionMode() == QAbstractItemView.SelectionMode.MultiSelection

    def test_enum_extended(self, qtbot, sample_df):
        t = DataFrameTable(columns=_basic_columns(), selection_mode=SelectionMode.Extended)
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.table_view.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection

    def test_string_still_works(self, qtbot, sample_df):
        t = DataFrameTable(columns=_basic_columns(), selection_mode="single")
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.table_view.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection

    def test_string_case_insensitive(self, qtbot, sample_df):
        t = DataFrameTable(columns=_basic_columns(), selection_mode="Multi")
        qtbot.addWidget(t)
        t.set_data(sample_df)
        assert t.table_view.selectionMode() == QAbstractItemView.SelectionMode.MultiSelection

    def test_invalid_string_raises(self, qtbot):
        with pytest.raises(ValueError, match="Unknown selection mode"):
            DataFrameTable(columns=_basic_columns(), selection_mode="invalid")
