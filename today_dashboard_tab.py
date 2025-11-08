import uuid
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QScrollArea, QFrame, QMessageBox, QGroupBox
)
from PySide6.QtCore import (
    Signal, Qt, QDate
)
from PySide6.QtGui import QFont

# --- Import from our new structure ---
from app.core.database import (
    get_tasks_by_deadline, get_tasks_by_show_date, get_tasks_always_pending,
    is_task_logged_complete, get_show_dates_for_task, log_task_completion,
    remove_task_completion_log, get_all_tasks, update_task_status,
    get_schedule_events_for_date, get_calendar_events_for_date,
    get_daily_note, save_daily_note
)
from app.widgets.task_widgets import TodayTaskWidget

# --- Today Dashboard Tab Widget ---
class TodayDashboardTab(QWidget):
    """
    A self-contained widget for the "Today" dashboard.
    Manages its own UI, date navigation, and data loading.
    """
    # Signal emitted when a task is changed (affects other tabs)
    task_list_updated = Signal()
    # Signal emitted when a quick note is added
    note_list_updated = Signal()
    # ***BUG FIX***: Signal to tell other tabs (like Schedule) what date we're on
    dashboard_date_changed = Signal(QDate)


    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Member Variables ---
        self.dashboard_date = QDate.currentDate()

        # --- Setup UI ---
        self._setup_ui()

        # --- Load Initial Data ---
        self._refresh_today_dashboard()

    def _setup_ui(self):
        """Builds the UI for this tab."""
        main_layout = QVBoxLayout(self)
        
        # --- Date Navigation ---
        nav_layout = QHBoxLayout()
        prev_day_button = QPushButton("< Prev Day")
        prev_day_button.clicked.connect(self._prev_day)
        self.today_date_label = QLabel("Today")
        font = QFont(); font.setPointSize(16); font.setBold(True)
        self.today_date_label.setFont(font)
        self.today_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        next_day_button = QPushButton("Next Day >")
        next_day_button.clicked.connect(self._next_day)
        
        nav_layout.addWidget(prev_day_button)
        nav_layout.addWidget(self.today_date_label, 1)
        nav_layout.addWidget(next_day_button)
        main_layout.addLayout(nav_layout)
        
        # --- Main Columns ---
        columns_layout = QHBoxLayout()
        main_layout.addLayout(columns_layout, 1)
        
        # Column 1: Today's Tasks
        tasks_group = QGroupBox("Today's Tasks")
        tasks_layout = QVBoxLayout(tasks_group)
        self.today_task_scroll_area = QScrollArea()
        self.today_task_scroll_area.setWidgetResizable(True)
        today_task_list_widget = QWidget() 
        self.today_task_list_layout = QVBoxLayout(today_task_list_widget)
        self.today_task_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop) 
        self.today_task_list_layout.setSpacing(2) 
        self.today_task_scroll_area.setWidget(today_task_list_widget)
        tasks_layout.addWidget(self.today_task_scroll_area)
        columns_layout.addWidget(tasks_group, 1)
        
        # Column 2: Today's Schedule
        schedule_group = QGroupBox("Today's Schedule")
        schedule_layout = QVBoxLayout(schedule_group)
        self.today_schedule_scroll_area = QScrollArea()
        self.today_schedule_scroll_area.setWidgetResizable(True)
        today_schedule_list_widget = QWidget() 
        self.today_schedule_list_layout = QVBoxLayout(today_schedule_list_widget)
        self.today_schedule_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop) 
        self.today_schedule_list_layout.setSpacing(2) 
        self.today_schedule_scroll_area.setWidget(today_schedule_list_widget)
        schedule_layout.addWidget(self.today_schedule_scroll_area)
        columns_layout.addWidget(schedule_group, 1)

        # Column 3: Today's Events (Rota)
        events_group = QGroupBox("Today's Events (Rota)")
        events_layout = QVBoxLayout(events_group)
        self.today_events_scroll_area = QScrollArea()
        self.today_events_scroll_area.setWidgetResizable(True)
        today_events_list_widget = QWidget() 
        self.today_events_list_layout = QVBoxLayout(today_events_list_widget)
        self.today_events_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop) 
        self.today_events_list_layout.setSpacing(2) 
        self.today_events_scroll_area.setWidget(today_events_list_widget)
        events_layout.addWidget(self.today_events_scroll_area)
        columns_layout.addWidget(events_group, 1)

        # --- Quick Note Box ---
        quick_note_group = QGroupBox("Quick Note")
        quick_note_layout = QHBoxLayout(quick_note_group)
        self.quick_note_entry = QLineEdit()
        self.quick_note_entry.setPlaceholderText("Add a quick note for today...")
        add_note_button = QPushButton("Add Note")
        add_note_button.clicked.connect(self._add_quick_note)
        quick_note_layout.addWidget(self.quick_note_entry, 1)
        quick_note_layout.addWidget(add_note_button)
        main_layout.addWidget(quick_note_group, 0)

    def _prev_day(self):
        """Moves the dashboard to the previous day."""
        self.dashboard_date = self.dashboard_date.addDays(-1)
        self._refresh_today_dashboard()
        # ***BUG FIX***: Emit the signal
        self.dashboard_date_changed.emit(self.dashboard_date)

    def _next_day(self):
        """Moves the dashboard to the next day."""
        self.dashboard_date = self.dashboard_date.addDays(1)
        self._refresh_today_dashboard()
        # ***BUG FIX***: Emit the signal
        self.dashboard_date_changed.emit(self.dashboard_date)

    def _refresh_today_dashboard(self):
        """Clears and re-populates all three columns with data."""
        if not hasattr(self, 'today_task_list_layout'):
             return
             
        date_str = self.dashboard_date.toString("yyyy-MM-dd")
        
        if self.dashboard_date == QDate.currentDate():
            self.today_date_label.setText("Today's Dashboard")
        else:
            self.today_date_label.setText(self.dashboard_date.toString("dddd, MMM d, yyyy"))

        # Clear existing widgets
        for layout in [self.today_task_list_layout, self.today_schedule_list_layout, self.today_events_list_layout]:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                    
        # --- Populate Today's Tasks ---
        try:
            tasks_deadline = get_tasks_by_deadline(date_str)
            tasks_show_date = get_tasks_by_show_date(date_str)
            tasks_always_pending = get_tasks_always_pending()
            
            all_today_tasks = {}
            for task in tasks_deadline + tasks_show_date + tasks_always_pending:
                all_today_tasks[task['id']] = task
                
            if not all_today_tasks:
                 self.today_task_list_layout.addWidget(QLabel(f"No tasks scheduled for {date_str}."))
            
            priority_map = {"High": 0, "Medium": 1, "Low": 2}
            sorted_tasks = sorted(all_today_tasks.values(), key=lambda t: (
                priority_map.get(t.get('priority', 'Medium'), 1)
            ))

            for task in sorted_tasks:
                task_id = task['id']
                is_complete_today = is_task_logged_complete(task_id, date_str)
                
                is_one_off_complete = (task.get('status') == 'completed' and 
                                       task.get('show_mode') == 'auto' and
                                       not get_show_dates_for_task(task_id) and 
                                       not task.get('created_by_automation_id'))

                if is_one_off_complete:
                    continue 
                if is_complete_today and task.get('show_mode') == 'always_pending':
                     continue
                if is_complete_today and (get_show_dates_for_task(task_id) or task.get('created_by_automation_id')):
                     continue

                task_widget = TodayTaskWidget(task, is_complete_today)
                task_widget.completion_changed.connect(self._handle_today_task_completion)
                self.today_task_list_layout.addWidget(task_widget)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading Today's Tasks: {e}")
            self.today_task_list_layout.addWidget(QLabel("Error loading tasks."))
            
        # --- Populate Today's Schedule ---
        try:
            schedule_events = get_schedule_events_for_date(date_str)
            if not schedule_events:
                 self.today_schedule_list_layout.addWidget(QLabel(f"No schedule blocks for {date_str}."))

            for event in schedule_events:
                 label = QLabel(f"{event['start_time']} - {event['end_time']}: {event['title']}")
                 # Use objectName for QSS styling
                 label.setObjectName("todayScheduleLabel")
                 # This inline style will be overridden by QSS, but is a good fallback
                 label.setStyleSheet("background-color: #343638; border-radius: 4px; padding: 5px;")
                 label.setWordWrap(True)
                 self.today_schedule_list_layout.addWidget(label)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading Today's Schedule: {e}")
            self.today_schedule_list_layout.addWidget(QLabel("Error loading schedule."))

        # --- Populate Today's Events (Rota) ---
        try:
            calendar_events = get_calendar_events_for_date(date_str)
            if not calendar_events:
                 self.today_events_list_layout.addWidget(QLabel(f"No calendar events for {date_str}."))
                 
            for event in calendar_events:
                 start_time = event.get('start_time')
                 title = event['title']
                 display_text = f"{title} ({start_time})" if start_time else title
                 label = QLabel(display_text)
                 # Use objectName for QSS styling
                 label.setObjectName("todayEventLabel")
                 label.setStyleSheet("background-color: #343638; border-radius: 4px; padding: 5px;")
                 label.setWordWrap(True)
                 self.today_events_list_layout.addWidget(label)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading Today's Events: {e}")
            self.today_events_list_layout.addWidget(QLabel("Error loading events."))
            
    def _handle_today_task_completion(self, task_id, date_str, is_checked):
        """Handles logic when a task checkbox is clicked on the dashboard."""
        try:
            task = next((t for t in get_all_tasks() if t['id'] == task_id), None)
            if not task: return

            is_recurring = (get_show_dates_for_task(task_id) or 
                            task.get('created_by_automation_id') or
                            task.get('show_mode') == 'always_pending')

            if is_recurring:
                if is_checked:
                    log_task_completion(task_id, date_str)
                else:
                    remove_task_completion_log(task_id, date_str)
            else:
                if is_checked:
                    update_task_status(task_id, 'completed', date_str)
                else:
                    update_task_status(task_id, 'pending', None)
            
            self._refresh_today_dashboard()
            self.task_list_updated.emit() # Tell main window to refresh

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not log task completion: {e}")
            self._refresh_today_dashboard()

    def _add_quick_note(self):
        """Adds text from the quick note box to today's note."""
        text_to_add = self.quick_note_entry.text().strip()
        if not text_to_add:
            return
            
        note_date_str = self.dashboard_date.toString("yyyy-MM-dd")
        now_time = datetime.now().strftime("%H:%M")
        
        try:
            current_note_html = get_daily_note(note_date_str) or ""
            new_note_html = f"<p><b>Quick Note ({now_time}):</b> {text_to_add}</p>"
            
            if not current_note_html or current_note_html.startswith("# Start"):
                 final_html = new_note_html
            else:
                 final_html = current_note_html + new_note_html
            
            save_daily_note(note_date_str, final_html)
            self.quick_note_entry.clear()
            
            # Tell main window to refresh the notes tab
            self.note_list_updated.emit()
                
            QMessageBox.information(self, "Note Added", f"Quick note added to {note_date_str}.")
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not add quick note: {e}")