"""Filter widgets for the DataFrameTable filter bar.

Every filter is a QWidget that emits ``filter_changed`` when the user changes
its value, and implements ``apply_filter(series) -> bool mask``.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget


class AbstractFilter(QWidget):
    """Base class for column filter widgets."""

    filter_changed = pyqtSignal()

    @abstractmethod
    def apply_filter(self, series: pd.Series) -> np.ndarray:
        """Return a boolean numpy array (same length as *series*)."""
        ...

    @abstractmethod
    def is_active(self) -> bool:
        """True when the filter is actually constraining results."""
        ...

    def reset(self) -> None:
        """Clear the filter to its default (no filtering) state."""
        ...

    def update_data(self, series: pd.Series) -> None:
        """Called when the source data changes.  Override to refresh options."""
        ...


class TextFilter(AbstractFilter):
    """Free-text filter with mode selector (Contains / Equals / Regex)."""

    MODES = ["Contains", "Equals", "Regex"]

    def __init__(self, placeholder: str = "Filter…"):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)

        self._mode = QComboBox()
        self._mode.addItems(self.MODES)
        self._mode.setFixedWidth(80)
        self._mode.currentIndexChanged.connect(self._emit)
        layout.addWidget(self._mode)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.textChanged.connect(self._emit)
        layout.addWidget(self._edit)

    def _emit(self):
        self.filter_changed.emit()

    def is_active(self) -> bool:
        return bool(self._edit.text())

    def reset(self) -> None:
        self._edit.clear()

    def apply_filter(self, series: pd.Series) -> np.ndarray:
        text = self._edit.text()
        if not text:
            return np.ones(len(series), dtype=bool)
        s = series.astype(str)
        mode = self._mode.currentText()
        if mode == "Contains":
            return s.str.contains(text, case=False, na=False).values
        if mode == "Equals":
            return (s.str.lower() == text.lower()).values
        try:
            return s.str.contains(text, case=False, na=False, regex=True).values
        except Exception:
            return np.ones(len(series), dtype=bool)


class NumericFilter(AbstractFilter):
    """Numeric comparison filter (=, <, >, <=, >=, !=)."""

    OPS = ["=", "<", ">", "<=", ">=", "!="]

    def __init__(self, placeholder: str = "Value"):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)

        self._op = QComboBox()
        self._op.addItems(self.OPS)
        self._op.setFixedWidth(52)
        self._op.currentIndexChanged.connect(self._emit)
        layout.addWidget(self._op)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.textChanged.connect(self._emit)
        layout.addWidget(self._edit)

    def _emit(self):
        self.filter_changed.emit()

    def is_active(self) -> bool:
        try:
            float(self._edit.text())
            return True
        except (ValueError, TypeError):
            return False

    def reset(self) -> None:
        self._edit.clear()

    def apply_filter(self, series: pd.Series) -> np.ndarray:
        try:
            val = float(self._edit.text())
        except (ValueError, TypeError):
            return np.ones(len(series), dtype=bool)
        numeric = pd.to_numeric(series, errors="coerce")
        ops = {"=": numeric == val, "<": numeric < val, ">": numeric > val,
               "<=": numeric <= val, ">=": numeric >= val, "!=": numeric != val}
        result = ops.get(self._op.currentText(), pd.Series(np.ones(len(series), dtype=bool)))
        return result.fillna(False).values


class DropdownFilter(AbstractFilter):
    """Dropdown that filters to a single selected value (or *All*)."""

    _ALL_LABEL = "(All)"

    def __init__(self, options: Optional[Sequence[str]] = None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)

        self._combo = QComboBox()
        self._combo.addItem(self._ALL_LABEL)
        if options:
            for o in options:
                self._combo.addItem(str(o))
        self._combo.currentIndexChanged.connect(lambda _: self.filter_changed.emit())
        layout.addWidget(self._combo)

    def is_active(self) -> bool:
        return self._combo.currentText() != self._ALL_LABEL

    def reset(self) -> None:
        self._combo.setCurrentIndex(0)

    def apply_filter(self, series: pd.Series) -> np.ndarray:
        selected = self._combo.currentText()
        if selected == self._ALL_LABEL:
            return np.ones(len(series), dtype=bool)
        return (series.astype(str) == selected).values

    def update_data(self, series: pd.Series) -> None:
        current = self._combo.currentText()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem(self._ALL_LABEL)
        for v in sorted(series.dropna().unique(), key=str):
            self._combo.addItem(str(v))
        idx = self._combo.findText(current)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo.blockSignals(False)
