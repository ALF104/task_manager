from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QCheckBox, QLabel, QPushButton,
    QVBoxLayout, QMessageBox  # <-- NEW: Added QMessageBox
)
from PySide6.QtCore import (
    Signal, Qt
)
from datetime import datetime

# --- Custom Widget for Task Row (MODIFIED) ---
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

        # --- MODIFIED: Main layout is now Vertical ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5) # Added a bit more margin
        self.main_layout.setSpacing(2) # Space between task and tags
        
        # Top layout holds the main controls
        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        # --- END MODIFIED ---

        description_text = task_data.get('description', 'No Description')
        note_indicator = " 📝" if task_data.get("notes") else ""
        schedule_indicator = " 📅" if task_data.get("schedule_event_id") else ""
        
        # --- NEW: Dependency Indicator ---
        self.pending_dep_count = task_data.get('pending_dependency_count', 0)
        dep_indicator = " 🔒" if self.pending_dep_count > 0 else ""
        # --- END NEW ---

        self.checkbox = QCheckBox(description_text + note_indicator + schedule_indicator + dep_indicator)
        if self.pending_dep_count > 0:
            self.checkbox.setToolTip(f"This task is blocked by {self.pending_dep_count} pending prerequisite(s).")
            # We can't disable it entirely, or the user can't uncheck it
            # self.checkbox.setEnabled(False) 
        
        self.checkbox.setChecked(task_data.get('status') == 'completed')
        self.checkbox.stateChanged.connect(self._emit_status_change)
        self.top_layout.addWidget(self.checkbox, 1) # Add to top layout

        deadline_text = f"Deadline: {task_data.get('deadline')}" if task_data.get("deadline") else "No Deadline"
        self.deadline_label = QLabel(deadline_text)
        today_str = datetime.now().strftime("%Y-%m-%d")

        deadline_color = "color: #E53935;" if task_data.get("deadline") and task_data.get("deadline") < today_str else "color: gray;"
        self.deadline_label.setStyleSheet(deadline_color)

        self.top_layout.addWidget(self.deadline_label) # Add to top layout

        self.info_button = QPushButton("Info")
        self.info_button.setFixedWidth(50)
        self.info_button.clicked.connect(self._emit_info_request)
        self.top_layout.addWidget(self.info_button) # Add to top layout

        self.delete_button = QPushButton("Delete")
        self.delete_button.setFixedWidth(60)
        self.delete_button.setStyleSheet("background-color: #D32F2F;") # Red color
        self.delete_button.clicked.connect(self._emit_delete_request)
        self.top_layout.addWidget(self.delete_button) # Add to top layout
        
        self.main_layout.addLayout(self.top_layout) # Add top layout to main VBox
        
        # --- NEW: Add Tags Label ---
        tags_text = self.task_data.get('tags')
        if tags_text:
            self.tags_label = QLabel(f"Tags: {tags_text}")
            # Style to be small, grey, and indented
            self.tags_label.setStyleSheet("font-size: 8pt; color: gray; padding-left: 25px; background-color: transparent;")
            self.main_layout.addWidget(self.tags_label)
        # --- END NEW ---

    def _emit_status_change(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        
        # --- NEW: Dependency Check ---
        # Only block if user is trying to *check* the box
        if is_checked and self.pending_dep_count > 0:
            QMessageBox.warning(self, "Task Blocked",
                                f"This task is blocked by {self.pending_dep_count} pending prerequisite(s).\n"
                                "Complete the other task(s) first.")
            self.checkbox.setChecked(False) # Revert the checkbox
            return # Stop here
        # --- END NEW ---
            
        self.status_changed.emit(self.task_id, is_checked)

    def _emit_delete_request(self):
        self.delete_requested.emit(self.task_id)

    def _emit_info_request(self):
        self.info_requested.emit(self.task_data)

# --- Task Widget for Today Dashboard (MODIFIED) ---
class TodayTaskWidget(QFrame):
    """
    Custom widget for the 'Today' dashboard list.
    Checking this box logs completion for *today* only.
    """
    completion_changed = Signal(str, str, bool)

    def __init__(self, task_data, is_complete_today, display_description=None):
        super().__init__()
        self.task_data = task_data
        self.task_id = task_data['id']
        self.today_str = datetime.now().strftime("%Y-%m-%d")

        self.setObjectName("todayTaskFrame")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        # --- MODIFIED: Use separate CheckBox and RichText Label ---
        if display_description is None:
            display_description = task_data.get('description', 'No Description')
            
        # --- NEW: Dependency Indicator ---
        self.pending_dep_count = task_data.get('pending_dependency_count', 0)
        dep_indicator = " 🔒" if self.pending_dep_count > 0 else ""
        # --- END NEW ---
            
        self.checkbox = QCheckBox() # No text
        self.checkbox.setChecked(is_complete_today)
        self.checkbox.stateChanged.connect(self._emit_completion_change)
        
        self.description_label = QLabel(display_description + dep_indicator) # Add indicator
        self.description_label.setTextFormat(Qt.TextFormat.RichText) # <-- Render HTML
        self.description_label.setWordWrap(True)
        
        if self.pending_dep_count > 0:
            self.description_label.setToolTip(f"This task is blocked by {self.pending_dep_count} pending prerequisite(s).")
        
        self.layout.addWidget(self.checkbox) # Add checkbox (no stretch)
        self.layout.addWidget(self.description_label, 1) # Add label (with stretch)
        # --- END MODIFIED ---

        # --- MODIFIED: Use QSS property for highlighting ---
        priority = task_data.get('priority', 'Medium')
        self.setProperty("priority", priority)
        # --- END MODIFIED (Priority label is removed) ---
        

    def _emit_completion_change(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        
        # --- NEW: Dependency Check ---
        if is_checked and self.pending_dep_count > 0:
            QMessageBox.warning(self, "Task Blocked",
                                f"This task is blocked by {self.pending_dep_count} pending prerequisite(s).\n"
                                "Complete the other task(s) first.")
            self.checkbox.setChecked(False) # Revert the checkbox
            return # Stop here
        # --- END NEW ---
        
        self.completion_changed.emit(self.task_id, self.today_str, is_checked)