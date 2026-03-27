"""Tests for filters — text, numeric, dropdown, and filter bar."""

from __future__ import annotations

import inspect

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dataframe_table import ColumnDef, DataFrameTable, DropdownFilter, NumericFilter, TextFilter
from conftest import _basic_columns


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
        categories = sorted(sample_df["category"].unique())
        df_filt = DropdownFilter(options_fn=lambda: categories)
        cols = _basic_columns()
        cols[4] = ColumnDef(key="category", header="Cat", stretch=1, filter_widget=df_filt)
        t = DataFrameTable(columns=cols)
        qtbot.addWidget(t)
        t.set_data(sample_df)

        # Populate by opening the dropdown
        df_filt._combo.showPopup()
        df_filt._combo.hidePopup()
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


class TestRegressionFilters:
    def test_filters_do_not_accept_parent(self):
        """Filter constructors should not accept a `parent` parameter."""
        for cls in (TextFilter, NumericFilter, DropdownFilter):
            params = inspect.signature(cls.__init__).parameters
            assert "parent" not in params, f"{cls.__name__} still accepts `parent`"


class TestDropdownFilter:
    """DropdownFilter with options_fn."""

    def test_no_fn_starts_with_all_only(self):
        """Without options_fn, dropdown has just (All)."""
        filt = DropdownFilter()
        assert filt._combo.count() == 1
        assert filt._combo.currentText() == "(All)"
        assert not filt.is_active()

    def test_options_fn_called_on_popup(self, qtbot):
        """options_fn is called every time the dropdown opens."""
        call_count = 0
        items = ["A", "B"]

        def get_options():
            nonlocal call_count
            call_count += 1
            return items

        filt = DropdownFilter(options_fn=get_options)

        filt._combo.showPopup()
        filt._combo.hidePopup()
        assert call_count == 1
        assert filt._combo.count() == 3  # (All) + A, B

        items.append("C")
        filt._combo.showPopup()
        filt._combo.hidePopup()
        assert call_count == 2
        assert filt._combo.count() == 4  # (All) + A, B, C

    def test_preserves_selection_across_popup(self, qtbot):
        """If the previously selected value still exists, it stays selected."""
        filt = DropdownFilter(options_fn=lambda: ["A", "B", "C"])
        filt._combo.showPopup()
        filt._combo.hidePopup()
        filt._combo.setCurrentText("B")
        assert filt._combo.currentText() == "B"

        filt._combo.showPopup()
        filt._combo.hidePopup()
        assert filt._combo.currentText() == "B"

    def test_selection_falls_back_to_all(self, qtbot):
        """If the selected value disappears, falls back to (All)."""
        items = ["A", "B"]
        filt = DropdownFilter(options_fn=lambda: items)
        filt._combo.showPopup()
        filt._combo.hidePopup()
        filt._combo.setCurrentText("B")

        items.remove("B")
        filt._combo.showPopup()
        filt._combo.hidePopup()
        assert filt._combo.currentText() == "(All)"

    def test_filter_applies_correctly(self, qtbot, sample_df):
        filt = DropdownFilter(options_fn=lambda: ["A", "B", "C"])
        filt._combo.showPopup()
        filt._combo.hidePopup()
        filt._combo.setCurrentText("A")
        assert filt.is_active()

        mask = filt.apply_filter(sample_df["category"])
        assert mask.sum() == (sample_df["category"] == "A").sum()
        assert mask.sum() < len(sample_df)

    def test_reset_clears_selection(self, qtbot):
        filt = DropdownFilter(options_fn=lambda: ["A", "B"])
        filt._combo.showPopup()
        filt._combo.hidePopup()
        filt._combo.setCurrentText("A")
        assert filt.is_active()

        filt.reset()
        assert not filt.is_active()
        assert filt._combo.currentText() == "(All)"
