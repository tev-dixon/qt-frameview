from __future__ import annotations

from abc import abstractmethod

import numpy as np
import pandas as pd
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget


class AbstractFilter(QWidget):
    """Base class for column filter widgets."""

    filter_changed = pyqtSignal()
    return_pressed = pyqtSignal()

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

    def focus(self) -> None:
        """Put the filter in a ready-to-type state."""
        ...

    def update_data(self, series: pd.Series) -> None:
        """Called when the source data changes.  Override to refresh options."""
        ...