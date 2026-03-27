from __future__ import annotations

from PyQt6.QtCore import QEvent, QModelIndex, QRect, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionButton, QStyleOptionViewItem, QStyledItemDelegate



class CheckBoxDelegate(QStyledItemDelegate):
    """Paints a native-looking checkbox centred in the cell.

    Reads/writes a boolean via the model's ``EditRole``.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        checked = bool(index.data(Qt.ItemDataRole.UserRole))
        cb_opt = QStyleOptionButton()
        cb_opt.state = QStyle.StateFlag.State_Enabled
        cb_opt.state |= QStyle.StateFlag.State_On if checked else QStyle.StateFlag.State_Off
        cb_opt.rect = self._checkbox_rect(option)
        style.drawControl(QStyle.ControlElement.CE_CheckBox, cb_opt, painter)

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            cb_rect = self._checkbox_rect(option)
            if cb_rect.contains(event.position().toPoint()):
                current = bool(index.data(Qt.ItemDataRole.UserRole))
                model.setData(index, not current, Qt.ItemDataRole.EditRole)
                return True
        return False

    @staticmethod
    def _checkbox_rect(option: QStyleOptionViewItem) -> QRect:
        size = 20
        r = option.rect
        return QRect(r.x() + (r.width() - size) // 2, r.y() + (r.height() - size) // 2, size, size)
