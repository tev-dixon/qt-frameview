from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QEvent, QModelIndex, QRect, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionButton, QStyleOptionViewItem, QStyledItemDelegate


class CheckBoxDelegate(QStyledItemDelegate):

    def __init__(
        self,
        on_toggle: Optional[Callable[[int, bool], None]] = None,
        is_disabled: Optional[Callable[[int], bool]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_toggle = on_toggle
        self._is_disabled = is_disabled

    def _row_disabled(self, index: QModelIndex) -> bool:
        if self._is_disabled is None:
            return False
        source_row = index.model().source_index(index.row())
        return self._is_disabled(source_row)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        checked = bool(index.data(Qt.ItemDataRole.UserRole))
        cb_opt = QStyleOptionButton()

        if self._row_disabled(index):
            cb_opt.state = QStyle.StateFlag.State_Off  # no State_Enabled → greyed out
        else:
            cb_opt.state = QStyle.StateFlag.State_Enabled

        cb_opt.state |= QStyle.StateFlag.State_On if checked else QStyle.StateFlag.State_Off
        cb_opt.rect = self._checkbox_rect(option)
        style.drawControl(QStyle.ControlElement.CE_CheckBox, cb_opt, painter)

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            if self._row_disabled(index):
                return True  # swallow the click, do nothing
            cb_rect = self._checkbox_rect(option)
            if cb_rect.contains(event.position().toPoint()):
                current = bool(index.data(Qt.ItemDataRole.UserRole))
                if self._on_toggle:
                    source_row = model.source_index(index.row())
                    self._on_toggle(source_row, not current)
                return True
        return False
    
    def createEditor(self, parent, option, index):
        return None # override prevents default text editor from appearing

    @staticmethod
    def _checkbox_rect(option: QStyleOptionViewItem) -> QRect:
        size = 20
        r = option.rect
        return QRect(r.x() + (r.width() - size) // 2, r.y() + (r.height() - size) // 2, size, size)
