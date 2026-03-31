from __future__ import annotations

from .AbstractFilter import AbstractFilter

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import QComboBox, QHBoxLayout


class _LazyComboBox(QComboBox):
 
    def __init__(self, options: list, all_label: str):
        super().__init__()
        self._options = options
        self._all_label = all_label
 
    def showPopup(self):
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItem(self._all_label)
        for v in self._options:
            self.addItem(str(v))
        idx = self.findText(current)
        self.setCurrentIndex(idx if idx >= 0 else 0)
        self.blockSignals(False)
        super().showPopup()


class DropdownFilter(AbstractFilter):
 
    _ALL_LABEL = "(All)"
 
    def __init__(
        self,
        options: list = None,
    ):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
 
        if options is not None:
            self._combo = _LazyComboBox(options, self._ALL_LABEL)
        else:
            self._combo = QComboBox()
 
        self._combo.addItem(self._ALL_LABEL)
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
