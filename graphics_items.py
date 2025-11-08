from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem
)
from PySide6.QtGui import (
    QFont, QColor, QBrush, QPen
)
from PySide6.QtCore import (
    Qt
)

# --- Import from our new structure ---
from app.core.database import get_tasks_for_event

# --- Schedule Event Item ---
class ScheduleEventItem(QGraphicsRectItem):
    """ Custom QGraphicsItem to represent a schedule event block. """
    def __init__(self, event_data, y_start_abs, y_end_abs, width, double_click_handler):
        height = y_end_abs - y_start_abs
        super().__init__(0, 0, width, height)
        self.event_data = event_data
        self.double_click_handler = double_click_handler

        color = QColor(event_data.get('color', '#3B8ED0'))
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setToolTip(f"{event_data['title']}\n{event_data['start_time']} - {event_data['end_time']}")
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        self.title_text = QGraphicsTextItem(event_data['title'], self)
        self.title_text.setDefaultTextColor(Qt.GlobalColor.white)
        font = QFont(); font.setPointSize(9); font.setBold(True)
        self.title_text.setFont(font)
        self.title_text.setPos(5, 5)

        linked_tasks = get_tasks_for_event(event_data['id'])
        task_y_offset = 20
        for task in linked_tasks:
            task_text = QGraphicsTextItem(f"- {task['description']}", self)
            task_text.setDefaultTextColor(Qt.GlobalColor.white)
            task_font = QFont(); task_font.setPointSize(8)
            task_text.setFont(task_font)
            task_text.setPos(10, task_y_offset)
            task_y_offset += 15
            if task_y_offset > (height - 10):
                task_text.setPlainText("- ...")
                break

    def mouseDoubleClickEvent(self, event):
        if self.double_click_handler:
            self.double_click_handler(self.event_data)
        super().mouseDoubleClickEvent(event)