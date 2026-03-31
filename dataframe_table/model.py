from __future__ import annotations

from typing import Any, List, Optional

import numpy as np
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from .column import ColumnDef


class DataFrameTableModel(QAbstractTableModel):

    def __init__(self, columns: List[ColumnDef], parent=None):
        super().__init__(parent)
        self._columns = columns
        self._df = pd.DataFrame()
        self._view_indices: np.ndarray = np.array([], dtype=np.intp)

        # Sort state
        self._sort_col_idx: Optional[int] = None
        self._sort_ascending: bool = True

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def source_index(self, view_row: int) -> int:
        """Map a visible (view) row to the source DataFrame iloc index."""
        return int(self._view_indices[view_row])

    def view_row_for_source(self, source_iloc: int) -> Optional[int]:
        """Reverse map: source iloc -> view row, or *None* if filtered out."""
        hits = np.where(self._view_indices == source_iloc)[0]
        return int(hits[0]) if len(hits) else None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def set_dataframe(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True).copy()
        self._rebuild_view()
        self.endResetModel()

    def get_dataframe(self) -> pd.DataFrame:
        return self._df

    def update_cell(self, source_row: int, col_key: str, value: Any) -> None:
        if col_key not in self._df.columns:
            return
        self._df.iat[source_row, self._df.columns.get_loc(col_key)] = value
        view_row = self.view_row_for_source(source_row)
        if view_row is not None:
            col_idx = next((i for i, c in enumerate(self._columns) if c.key == col_key), None)
            if col_idx is not None:
                idx = self.index(view_row, col_idx)
                self.dataChanged.emit(idx, idx, [])

    def update_cells_bulk(self, updates: List[tuple]) -> None:
        for source_row, col_key, value in updates:
            if col_key in self._df.columns:
                self._df.iat[source_row, self._df.columns.get_loc(col_key)] = value
        self.layoutChanged.emit()

    # ------------------------------------------------------------------
    # Sort / filter
    # ------------------------------------------------------------------

    def rebuild_view(self) -> None:
        self.beginResetModel()
        self._rebuild_view()
        self.endResetModel()

    def set_sort(self, col_idx: Optional[int], ascending: bool = True) -> None:
        self._sort_col_idx = col_idx
        self._sort_ascending = ascending

    def get_sort(self) -> tuple[Optional[int], bool]:
        """Return (col_idx, ascending). col_idx is None if unsorted."""
        return self._sort_col_idx, self._sort_ascending

    def _rebuild_view(self) -> None:
        n = len(self._df)
        if n == 0:
            self._view_indices = np.array([], dtype=np.intp)
            return

        # ---------- filter ----------
        mask = np.ones(n, dtype=bool)
        for col in self._columns:
            fw = col.filter_widget
            if fw is not None and fw.is_active() and col.key in self._df.columns:
                col_mask = fw.apply_filter(self._df[col.key])
                if isinstance(col_mask, pd.Series):
                    col_mask = col_mask.values
                mask &= col_mask.astype(bool)

        indices = np.where(mask)[0]

        # ---------- sort ----------
        if self._sort_col_idx is not None:
            col_def = self._columns[self._sort_col_idx]
            if col_def.key in self._df.columns:
                values = self._df[col_def.key].values[indices]
                order = pd.Series(values).argsort().values
                if not self._sort_ascending:
                    order = order[::-1]
                indices = indices[order]

        self._view_indices = indices

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._view_indices)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        col_def = self._columns[index.column()]
        source_row = int(self._view_indices[index.row()])

        if col_def.key not in self._df.columns:
            if role == Qt.ItemDataRole.UserRole:
                return source_row
            return None

        raw = self._df.iat[source_row, self._df.columns.get_loc(col_def.key)]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_def.delegate is not None:
                return None
            if col_def.formatter:
                return col_def.formatter(raw)
            if pd.isna(raw):
                return ""
            return str(raw)
        if role == Qt.ItemDataRole.EditRole:
            return raw
        if role == Qt.ItemDataRole.UserRole:
            return raw
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(col_def.alignment)
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        col_def = self._columns[index.column()]
        if col_def.key not in self._df.columns:
            return False
        source_row = int(self._view_indices[index.row()])
        self._df.iat[source_row, self._df.columns.get_loc(col_def.key)] = value
        self.dataChanged.emit(index, index, [])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if not index.isValid():
            return base
        col_def = self._columns[index.column()]
        if col_def.editable or col_def.delegate is not None:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._columns):
                return self._columns[section].header
            if orientation == Qt.Orientation.Vertical:
                if 0 <= section < len(self._view_indices):
                    return str(self._view_indices[section])
        return None
