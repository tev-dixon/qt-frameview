from __future__ import annotations

from typing import Callable, List, Optional, Sequence

import numpy as np
import pandas as pd
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .AbstractFilter import AbstractFilter


class _OptionsPopup(QWidget):
    """Floating popup with optional (Select All) row, search box, and option list."""

    _SELECT_ALL_LABEL = "(Select All)"

    item_clicked = pyqtSignal()  # emitted on every meaningful change
    closed = pyqtSignal()

    def __init__(self, multi_select: bool, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup)
        self._multi_select = multi_select
        self._guard = False  # prevents signal loops during programmatic changes
        self._change_handled = False  # True when itemChanged already processed the click

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._apply_search)
        layout.addWidget(self._search)

        self._list = QListWidget()
        if multi_select:
            self._list.itemChanged.connect(self._on_item_changed)
            self._list.itemClicked.connect(self._on_item_clicked_multi)
        else:
            self._list.itemClicked.connect(self._on_item_clicked_single)
        layout.addWidget(self._list)

        self.setMinimumWidth(160)

    # -- public API --

    def populate(self, options: Sequence[str], checked: set[str] | None = None) -> None:
        self._guard = True
        self._search.clear()
        self._list.clear()
        if self._multi_select:
            select_all = QListWidgetItem(self._SELECT_ALL_LABEL)
            select_all.setFlags(select_all.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            select_all.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(select_all)
        else:
            self._list.addItem(QListWidgetItem("(All)"))
        for opt in options:
            item = QListWidgetItem(str(opt))
            if self._multi_select:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if checked and opt in checked else Qt.CheckState.Unchecked
                )
            self._list.addItem(item)
        if self._multi_select:
            self._sync_select_all_state()
        self._guard = False

    def get_checked(self) -> set[str]:
        result: set[str] = set()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.text() == self._SELECT_ALL_LABEL:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                result.add(item.text())
        return result

    def get_selected_single(self) -> str | None:
        current = self._list.currentItem()
        if current is None:
            return None
        text = current.text()
        return None if text == "(All)" else text

    def open_at(self, global_pos: QPoint, width: int) -> None:
        self.setFixedWidth(max(width, self.minimumWidth()))
        self.move(global_pos)
        self.show()
        self._search.setFocus()

    # -- internals --

    def _option_items(self) -> list[QListWidgetItem]:
        """Return all items except the (Select All) row."""
        return [
            self._list.item(i)
            for i in range(self._list.count())
            if self._list.item(i).text() != self._SELECT_ALL_LABEL
        ]

    def _sync_select_all_state(self) -> None:
        """Update the (Select All) checkbox to reflect current option states."""
        sa = self._list.item(0)
        if sa is None or sa.text() != self._SELECT_ALL_LABEL:
            return
        options = self._option_items()
        all_checked = all(it.checkState() == Qt.CheckState.Checked for it in options) if options else False
        sa.setCheckState(Qt.CheckState.Checked if all_checked else Qt.CheckState.Unchecked)

    def _apply_search(self, text: str) -> None:
        text_lower = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            label = item.text()
            if label == "(All)" or label == self._SELECT_ALL_LABEL:
                item.setHidden(bool(text))
                continue
            item.setHidden(text_lower not in label.lower())

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """Multi-select: fired by Qt when any check state changes (click or programmatic)."""
        if self._guard:
            return
        self._change_handled = True
        if item.text() == self._SELECT_ALL_LABEL:
            # (Select All) was toggled — apply to all option items
            new_state = item.checkState()
            self._guard = True
            for opt in self._option_items():
                opt.setCheckState(new_state)
            self._guard = False
        else:
            # Regular item toggled — update (Select All) to match
            self._guard = True
            self._sync_select_all_state()
            self._guard = False
        self.item_clicked.emit()

    def _on_item_clicked_multi(self, item: QListWidgetItem) -> None:
        """Fallback for checkbox clicks that don't fire itemChanged in Popup windows."""
        if self._change_handled:
            self._change_handled = False
            return
        new_state = (
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setCheckState(new_state)  # triggers _on_item_changed

    def _on_item_clicked_single(self, item: QListWidgetItem) -> None:
        """Single-select: pick and close."""
        self.item_clicked.emit()
        self.close()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()


class OptionsFilter(AbstractFilter):
    """Searchable dropdown filter with optional multi-select."""

    _ALL_LABEL = "(All)"

    def __init__(
        self,
        options_fn: Optional[Callable[[], Sequence[str]]] = None,
        multi_select: bool = False,
        placeholder: str = "Select…",
    ):
        super().__init__()
        self._options_fn = options_fn
        self._multi_select = multi_select
        self._static_options: List[str] = []
        self._checked: set[str] = set()       # multi-select state
        self._selected: str | None = None      # single-select state

        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)

        self._display = QLineEdit()
        self._display.setReadOnly(True)
        self._display.setPlaceholderText(placeholder)
        self._display.mousePressEvent = self._on_display_clicked
        layout.addWidget(self._display)

        self._popup: _OptionsPopup | None = None

    # -- AbstractFilter interface --

    def is_active(self) -> bool:
        if self._multi_select:
            return len(self._checked) > 0
        return self._selected is not None

    def reset(self) -> None:
        self._checked.clear()
        self._selected = None
        self._update_display()

    def checked(self) -> set[str]:
        """Return the currently checked options (multi-select)."""
        if not self._multi_select:
            raise RuntimeError("Tried to use a multi-select method when self._multi_select = False")
        return set(self._checked)

    def set_checked(self, values: set[str]) -> None:
        """Set checked options (multi-select) and emit filter_changed."""
        if not self._multi_select:
            raise RuntimeError("Tried to use a multi-select method when self._multi_select = False")
        self._checked = set(values)
        self._update_display()
        self.filter_changed.emit()

    def selected(self) -> str | None:
        """Return the currently selected option (single-select)."""
        if self._multi_select:
            raise RuntimeError("Tried to use a single-select method when self._multi_select = True")
        return self._selected

    def set_selected(self, value: str | None) -> None:
        """Set selected option (single-select) and emit filter_changed."""
        if self._multi_select:
            raise RuntimeError("Tried to use a single-select method when self._multi_select = True")
        self._selected = value
        self._update_display()
        self.filter_changed.emit()

    def focus(self) -> None:
        self._on_display_clicked(None)

    def apply_filter(self, series: pd.Series) -> np.ndarray:
        if self._multi_select:
            if not self._checked:
                return np.ones(len(series), dtype=bool)
            return series.astype(str).isin(self._checked).values
        if self._selected is None:
            return np.ones(len(series), dtype=bool)
        return (series.astype(str) == self._selected).values

    # -- internals --

    def _ensure_popup(self) -> _OptionsPopup:
        if self._popup is None:
            self._popup = _OptionsPopup(self._multi_select)
            self._popup.item_clicked.connect(self._on_popup_interaction)
            self._popup.closed.connect(self._on_popup_closed)
        return self._popup

    def _get_options(self) -> list[str]:
        if self._options_fn is not None:
            return list(self._options_fn())
        return list(self._static_options)

    def _on_display_clicked(self, event) -> None:
        popup = self._ensure_popup()
        options = self._get_options()
        popup.populate(options, self._checked if self._multi_select else None)
        pos = self.mapToGlobal(QPoint(0, self.height()))
        popup.open_at(pos, self.width())

    def _on_popup_interaction(self) -> None:
        if self._multi_select:
            self._checked = self._popup.get_checked()
        else:
            self._selected = self._popup.get_selected_single()
        self._update_display()
        self.filter_changed.emit()

    def _on_popup_closed(self) -> None:
        # sync final state when popup closes (multi-select)
        if self._multi_select:
            new_checked = self._popup.get_checked()
            if new_checked != self._checked:
                self._checked = new_checked
                self._update_display()
                self.filter_changed.emit()

    def _update_display(self) -> None:
        if self._multi_select:
            n = len(self._checked)
            self._display.setText(f"{n} selected" if n > 0 else "")
        else:
            self._display.setText(self._selected or "")
