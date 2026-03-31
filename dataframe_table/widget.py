from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Union, Iterable

import pandas as pd
import numpy as np

from PyQt6.QtCore import QItemSelectionModel, Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QVBoxLayout, QWidget

from .column import ColumnDef
from .filter_bar import FilterBar
from .model import DataFrameTableModel


@dataclass
class TableStyle:
    alternating_rows: bool = True
    grid_visible: bool = True
    row_height: int = 30
    show_row_numbers: bool = False
    stylesheet: Optional[str] = ""


class SelectionMode(Enum):
    Single = "single"
    Multi = "multi"
    Extended = "extended"


_SELECTION_MODE_MAP = {
    SelectionMode.Single: QAbstractItemView.SelectionMode.SingleSelection,
    SelectionMode.Multi: QAbstractItemView.SelectionMode.MultiSelection,
    SelectionMode.Extended: QAbstractItemView.SelectionMode.ExtendedSelection,
}


class DataFrameTable(QWidget):
    selection_changed = pyqtSignal(set)
    data_set = pyqtSignal()
    data_updated = pyqtSignal(set)

    def __init__(
        self,
        columns: List[ColumnDef],
        selection_mode: Union[str, SelectionMode] = SelectionMode.Extended,
        table_style: Optional[TableStyle] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._columns = columns
        self._table_style = table_style or TableStyle()

        # ---- model ----
        self._model = DataFrameTableModel(columns, parent=self)

        # ---- view ----
        self._view = QTableView(self)
        self._view.setModel(self._model)
        self._apply_style()
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(_SELECTION_MODE_MAP[selection_mode])
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # ---- delegates ----
        for i, col in enumerate(columns):
            if col.delegate is not None:
                self._view.setItemDelegateForColumn(i, col.delegate)

        # ---- hidden columns ----
        for i, col in enumerate(columns):
            if col.hidden:
                self._view.setColumnHidden(i, True)

        # ---- filter bar ----
        self._filter_bar = FilterBar(columns, self)
        self._filter_bar.bind_table_view(self._view)
        self._filter_bar.hide()

        for col in columns:
            if col.filter_widget is not None:
                col.filter_widget.filter_changed.connect(self._on_filter_changed)

        # ---- layout ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._filter_bar)
        layout.addWidget(self._view)

    # ==================================================================
    # Public API
    # ==================================================================

    def set_data(self, data: pd.DataFrame | list[dict] | dict) -> None:
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        self._model.set_dataframe(data)
        self.data_set.emit(set(range(len(data))))

    def get_data(self) -> pd.DataFrame:
        return self._model.get_dataframe()

    def clear_data(self) -> None:
        """Reset the table to an empty state."""
        self.set_data(pd.DataFrame())

    def update_cell(self, source_row: int, col_key: str, value) -> None:
        self._model.update_cell(source_row, col_key, value)
        self.data_updated.emit({source_row})

    def update_cells_bulk(self, updates: list) -> None:
        self._model.update_cells_bulk(updates)
        self.data_updated.emit({row for row, _, _ in updates})

    def row_count(self) -> int:
        """Number of visible rows (after filtering)."""
        return self._model.rowCount()

    def source_index(self, view_row: int) -> int:
        """Map a visible row position to the source DataFrame iloc index."""
        return self._model.source_index(view_row)

    def sort_by(self, key: str, ascending: bool = True) -> None:
        """Sort by column key. Pass None to clear sorting."""
        col_idx = self._col_index(key)
        if col_idx is None:
            return
        self._model.set_sort(col_idx, ascending)
        self._model.rebuild_view()
        header = self._view.horizontalHeader()
        header.setSortIndicator(col_idx, Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder)
        header.setSortIndicatorShown(True)

    def clear_sort(self) -> None:
        """Remove sorting, restore original DataFrame order."""
        self._model.set_sort(None, True)
        self._model.rebuild_view()
        self._view.horizontalHeader().setSortIndicatorShown(False)

    # ---- selection ----------------------------------------------------

    def set_selected_rows(self, source_indices: Set[int], silent: bool = False) -> None:
        sel = self._view.selectionModel()
        if silent:
            sel.blockSignals(True)
        try:
            sel.clearSelection()
            if not source_indices:
                return
            top_view_row = None
            for src in source_indices:
                view_row = self._model.view_row_for_source(src)
                if view_row is not None:
                    sel.select(self._model.index(view_row, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                    if top_view_row is None or view_row < top_view_row:
                        top_view_row = view_row
            if top_view_row is not None:
                sel.setCurrentIndex(self._model.index(top_view_row, 0), QItemSelectionModel.SelectionFlag.Current)
            self._view.setFocus()
        finally:
            if silent:
                sel.blockSignals(False)

    def get_selected_row_indexes(self) -> Set[int]:
        rows = set()
        for idx in self._view.selectionModel().selectedRows():
            rows.add(self._model.source_index(idx.row()))
        return rows

    def get_row(self, source_index: int) -> dict:
        row = self._model.get_dataframe().iloc[source_index]
        return {k: self._to_native(v) for k, v in row.items()}

    def get_rows(self, source_indices: Iterable) -> list[dict]:
        indices = sorted(source_indices)
        sub = self._model.get_dataframe().iloc[indices]
        return [
            {k: self._to_native(v) for k, v in record.items()}
            for record in sub.to_dict(orient="records")
        ]

    @staticmethod
    def _to_native(value):
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, float) and pd.isna(value):
            return None
        return value

    def select_first_visible_row(self) -> Optional[int]:
        if self._model.rowCount() == 0:
            return None
        src = self._model.source_index(0)
        self.set_selected_rows({src})
        return src

    # ---- columns ------------------------------------------------------

    def set_column_visible(self, key: str, visible: bool) -> None:
        col_idx = self._col_index(key)
        if col_idx is not None:
            self._view.setColumnHidden(col_idx, not visible)
            self._do_stretch()

    def is_column_visible(self, key: str) -> bool:
        col_idx = self._col_index(key)
        return col_idx is not None and not self._view.isColumnHidden(col_idx)

    # ---- filter bar ---------------------------------------------------

    def set_filter_bar_visible(self, visible: bool) -> None:
        self._filter_bar.setVisible(visible)

    def is_filter_bar_visible(self) -> bool:
        return self._filter_bar.isVisible()

    def reset_filters(self) -> None:
        for col in self._columns:
            if col.filter_widget is not None:
                col.filter_widget.blockSignals(True)
                col.filter_widget.reset()
                col.filter_widget.blockSignals(False)
        self._model.rebuild_view()

    def get_filter(self, key: str):
        for col in self._columns:
            if col.key == key:
                return col.filter_widget
        return None

    # ---- accessors ----------------------------------------------------

    @property
    def table_view(self) -> QTableView:
        return self._view

    # ==================================================================
    # Internal
    # ==================================================================

    def _col_index(self, key: str) -> Optional[int]:
        for i, c in enumerate(self._columns):
            if c.key == key:
                return i
        return None

    def _apply_style(self) -> None:
        self._view.setAlternatingRowColors(self._table_style.alternating_rows)
        self._view.setShowGrid(self._table_style.grid_visible)
        self._view.verticalHeader().setDefaultSectionSize(self._table_style.row_height)
        self._view.verticalHeader().setVisible(self._table_style.show_row_numbers)
        self._view.setStyleSheet(self._table_style.stylesheet)

    def _do_stretch(self) -> None:
        header = self._view.horizontalHeader()
        available = self._view.viewport().width()
        if available <= 0:
            return
        visible = [(i, c) for i, c in enumerate(self._columns) if not self._view.isColumnHidden(i)]
        total_stretch = sum(c.stretch for _, c in visible)
        if total_stretch <= 0:
            return
        header.blockSignals(True)
        try:
            allocated = 0
            for idx, (i, col) in enumerate(visible):
                if idx == len(visible) - 1:
                    w = available - allocated
                else:
                    w = int(available * col.stretch / total_stretch)
                allocated += w
                header.resizeSection(i, w)
        finally:
            header.blockSignals(False)
        header.viewport().update()
        self._view.viewport().update()
        self._filter_bar.sync_widths()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._do_stretch()

    def showEvent(self, event):
        super().showEvent(event)
        self._do_stretch()

    def _on_header_clicked(self, logical_index: int) -> None:
        col = self._columns[logical_index]
        if not col.sortable:
            return
        sort_col_idx, sort_ascending = self._model.get_sort()
        if sort_col_idx == logical_index:
            asc = not sort_ascending
        else:
            asc = True
        self.sort_by(col.key, asc)

    def _on_filter_changed(self) -> None:
        self._model.rebuild_view()

    def _on_selection_changed(self, selected, deselected) -> None:
        self.selection_changed.emit(self.get_selected_row_indexes())