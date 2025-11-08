import uuid
from datetime import datetime, timedelta, time, date
import sqlite3 # For IntegrityError

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QScrollArea, QFrame, QCheckBox, QPlainTextEdit, QMessageBox,
    QFileDialog, QSizePolicy, QSpacerItem, QCalendarWidget, QDialog,
    QTimeEdit, QDialogButtonBox, QFormLayout, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QTextBrowser,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QGroupBox, QToolBar,
    QTextEdit, QInputDialog, QSpinBox
)
from PySide6.QtGui import (
    QFont, QColor, QPen, QBrush, QAction, QTextCharFormat,
    QPainterPath, QTextListFormat, QIntValidator
)
from PySide6.QtCore import (
    Qt, QTime, QDate, QRectF, Signal
)

# --- Import from our new structure ---
from app.core.database import (
    get_app_state, set_app_state, get_all_daily_notes,
    get_tasks_by_deadline, get_completed_tasks_for_date,
    get_schedule_events_for_date, get_calendar_events_for_date, get_daily_note
)
# We need this for the "Manage Automations" button
from app.widgets.dialogs_automation import ManageAutomationsDialog
# Get the app version from our central init file
from app import APP_VERSION


# --- Pomodoro Settings Dialog ---
class PomodoroSettingsDialog(QDialog):
    """
    A separate dialog just for managing Pomodoro Timer settings.
    """
    pomodoro_settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pomodoro Timer Settings")

        self.layout = QVBoxLayout(self)

        pomodoro_layout = QFormLayout()

        self.work_min_spin = QSpinBox()
        self.work_min_spin.setRange(1, 120)
        self.work_min_spin.setValue(int(get_app_state('pomodoro_work_min') or 25))

        self.short_break_spin = QSpinBox()
        self.short_break_spin.setRange(1, 30)
        self.short_break_spin.setValue(int(get_app_state('pomodoro_short_break_min') or 5))

        self.long_break_spin = QSpinBox()
        self.long_break_spin.setRange(1, 60)
        self.long_break_spin.setValue(int(get_app_state('pomodoro_long_break_min') or 15))

        self.sessions_spin = QSpinBox()
        self.sessions_spin.setRange(2, 10)
        self.sessions_spin.setValue(int(get_app_state('pomodoro_sessions') or 4))

        pomodoro_layout.addRow("Work (minutes):", self.work_min_spin)
        pomodoro_layout.addRow("Short Break (minutes):", self.short_break_spin)
        pomodoro_layout.addRow("Long Break (minutes):", self.long_break_spin)
        pomodoro_layout.addRow("Sessions before long break:", self.sessions_spin)

        self.layout.addLayout(pomodoro_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._save_pomodoro_settings)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _save_pomodoro_settings(self):
        """Saves all pomodoro settings to the database."""
        try:
            set_app_state('pomodoro_work_min', str(self.work_min_spin.value()))
            set_app_state('pomodoro_short_break_min', str(self.short_break_spin.value()))
            set_app_state('pomodoro_long_break_min', str(self.long_break_spin.value()))
            set_app_state('pomodoro_sessions', str(self.sessions_spin.value()))

            self.pomodoro_settings_changed.emit()
            QMessageBox.information(self, "Saved", "Timer settings saved!")
            self.accept() # Close the dialog

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save timer settings: {e}")


# --- Settings Dialog ---
class SettingsDialog(QDialog):
    theme_changed = Signal()
    pomodoro_settings_changed = Signal()
    personalization_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)

        # --- Personalization Settings ---
        personal_group = QGroupBox("Personalization")
        personal_layout = QFormLayout(personal_group)

        self.name_entry = QLineEdit()
        self.name_entry.setPlaceholderText("Your Name")
        self.name_entry.setText(get_app_state('user_name') or '')
        self.name_entry.editingFinished.connect(self._save_user_name)

        personal_layout.addRow("Your Name:", self.name_entry)
        self.layout.addWidget(personal_group)

        # --- Theme Settings ---
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])

        current_theme = get_app_state('theme') or 'system'
        self.theme_combo.setCurrentText(current_theme.capitalize())

        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addRow("App Theme:", self.theme_combo)
        self.layout.addWidget(theme_group)

        other_group = QGroupBox("Modules & Data")
        other_layout = QVBoxLayout(other_group)

        self.pomodoro_settings_button = QPushButton("Manage Timer Settings...")
        self.pomodoro_settings_button.clicked.connect(self._open_pomodoro_settings)
        other_layout.addWidget(self.pomodoro_settings_button)

        self.automation_button = QPushButton("Manage Automations")
        self.automation_button.clicked.connect(self._open_automations_dialog)
        other_layout.addWidget(self.automation_button)

        self.export_button = QPushButton("Export Tasks to CSV")
        self.export_button.clicked.connect(self.parent_window._export_tasks)
        other_layout.addWidget(self.export_button)

        self.prev_notes_button = QPushButton("View Daily History")
        self.prev_notes_button.clicked.connect(self.parent_window._open_history_dialog)
        other_layout.addWidget(self.prev_notes_button)

        self.layout.addWidget(other_group)

        self.layout.addStretch()

        # --- About Section ---
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout(about_group)

        version_label = QLabel(f"Version: {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dev_label = QLabel("Developed by ALF") # Or your name
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_label.setStyleSheet("font-size: 9pt; color: gray;")

        about_layout.addWidget(version_label)
        about_layout.addWidget(dev_label)
        self.layout.addWidget(about_group)

        # --- Close Button ---
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        self.layout.addWidget(close_button)

    def _save_user_name(self):
        """Saves the user name when editing is finished."""
        try:
            set_app_state('user_name', self.name_entry.text())
            self.personalization_changed.emit() # Tell main window to update
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save name: {e}")

    def _on_theme_changed(self, text):
        """Saves the new theme setting to the database."""
        try:
            set_app_state('theme', text.lower())
            self.theme_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save theme setting: {e}")

    def _open_pomodoro_settings(self):
        """Opens the separate dialog for Pomodoro settings."""
        dialog = PomodoroSettingsDialog(self)
        # We catch the signal from the sub-dialog and pass it up
        dialog.pomodoro_settings_changed.connect(self.pomodoro_settings_changed)
        dialog.exec()

    def _open_automations_dialog(self):
        dialog = ManageAutomationsDialog(self)
        dialog.exec()

# --- History Dialog ---
class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Daily History")
        self.setMinimumSize(800, 600)

        self.layout = QHBoxLayout(self)

        # --- Left Side: Calendar ---
        calendar_widget = QCalendarWidget()
        calendar_widget.setGridVisible(True)
        calendar_widget.setMaximumWidth(300)
        calendar_widget.clicked.connect(self._on_date_selected)
        self.layout.addWidget(calendar_widget)

        # --- Right Side: Data Display ---
        self.data_area = QWidget()
        data_layout = QVBoxLayout(self.data_area)
        self.layout.addWidget(self.data_area, 1)

        self.selected_date_label = QLabel("Select a date")
        font = QFont(); font.setPointSize(14); font.setBold(True)
        self.selected_date_label.setFont(font)
        data_layout.addWidget(self.selected_date_label)

        # --- Columns for Data ---
        columns_layout = QHBoxLayout()
        data_layout.addLayout(columns_layout, 1)

        # Column 1: Tasks
        tasks_group = QGroupBox("Tasks")
        tasks_layout = QVBoxLayout(tasks_group)
        self.tasks_scroll_area = QScrollArea()
        self.tasks_scroll_area.setWidgetResizable(True)
        tasks_list_widget = QWidget()
        self.tasks_list_layout = QVBoxLayout(tasks_list_widget)
        self.tasks_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tasks_scroll_area.setWidget(tasks_list_widget)
        tasks_layout.addWidget(self.tasks_scroll_area)
        columns_layout.addWidget(tasks_group)

        # Column 2: Schedule & Events
        schedule_group = QGroupBox("Schedule & Events")
        schedule_layout = QVBoxLayout(schedule_group)
        self.schedule_scroll_area = QScrollArea()
        self.schedule_scroll_area.setWidgetResizable(True)
        schedule_list_widget = QWidget()
        self.schedule_list_layout = QVBoxLayout(schedule_list_widget)
        self.schedule_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.schedule_scroll_area.setWidget(schedule_list_widget)
        schedule_layout.addWidget(self.schedule_scroll_area)
        columns_layout.addWidget(schedule_group)

        # Bottom: Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_preview = QTextBrowser()
        self.notes_preview.setOpenExternalLinks(True)
        notes_layout.addWidget(self.notes_preview, 1)
        data_layout.addWidget(notes_group, 1) # Give notes 1 stretch factor

        # Set initial date
        calendar_widget.setSelectedDate(QDate.currentDate())
        self._on_date_selected(QDate.currentDate())

    def _clear_layout(self, layout):
        """Helper function to remove all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _on_date_selected(self, q_date):
        """Fetches and displays all data for the newly selected date."""
        date_str = q_date.toString("yyyy-MM-dd")
        self.selected_date_label.setText(q_date.toString("dddd, MMM d, yyyy"))

        # Clear previous data
        self._clear_layout(self.tasks_list_layout)
        self._clear_layout(self.schedule_list_layout)
        self.notes_preview.clear()

        # --- Load Tasks ---
        try:
            tasks_pending = get_tasks_by_deadline(date_str)
            tasks_completed = get_completed_tasks_for_date(date_str)

            if not tasks_pending and not tasks_completed:
                self.tasks_list_layout.addWidget(QLabel("No tasks for this day."))

            if tasks_completed:
                completed_label = QLabel("<b>Completed</b>")
                self.tasks_list_layout.addWidget(completed_label)
                for task in tasks_completed:
                    label = QLabel(f"✓ {task['description']}")
                    label.setStyleSheet("color: gray;")
                    self.tasks_list_layout.addWidget(label)

            if tasks_pending:
                pending_label = QLabel("<b>Pending on this day</b>")
                self.tasks_list_layout.addWidget(pending_label)
                for task in tasks_pending:
                    label = QLabel(f"• {task['description']}")
                    self.tasks_list_layout.addWidget(label)

        except Exception as e:
            print(f"Error loading history tasks: {e}")
            self.tasks_list_layout.addWidget(QLabel("Error loading tasks."))

        # --- Load Schedule ---
        try:
            schedule_events = get_schedule_events_for_date(date_str)
            if not schedule_events:
                 self.schedule_list_layout.addWidget(QLabel("No schedule blocks."))
            else:
                for event in schedule_events:
                     label = QLabel(f"{event['start_time']} - {event['end_time']}: {event['title']}")
                     label.setObjectName("todayScheduleLabel")
                     label.setWordWrap(True)
                     self.schedule_list_layout.addWidget(label)
        except Exception as e:
            print(f"Error loading history schedule: {e}")
            self.schedule_list_layout.addWidget(QLabel("Error loading schedule."))

        # --- Load Events ---
        try:
            calendar_events = get_calendar_events_for_date(date_str)
            if calendar_events:
                self.schedule_list_layout.addSpacing(15)
                self.schedule_list_layout.addWidget(QLabel("<b>Calendar Events</b>"))
                for event in calendar_events:
                     start_time = event.get('start_time')
                     title = event['title']
                     display_text = f"{title} ({start_time})" if start_time else title
                     label = QLabel(display_text)
                     label.setObjectName("todayEventLabel")
                     label.setWordWrap(True)
                     self.schedule_list_layout.addWidget(label)
        except Exception as e:
            print(f"Error loading history events: {e}")
            self.schedule_list_layout.addWidget(QLabel("Error loading events."))

        # --- Load Notes ---
        try:
            content = get_daily_note(date_str) or "<p><i>No notes for this day.</i></p>"
            if hasattr(self.parent_window, '_render_note_html'):
                self.parent_window._render_note_html(content, self.notes_preview)
            else:
                self.notes_preview.setHtml(content) # Fallback
        except Exception as e:
            print(f"Error loading history notes: {e}")
            self.notes_preview.setHtml("<p>Error loading notes.</p>")