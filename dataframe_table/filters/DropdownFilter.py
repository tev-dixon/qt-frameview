from __future__ import annotations

from .AbstractFilter import AbstractFilter

from typing import Optional, Sequence, Callable

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import QComboBox, QHBoxLayout


class _LazyComboBox(QComboBox):
    """QComboBox that calls a function to populate options on every popup open."""
 
    def __init__(self, options_fn: Callable[[], Sequence[str]], all_label: str):
        super().__init__()
        self._options_fn = options_fn
        self._all_label = all_label
 
    def showPopup(self):
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItem(self._all_label)
        for v in self._options_fn():
            self.addItem(str(v))
        idx = self.findText(current)
        self.setCurrentIndex(idx if idx >= 0 else 0)
        self.blockSignals(False)
        super().showPopup()


class DropdownFilter(AbstractFilter):
    """Dropdown that filters to a single selected value (or *All*).
 
    Args:
        options_fn: A callable that returns the current list of options.
            Invoked every time the dropdown is opened (via ``showPopup``),
            so the list is always fresh.  If ``None``, the dropdown starts
            with only "(All)".
 
    .. warning::
 
       ``options_fn`` is called on the **main/UI thread** every time the
       user opens the dropdown.  If the callable is slow (e.g. an
       unindexed database query), it will block the interface until it
       returns.  Keep the function fast, or cache results externally and
       invalidate on your own schedule.
    """
 
    _ALL_LABEL = "(All)"
 
    def __init__(
        self,
        options_fn: Optional[Callable[[], Sequence[str]]] = None,
    ):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
 
        if options_fn is not None:
            self._combo = _LazyComboBox(options_fn, self._ALL_LABEL)
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
