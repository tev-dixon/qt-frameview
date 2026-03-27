"""DataFrameTable — the main public widget.

Usage::

    table = DataFrameTable(
        columns=[
            ColumnDef(key="name", header="Name", stretch=2, sortable=True,
                      filter_widget=TextFilter()),
            ColumnDef(key="age", header="Age", stretch=1, sortable=True,
                      filter_widget=NumericFilter()),
            ColumnDef(key="active", header="Active", stretch=0.5,
                      delegate=CheckBoxDelegate()),
            ColumnDef(key="actions", header="",
                      delegate=ButtonDelegate(text="Del", on_click=print)),
        ],
        selection_mode="extended",
    )
    table.set_data(my_dataframe)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set

import pandas as pd
from PyQt6.QtCore import QItemSelectionModel, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QVBoxLayout, QWidget

from .column import ColumnDef
from .filter_bar import FilterBar
from .model import DataFrameTableModel


@dataclass
class TableStyle:
    """Visual defaults — all optional, sane defaults provided."""

    alternating_rows: bool = True
    grid_visible: bool = True
    row_height: int = 30
    show_row_numbers: bool = False
    selection_color: Optional[str] = None
    font_size: Optional[int] = None
    header_font_size: Optional[int] = None


_SELECTION_MODES = {
    "single": QAbstractItemView.SelectionMode.SingleSelection,
    "multi": QAbstractItemView.SelectionMode.MultiSelection,
    "extended": QAbstractItemView.SelectionMode.ExtendedSelection,
}


class DataFrameTable(QWidget):
    """Feature-rich table backed by a pandas DataFrame.

    Signals:
        selection_changed(set[int]): Emitted with the set of currently
            selected source DataFrame iloc indices whenever the selection
            changes.
    """

    selection_changed = pyqtSignal(set)

    def __init__(
        self,
        columns: List[ColumnDef],
        selection_mode: str = "extended",
        style: Optional[TableStyle] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._columns = columns
        self._style = style or TableStyle()

        # ---- model ----
        self._model = DataFrameTableModel(columns, parent=self)

        # ---- view ----
        self._view = QTableView(self)
        self._view.setModel(self._model)
        self._apply_style()
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(
            _SELECTION_MODES.get(selection_mode, QAbstractItemView.SelectionMode.ExtendedSelection)
        )
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        # Re-stretch when vertical scrollbar appears/disappears (changes viewport width)
        self._view.verticalScrollBar().rangeChanged.connect(lambda: self._schedule_stretch())

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

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(16)  # ~1 frame at 60fps
        self._resize_timer.timeout.connect(self._deferred_stretch)

    # ==================================================================
    # Public API
    # ==================================================================

    def set_data(self, df: pd.DataFrame) -> None:
        """Load a new DataFrame (or replace existing data)."""
        self._model.set_dataframe(df)
        for col in self._columns:
            if col.filter_widget is not None and col.key in df.columns:
                col.filter_widget.update_data(df[col.key])
        self._do_stretch()
        self._schedule_stretch()

    def get_data(self) -> pd.DataFrame:
        return self._model.get_dataframe()

    def update_cell(self, source_row: int, col_key: str, value) -> None:
        """Update a single cell by source DataFrame iloc index and column key."""
        self._model.update_cell(source_row, col_key, value)

    def update_cells_bulk(self, updates: list) -> None:
        """Batch-update many cells with a single repaint.

        Args:
            updates: List of ``(source_row, col_key, value)`` tuples.
        """
        self._model.update_cells_bulk(updates)

    # ---- selection ----------------------------------------------------

    def set_selected_rows(self, source_indices: Set[int]) -> None:
        """Programmatically select rows by source DataFrame iloc indices.

        Gives focus to the table so that the active (dark blue) selection
        palette is used rather than the inactive (light grey) one.
        """
        sel = self._view.selectionModel()
        sel.clearSelection()
        if not source_indices:
            return
        first_set = False
        for src in source_indices:
            view_row = self._model.view_row_for_source(src)
            if view_row is not None:
                idx = self._model.index(view_row, 0)
                if not first_set:
                    # First row: ClearAndSelect + set as current index
                    sel.select(
                        idx,
                        QItemSelectionModel.SelectionFlag.ClearAndSelect
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
                    sel.setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.Current)
                    first_set = True
                else:
                    sel.select(
                        idx,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
        # Give focus so Qt uses the active palette (dark blue) not inactive (grey)
        self._view.setFocus()

    def get_selected_rows(self) -> Set[int]:
        rows = set()
        for idx in self._view.selectionModel().selectedRows():
            rows.add(self._model.source_index(idx.row()))
        return rows

    # ---- columns ------------------------------------------------------

    def set_column_visible(self, key: str, visible: bool) -> None:
        col_idx = self._col_index(key)
        if col_idx is not None:
            header = self._view.horizontalHeader()
            if visible and self._view.isColumnHidden(col_idx):
                # Zero the section before unhiding so its default width
                # never inflates the header beyond the viewport.
                header.resizeSection(col_idx, 0)
            self._view.setColumnHidden(col_idx, not visible)
            # Apply stretch immediately (geometry is stable here — no
            # resize event in flight) then schedule a deferred pass to
            # catch any layout settling.
            self._do_stretch()
            self._schedule_stretch()

    def is_column_visible(self, key: str) -> bool:
        col_idx = self._col_index(key)
        return col_idx is not None and not self._view.isColumnHidden(col_idx)

    # ---- filter bar ---------------------------------------------------

    def set_filter_bar_visible(self, visible: bool) -> None:
        self._filter_bar.setVisible(visible)
        if visible:
            self._schedule_stretch()

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
        """Return the filter widget for *key*, or ``None`` if the column
        has no filter or the key does not exist."""
        for col in self._columns:
            if col.key == key:
                return col.filter_widget
        return None

    # ---- accessors ----------------------------------------------------

    @property
    def table_view(self) -> QTableView:
        return self._view

    @property
    def table_model(self) -> DataFrameTableModel:
        return self._model

    # ==================================================================
    # Internal
    # ==================================================================

    def _col_index(self, key: str) -> Optional[int]:
        for i, c in enumerate(self._columns):
            if c.key == key:
                return i
        return None

    def _apply_style(self) -> None:
        s = self._style
        self._view.setAlternatingRowColors(s.alternating_rows)
        self._view.setShowGrid(s.grid_visible)
        self._view.verticalHeader().setDefaultSectionSize(s.row_height)
        if not s.show_row_numbers:
            self._view.verticalHeader().hide()
        else:
            self._view.verticalHeader().show()
        parts: list[str] = []
        if s.selection_color:
            parts.append(f"QTableView::item:selected {{ background: {s.selection_color}; }}")
        if s.font_size:
            parts.append(f"QTableView {{ font-size: {s.font_size}px; }}")
        if s.header_font_size:
            parts.append(f"QHeaderView::section {{ font-size: {s.header_font_size}px; }}")
        if parts:
            self._view.setStyleSheet("\n".join(parts))

    def _schedule_stretch(self) -> None:
        """Debounce: restart the timer so stretch fires once after
        the resize/show/hide event storm settles."""
        self._resize_timer.start()

    def _deferred_stretch(self) -> None:
        self._do_stretch()

    def _do_stretch(self) -> None:
        """Distribute column widths proportionally by stretch ratio."""
        header = self._view.horizontalHeader()
        available = self._view.viewport().width()
        if available <= 0:
            return
        visible = [(i, c) for i, c in enumerate(self._columns) if not self._view.isColumnHidden(i)]
        total_stretch = sum(c.stretch for _, c in visible)
        if total_stretch <= 0:
            return
        # Block signals to batch all resizes — prevents per-section
        # repaints and cascading layout recalculations.
        header.blockSignals(True)
        try:
            allocated = 0
            for idx, (i, col) in enumerate(visible):
                if idx == len(visible) - 1:
                    # Last column absorbs rounding remainder so total == available exactly
                    w = available - allocated
                else:
                    w = max(int(available * col.stretch / total_stretch), 30)
                allocated += w
                header.resizeSection(i, w)
        finally:
            header.blockSignals(False)
        # Signals were blocked during resize — force the view to repaint
        # both the header and the body so rows stay in sync with columns.
        header.viewport().update()
        self._view.viewport().update()
        self._filter_bar.sync_widths()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_stretch()

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_stretch()

    def _on_header_clicked(self, logical_index: int) -> None:
        col = self._columns[logical_index]
        if not col.sortable:
            return
        header = self._view.horizontalHeader()
        if self._model._sort_col_idx == logical_index:
            asc = not self._model._sort_ascending
        else:
            asc = True
        self._model.set_sort(logical_index, asc)
        self._model.rebuild_view()
        header.setSortIndicator(
            logical_index, Qt.SortOrder.AscendingOrder if asc else Qt.SortOrder.DescendingOrder
        )
        header.setSortIndicatorShown(True)

    def _on_filter_changed(self) -> None:
        self._model.rebuild_view()

    def _on_selection_changed(self, selected, deselected) -> None:
        self.selection_changed.emit(self.get_selected_rows())
