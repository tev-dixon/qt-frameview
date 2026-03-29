"""Tests for OptionsFilter — searchable dropdown with optional multi-select."""

from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dataframe_table import ColumnDef, DataFrameTable, OptionsFilter
from conftest import _basic_columns


class TestOptionsFilterSingleSelect:
    """Single-select mode (default)."""

    def test_not_active_initially(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"])
        qtbot.addWidget(filt)
        assert not filt.is_active()

    def test_apply_filter_inactive_returns_all_true(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B"])
        qtbot.addWidget(filt)
        series = pd.Series(["A", "B", "A", "B"])
        mask = filt.apply_filter(series)
        assert mask.all()

    def test_single_select_filters_correctly(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"])
        qtbot.addWidget(filt)
        filt._selected = "B"
        filt._update_display()
        assert filt.is_active()

        series = pd.Series(["A", "B", "C", "B", "A"])
        mask = filt.apply_filter(series)
        assert list(mask) == [False, True, False, True, False]

    def test_reset_clears_selection(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B"])
        qtbot.addWidget(filt)
        filt._selected = "A"
        filt._update_display()
        assert filt.is_active()

        filt.reset()
        assert not filt.is_active()
        assert filt._display.text() == ""

    def test_display_shows_selected_value(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["X", "Y"])
        qtbot.addWidget(filt)
        filt._selected = "X"
        filt._update_display()
        assert filt._display.text() == "X"

    def test_options_fn_called_on_popup(self, qtbot):
        call_count = 0
        items = ["A", "B"]

        def get_options():
            nonlocal call_count
            call_count += 1
            return items

        filt = OptionsFilter(options_fn=get_options)
        qtbot.addWidget(filt)
        filt.show()
        filt._on_display_clicked(None)
        assert call_count == 1

        items.append("C")
        filt._on_display_clicked(None)
        assert call_count == 2


class TestOptionsFilterMultiSelect:
    """Multi-select mode."""

    def test_not_active_initially(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B"], multi_select=True)
        qtbot.addWidget(filt)
        assert not filt.is_active()

    def test_multi_select_filters_with_isin(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"], multi_select=True)
        qtbot.addWidget(filt)
        filt._checked = {"A", "C"}
        assert filt.is_active()

        series = pd.Series(["A", "B", "C", "B", "A"])
        mask = filt.apply_filter(series)
        assert list(mask) == [True, False, True, False, True]

    def test_empty_checked_returns_all_true(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B"], multi_select=True)
        qtbot.addWidget(filt)
        filt._checked = set()
        series = pd.Series(["A", "B", "A"])
        mask = filt.apply_filter(series)
        assert mask.all()

    def test_reset_clears_checked(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B"], multi_select=True)
        qtbot.addWidget(filt)
        filt._checked = {"A", "B"}
        filt._update_display()
        assert filt.is_active()

        filt.reset()
        assert not filt.is_active()
        assert filt._display.text() == ""

    def test_display_shows_count(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"], multi_select=True)
        qtbot.addWidget(filt)
        filt._checked = {"A", "C"}
        filt._update_display()
        assert filt._display.text() == "2 selected"

    def test_toggle_all_checks_when_none_checked(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"], multi_select=True)
        qtbot.addWidget(filt)
        filt.show()
        filt._on_display_clicked(None)
        popup = filt._ensure_popup()

        # Initially none checked
        assert popup.get_checked() == set()

        popup._on_toggle_all()
        assert popup.get_checked() == {"A", "B", "C"}

    def test_toggle_all_unchecks_when_some_checked(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"], multi_select=True)
        filt._checked = {"A"}
        qtbot.addWidget(filt)
        filt.show()
        filt._on_display_clicked(None)
        popup = filt._popup

        popup._on_toggle_all()
        assert popup.get_checked() == set()


class TestOptionsFilterPopupSearch:
    """Search/filter functionality in the popup."""

    def test_search_hides_non_matching(self, qtbot):
        filt = OptionsFilter(options_fn=lambda: ["Apple", "Banana", "Avocado"], multi_select=True)
        qtbot.addWidget(filt)
        filt.show()
        filt._on_display_clicked(None)
        popup = filt._popup

        popup._search.setText("a")
        # Apple, Banana, Avocado all contain 'a'
        visible = [popup._list.item(i).text() for i in range(popup._list.count()) if not popup._list.item(i).isHidden()]
        assert "Apple" in visible
        assert "Banana" in visible
        assert "Avocado" in visible

        popup._search.setText("ban")
        visible = [popup._list.item(i).text() for i in range(popup._list.count()) if not popup._list.item(i).isHidden()]
        assert visible == ["Banana"]


class TestOptionsFilterIntegration:
    """OptionsFilter wired into DataFrameTable."""

    def test_single_select_filters_table(self, qtbot, sample_df):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"])
        cols = _basic_columns()
        cols[4] = ColumnDef(key="category", header="Cat", stretch=1, filter_widget=filt)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        filt._selected = "A"
        filt._update_display()
        filt.filter_changed.emit()
        QApplication.processEvents()

        m = t.table_model
        for r in range(m.rowCount()):
            assert m.data(m.index(r, 4), Qt.ItemDataRole.UserRole) == "A"

    def test_multi_select_filters_table(self, qtbot, sample_df):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"], multi_select=True)
        cols = _basic_columns()
        cols[4] = ColumnDef(key="category", header="Cat", stretch=1, filter_widget=filt)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        filt._checked = {"A", "C"}
        filt._update_display()
        filt.filter_changed.emit()
        QApplication.processEvents()

        m = t.table_model
        for r in range(m.rowCount()):
            val = m.data(m.index(r, 4), Qt.ItemDataRole.UserRole)
            assert val in ("A", "C")
        assert m.rowCount() < len(sample_df)

    def test_reset_filters_clears_options_filter(self, qtbot, sample_df):
        filt = OptionsFilter(options_fn=lambda: ["A", "B", "C"], multi_select=True)
        cols = _basic_columns()
        cols[4] = ColumnDef(key="category", header="Cat", stretch=1, filter_widget=filt)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        filt._checked = {"A"}
        filt.filter_changed.emit()
        QApplication.processEvents()
        assert t.table_model.rowCount() < len(sample_df)

        t.reset_filters()
        QApplication.processEvents()
        assert t.table_model.rowCount() == len(sample_df)
