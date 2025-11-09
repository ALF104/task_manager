import uuid
from datetime import datetime, timedelta, time, date
import sqlite3 # For IntegrityError

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QComboBox, QScrollArea, QFrame, QCheckBox, QPlainTextEdit, QMessageBox,
    QFileDialog, QSizePolicy, QSpacerItem, QCalendarWidget, QDialog,
    QTimeEdit, QDialogButtonBox, QFormLayout, QListWidget, QListWidgetItem
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
    get_tasks_for_event, get_tasks, update_schedule_event, add_schedule_event, 
    link_task_to_event, unlink_task_from_event, delete_schedule_event, 
    get_calendar_events_for_date, add_calendar_event, 
    update_calendar_event, delete_calendar_event
)

# --- Schedule Event Dialog ---
class ScheduleEventDialog(QDialog):
    def __init__(self, date_str, event_data=None, start_time=None, end_time=None, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.date_str = date_str
        self.linked_task_vars = {} 

        self.setWindowTitle("Add Schedule Event" if event_data is None else "Edit Schedule Event")
        self.setMinimumWidth(600)

        main_dialog_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()
        main_dialog_layout.addLayout(content_layout)

        # Left Side: Details
        details_widget = QWidget()
        details_layout = QFormLayout(details_widget)
        content_layout.addWidget(details_widget, 1)

        self.title_entry = QLineEdit()
        details_layout.addRow("Title:", self.title_entry)

        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm")
        details_layout.addRow("Start Time:", self.start_time_edit)

        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm")
        details_layout.addRow("End Time:", self.end_time_edit)

        # Right Side: Task Linking
        task_list_widget = QWidget()
        task_list_layout = QVBoxLayout(task_list_widget)
        content_layout.addWidget(task_list_widget, 1)

        task_list_layout.addWidget(QLabel("Link Tasks:"))
        self.task_scroll_area = QScrollArea()
        self.task_scroll_area.setWidgetResizable(True)
        task_scroll_content = QWidget()
        self.task_checkbox_layout = QVBoxLayout(task_scroll_content)
        self.task_checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.task_scroll_area.setWidget(task_scroll_content)
        task_list_layout.addWidget(self.task_scroll_area, 1)

        self._populate_linkable_tasks()

        if event_data:
            self.title_entry.setText(event_data.get('title', ''))
            start_qtime = QTime.fromString(event_data.get('start_time', '09:00'), "HH:mm")
            end_qtime = QTime.fromString(event_data.get('end_time', '10:00'), "HH:mm")
            self.start_time_edit.setTime(start_qtime)
            self.end_time_edit.setTime(end_qtime)
        elif start_time and end_time:
            start_qtime = QTime.fromString(start_time, "HH:mm")
            end_qtime = QTime.fromString(end_time, "HH:mm")
            self.start_time_edit.setTime(start_qtime)
            self.end_time_edit.setTime(end_qtime)
        else:
             self.start_time_edit.setTime(QTime(9, 0))
             self.end_time_edit.setTime(QTime(10, 0))

        self.button_box = QDialogButtonBox()
        if event_data:
            delete_btn = self.button_box.addButton("Delete", QDialogButtonBox.ButtonRole.DestructiveRole)
            delete_btn.clicked.connect(self.delete_event)
            
        self.button_box.addButton(QDialogButtonBox.StandardButton.Save)
        self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        
        self.button_box.accepted.connect(self.save_event)
        self.button_box.rejected.connect(self.reject)
        
        main_dialog_layout.addWidget(self.button_box) 


    def _populate_linkable_tasks(self):
        """
        Populates the task list. 
        *** FIX for Issue #2 ***: Ensures tasks are only checked if
        we are *editing* an event AND the task is *already* linked to it.
        """
        while self.task_checkbox_layout.count():
             item = self.task_checkbox_layout.takeAt(0)
             widget = item.widget()
             if widget: widget.deleteLater()
        self.linked_task_vars.clear()

        all_pending_tasks = get_tasks('pending')
        # Get the ID *before* the loop. It will be None if this is a new event.
        current_event_id = self.event_data['id'] if self.event_data else None
        tasks_found = False

        for task in all_pending_tasks:
            task_id = task['id']
            task_event_id = task.get('schedule_event_id')
            
            # Only show tasks that are unlinked OR already linked to *this specific* event
            if task_event_id is None or task_event_id == current_event_id:
                tasks_found = True
                cb = QCheckBox(task['description'])
                
                # *** THE FIX ***
                # Only check the box if we are *editing* (current_event_id is not None)
                # AND the task is already linked to this event.
                if current_event_id is not None and task_event_id == current_event_id:
                    cb.setChecked(True)
                else:
                    cb.setChecked(False) # Explicitly uncheck for new events

                self.task_checkbox_layout.addWidget(cb)
                self.linked_task_vars[task_id] = cb 
        
        if not tasks_found:
            self.task_checkbox_layout.addWidget(QLabel("No unlinked tasks available."))


    def save_event(self):
        title = self.title_entry.text().strip()
        start_qtime = self.start_time_edit.time()
        end_qtime = self.end_time_edit.time()
        if not title:
            QMessageBox.warning(self, "Input Error", "Event title cannot be empty.")
            return
        if end_qtime <= start_qtime:
            QMessageBox.warning(self, "Input Error", "End time must be after start time.")
            return

        start_str = start_qtime.toString("HH:mm")
        end_str = end_qtime.toString("HH:mm")
        event_id = self.event_data['id'] if self.event_data else str(uuid.uuid4())
        new_event_data = {
            'id': event_id, 'date': self.date_str, 'title': title,
            'start_time': start_str, 'end_time': end_str,
            'color': self.event_data.get('color') if self.event_data else "#3B8ED0" 
        }
        try:
            if self.event_data: 
                update_schedule_event(event_id, new_event_data)
            else: 
                add_schedule_event(new_event_data)
            for task_id, checkbox in self.linked_task_vars.items():
                if checkbox.isChecked():
                    link_task_to_event(task_id, event_id)
                else:
                    unlink_task_from_event(task_id, event_id) 
            self.accept() 
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save schedule event: {e}")


    def delete_event(self):
        """ Deletes the current event after confirmation. """
        if not self.event_data: return

        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Are you sure you want to delete the event '{self.event_data['title']}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_schedule_event(self.event_data['id'])
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not delete schedule event: {e}")

# --- Calendar Date Dialog (for Rota/Events) ---
class CalendarDateDialog(QDialog):
    events_changed = Signal() # Emits when an event is added/edited/deleted

    def __init__(self, q_date, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.q_date = q_date
        self.date_str = q_date.toString("yyyy-MM-dd")
        self.setWindowTitle(f"Events for {self.date_str}")
        self.setMinimumSize(400, 300)
        
        self.layout = QVBoxLayout(self)
        
        self.event_list_widget = QListWidget()
        self.layout.addWidget(self.event_list_widget)
        
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Event")
        add_button.clicked.connect(self._add_event)
        edit_button = QPushButton("Edit Selected")
        edit_button.clicked.connect(self._edit_event)
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self._delete_event)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        self.layout.addLayout(button_layout)
        
        self._load_events()

    def _load_events(self):
        """ Loads events for the selected date into the list. """
        self.event_list_widget.clear()
        try:
            events = get_calendar_events_for_date(self.date_str)
            if not events:
                # --- THIS IS THE FIX ---
                item = QListWidgetItem("No events for this date.")
                # Set flags to make it non-selectable and non-interactive
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray")) # Make it look disabled
                self.event_list_widget.addItem(item)
                # --- END OF FIX ---
            else:
                for event in events:
                    start_time = event.get('start_time')
                    title = event['title']
                    display_text = f"{title} ({start_time})" if start_time else title
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, event['id'])
                    self.event_list_widget.addItem(item)
        except Exception as e:
            print(f"Error loading calendar events: {e}")

    def _add_event(self):
        """ Opens a dialog to add a new event. """
        dialog = AddCalendarEventDialog(self.date_str, parent=self)
        if dialog.exec():
            event_data = {
                'id': str(uuid.uuid4()),
                'date': self.date_str,
                'title': dialog.title_entry.text().strip(),
                'start_time': dialog.start_time_edit.time().toString("HH:mm") if dialog.enable_time_check.isChecked() else None,
                'end_time': dialog.end_time_edit.time().toString("HH:mm") if dialog.enable_time_check.isChecked() else None
            }
            
            try:
                add_calendar_event(event_data)
                
                # --- START OF ADDED CODE (BUGFIX) ---
                # Get the main window and run the automation check for the new event
                # We use self.parent().window() in case self.parent() is the main window
                main_window = self.parent().window() # <<< THIS IS THE FIX
                if hasattr(main_window, 'run_automations_for_event'):
                    main_window.run_automations_for_event(event_data['title'], event_data['date'])
                # --- END OF ADDED CODE (BUGFIX) ---
                
                self._load_events()
                self.events_changed.emit() # Tell parent to refresh
                    
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not add event: {e}")

    def _edit_event(self):
        """ Edits the selected calendar event. """
        current_item = self.event_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Edit Error", "Please select an event to edit.")
            return
            
        event_id = current_item.data(Qt.ItemDataRole.UserRole)
        event_data = next((e for e in get_calendar_events_for_date(self.date_str) if e['id'] == event_id), None)
        if not event_data:
            QMessageBox.critical(self, "Error", "Could not find event data to edit.")
            return

        dialog = AddCalendarEventDialog(self.date_str, event_data=event_data, parent=self)
        if dialog.exec():
            new_title_stripped = dialog.title_entry.text().strip()
            start_time_str = dialog.start_time_edit.time().toString("HH:mm") if dialog.enable_time_check.isChecked() else None
            end_time_str = dialog.end_time_edit.time().toString("HH:mm") if dialog.enable_time_check.isChecked() else None

            try:
                update_calendar_event(event_id, new_title_stripped, start_time_str, end_time_str)
                self._load_events()
                self.events_changed.emit() # Tell parent to refresh
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not update event: {e}")

    def _delete_event(self):
        """ Deletes the selected event. """
        current_item = self.event_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Delete Error", "Please select an event to delete.")
            return
            
        event_id = current_item.data(Qt.ItemDataRole.UserRole)
        event_title = current_item.text()
        
        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Delete event '{event_title}' for {self.date_str}?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_calendar_event(event_id)
                self._load_events()
                self.events_changed.emit() # Tell parent to refresh
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not delete event: {e}")

# --- Add/Edit Calendar Event Dialog ---
class AddCalendarEventDialog(QDialog):
    def __init__(self, date_str, event_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Event" if event_data else "Add Event")
        
        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText("e.g., 'Late Shift'")
        form_layout.addRow("Title:", self.title_entry)
        
        self.enable_time_check = QCheckBox("Add Start/End Time")
        self.layout.addLayout(form_layout)
        self.layout.addWidget(self.enable_time_check)

        self.time_frame = QFrame()
        time_layout = QFormLayout(self.time_frame)
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm")
        time_layout.addRow("Start Time:", self.start_time_edit)
        time_layout.addRow("End Time:", self.end_time_edit)
        
        self.time_frame.setEnabled(False)
        self.enable_time_check.toggled.connect(self.time_frame.setEnabled)
        
        self.layout.addWidget(self.time_frame)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
        if event_data:
            self.title_entry.setText(event_data.get('title', ''))
            start_time_str = event_data.get('start_time')
            end_time_str = event_data.get('end_time')
            
            if start_time_str and end_time_str:
                self.enable_time_check.setChecked(True)
                self.start_time_edit.setTime(QTime.fromString(start_time_str, "HH:mm"))
                self.end_time_edit.setTime(QTime.fromString(end_time_str, "HH:mm"))
            else:
                 self.start_time_edit.setTime(QTime(9,0))
                 self.end_time_edit.setTime(QTime(10,0))
