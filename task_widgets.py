from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QCheckBox, QLabel, QPushButton
)
from PySide6.QtCore import (
    Signal, Qt
)
from datetime import datetime

# --- Custom Widget for Task Row ---
class TaskWidget(QFrame):
    """ Custom widget to display a single task row. """
    status_changed = Signal(str, bool)
    delete_requested = Signal(str)
    info_requested = Signal(dict)

    def __init__(self, task_data):
        super().__init__()
        self.task_data = task_data
        self.task_id = task_data['id']

        self.setObjectName("taskFrame")

        priority = task_data.get('priority', 'Medium')
        self.setProperty("priority", priority) # Set object property for QSS

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 2, 5, 2)

        description_text = task_data.get('description', 'No Description')
        note_indicator = " 📝" if task_data.get("notes") else ""
        schedule_indicator = " 📅" if task_data.get("schedule_event_id") else ""

        self.checkbox = QCheckBox(description_text + note_indicator + schedule_indicator)
        self.checkbox.setChecked(task_data.get('status') == 'completed')
        self.checkbox.stateChanged.connect(self._emit_status_change)
        self.layout.addWidget(self.checkbox, 1)

        deadline_text = f"Deadline: {task_data.get('deadline')}" if task_data.get("deadline") else "No Deadline"
        self.deadline_label = QLabel(deadline_text)
        today_str = datetime.now().strftime("%Y-%m-%d")

        # This styling is for real-time alerts (overdue) and is fine to keep.
        deadline_color = "color: #E53935;" if task_data.get("deadline") and task_data.get("deadline") < today_str else "color: gray;"
        self.deadline_label.setStyleSheet(deadline_color)

        self.layout.addWidget(self.deadline_label)

        self.info_button = QPushButton("Info")
        self.info_button.setFixedWidth(50)
        self.info_button.clicked.connect(self._emit_info_request)
        self.layout.addWidget(self.info_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setFixedWidth(60)
        self.delete_button.setStyleSheet("background-color: #D32F2F;") # Red color
        self.delete_button.clicked.connect(self._emit_delete_request)
        self.layout.addWidget(self.delete_button)

    def _emit_status_change(self, state):
        self.status_changed.emit(self.task_id, state == Qt.CheckState.Checked.value)

    def _emit_delete_request(self):
        self.delete_requested.emit(self.task_id)

    def _emit_info_request(self):
        self.info_requested.emit(self.task_data)

# --- Task Widget for Today Dashboard ---
class TodayTaskWidget(QFrame):
    """
    Custom widget for the 'Today' dashboard list.
    Checking this box logs completion for *today* only.
    """
    completion_changed = Signal(str, str, bool)

    def __init__(self, task_data, is_complete_today):
        super().__init__()
        self.task_data = task_data
        self.task_id = task_data['id']
        self.today_str = datetime.now().strftime("%Y-%m-%d")

        self.setObjectName("todayTaskFrame")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.checkbox = QCheckBox(task_data.get('description', 'No Description'))
        self.checkbox.setChecked(is_complete_today)
        self.checkbox.stateChanged.connect(self._emit_completion_change)
        self.layout.addWidget(self.checkbox, 1)

        priority = task_data.get('priority', 'Medium')
        priority_label = QLabel(priority)

        # This styling is fine, as it's specific to the logic of this widget
        colors = {"High": "#E57373", "Medium": "#FFF176", "Low": "#81C784"}
        priority_label.setStyleSheet(f"color: {colors.get(priority, 'gray')}; font-weight: bold;")
        self.layout.addWidget(priority_label)

    def _emit_completion_change(self, state):
        self.completion_changed.emit(self.task_id, self.today_str, state == Qt.CheckState.Checked.value)