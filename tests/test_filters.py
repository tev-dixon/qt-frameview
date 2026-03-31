"""Tests for filters — text, numeric, dropdown, and filter bar."""

from __future__ import annotations

import inspect

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dataframe_table import ColumnDef, DataFrameTable, NumericFilter, TextFilter
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
        for cls in (TextFilter, NumericFilter):
            params = inspect.signature(cls.__init__).parameters
            assert "parent" not in params, f"{cls.__name__} still accepts `parent`"


