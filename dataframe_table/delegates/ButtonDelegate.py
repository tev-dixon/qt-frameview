from __future__ import annotations

from typing import Any, Callable, Optional, Union

from PyQt6.QtCore import QEvent, QModelIndex, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QStyledItemDelegate


class ButtonDelegate(QStyledItemDelegate):
    """Paints a clickable button in each cell.

    Args:
        text: Fixed label **or** ``(source_row_idx, raw_value) -> str``.
        on_click: ``(source_row_iloc_index) -> None`` called on click.
        padding: Pixels between cell edge and button rect.
    """

    def __init__(
        self,
        text: Union[str, Callable[[int, Any], str]] = "Click",
        on_click: Optional[Callable[[int], None]] = None,
        padding: int = 4,
        parent=None,
    ):
        super().__init__(parent)
        self._text = text
        self._on_click = on_click
        self._padding = padding
        self._pressed_index: Optional[QModelIndex] = None

    def _resolve_text(self, index: QModelIndex) -> str:
        if callable(self._text):
            source_row = index.data(Qt.ItemDataRole.UserRole)
            raw = index.data(Qt.ItemDataRole.EditRole)
            return self._text(source_row, raw)
        return self._text

    def _button_rect(self, cell_rect: QRect) -> QRect:
        p = self._padding
        return cell_rect.adjusted(p, p, -p, -p)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        btn_rect = self._button_rect(option.rect)
        text = self._resolve_text(index)
        pressed = self._pressed_index is not None and self._pressed_index == index

        painter.save()
        bg = QColor("#d0d0d0") if pressed else QColor("#e8e8e8")
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(btn_rect, 3, 3)
        painter.setPen(QPen(QColor("#222222")))
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        btn_rect = self._button_rect(option.rect)

        if event.type() == QEvent.Type.MouseButtonPress and btn_rect.contains(event.position().toPoint()):
            self._pressed_index = index
            return True

        if event.type() == QEvent.Type.MouseButtonRelease:
            was_pressed = self._pressed_index == index
            self._pressed_index = None
            if was_pressed and btn_rect.contains(event.position().toPoint()) and self._on_click:
                source_row = index.model().source_index(index.row())
                self._on_click(source_row)
                return True

        return False

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setHeight(max(hint.height(), 28 + self._padding * 2))
        return hint
