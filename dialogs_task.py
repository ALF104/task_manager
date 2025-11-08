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
    add_task, update_task_details, connect_db, add_task_show_date,
    get_show_dates_for_task, remove_task_show_date
)


# --- Task Details Dialog ---
class TaskDetailsDialog(QDialog):
    task_saved = Signal() # Emits when a task is saved (new or updated)

    def __init__(self, task_data, parent=None, is_new_task=False):
        super().__init__(parent)
        self.task_data = task_data if task_data else {}
        self.task_id = task_data.get('id') if task_data else None
        self.is_new_task = is_new_task
        self.temp_show_dates = set()

        title = "New Task Details" if is_new_task else "Task Details"
        self.setWindowTitle(title)
        self.setMinimumWidth(500)

        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.desc_entry = QLineEdit(self.task_data.get('description', ''))
        form_layout.addRow("Description:", self.desc_entry)

        self.category_entry = QLineEdit(self.task_data.get('category', 'General'))
        form_layout.addRow("Category:", self.category_entry)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText(self.task_data.get('priority', 'Medium'))
        form_layout.addRow("Priority:", self.priority_combo)

        self.deadline_layout = QHBoxLayout()
        current_deadline = self.task_data.get('deadline')
        self.current_qdate_deadline = QDate.fromString(current_deadline, "yyyy-MM-dd") if current_deadline else None
        self.deadline_label = QLabel(current_deadline if current_deadline else "No Deadline")
        deadline_button = QPushButton("Change...")
        deadline_button.clicked.connect(self._select_deadline)
        self.deadline_layout.addWidget(self.deadline_label)
        self.deadline_layout.addWidget(deadline_button)
        self.deadline_layout.addStretch()
        form_layout.addRow("Deadline:", self.deadline_layout)

        added_label = QLabel(self.task_data.get('date_added', 'N/A'))
        if not self.is_new_task:
            form_layout.addRow("Date Added:", added_label)

        self.layout.addLayout(form_layout)

        show_on_group = QGroupBox("Task Visibility")
        show_on_layout = QVBoxLayout(show_on_group)

        self.show_always_check = QCheckBox("Always show in Today's Tasks (until completed)")
        is_always_pending = self.task_data.get('show_mode', 'auto') == 'always_pending'
        self.show_always_check.setChecked(is_always_pending)
        show_on_layout.addWidget(self.show_always_check)

        self.manage_show_dates_button = QPushButton("Manage 'Show On' Dates")
        self.manage_show_dates_button.clicked.connect(self._open_manage_show_dates)

        self.manage_show_dates_button.setEnabled(not is_always_pending)
        self.show_always_check.toggled.connect(
            lambda checked: self.manage_show_dates_button.setEnabled(not checked)
        )
        show_on_layout.addWidget(self.manage_show_dates_button)

        self.layout.addWidget(show_on_group)

        self.notes_editor = QPlainTextEdit(self.task_data.get('notes', ''))
        self.notes_editor.setPlaceholderText("Enter notes for this task...")
        self.layout.addWidget(QLabel("Notes:"))
        self.layout.addWidget(self.notes_editor, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_details)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _select_deadline(self):
        dialog = QDialog(self); layout = QVBoxLayout(dialog); calendar = QCalendarWidget(); calendar.setGridVisible(True)
        if self.current_qdate_deadline and self.current_qdate_deadline.isValid(): calendar.setSelectedDate(self.current_qdate_deadline)
        else: calendar.setSelectedDate(QDate.currentDate())
        layout.addWidget(calendar)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Reset)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); bb.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: calendar.setSelectedDate(QDate()))
        layout.addWidget(bb)
        if dialog.exec():
            selected_qdate = calendar.selectedDate()
            if selected_qdate.isValid():
                self.current_qdate_deadline = selected_qdate; self.deadline_label.setText(selected_qdate.toString("yyyy-MM-dd"))
            else:
                self.current_qdate_deadline = None; self.deadline_label.setText("No Deadline")

    def save_details(self):
        new_desc = self.desc_entry.text().strip()
        if not new_desc:
            QMessageBox.warning(self, "Input Error", "Description cannot be empty.")
            return

        deadline_str = self.current_qdate_deadline.toString("yyyy-MM-dd") if self.current_qdate_deadline else None
        show_mode = 'always_pending' if self.show_always_check.isChecked() else 'auto'

        try:
            if self.is_new_task:
                new_task_data = {
                    'id': str(uuid.uuid4()),
                    'description': new_desc,
                    'status': 'pending',
                    'date_added': datetime.now().strftime("%Y-%m-%d"),
                    'deadline': deadline_str,
                    'priority': self.priority_combo.currentText(),
                    'category': self.category_entry.text().strip() or "General",
                    'notes': self.notes_editor.toPlainText(),
                    'show_mode': show_mode
                }
                new_task_id = add_task(new_task_data)

                if self.temp_show_dates:
                    conn = connect_db()
                    try:
                        for q_date in self.temp_show_dates:
                            add_task_show_date(new_task_id, q_date.toString("yyyy-MM-dd"), db_conn=conn)
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        raise e
                    finally:
                        conn.close()
            else:
                update_task_details(
                    self.task_id, new_desc, self.priority_combo.currentText(),
                    self.category_entry.text().strip() or "General",
                    deadline_str, self.notes_editor.toPlainText(),
                    show_mode
                )

            self.task_saved.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to save task details: {e}")

    def _open_manage_show_dates(self):
        if self.is_new_task:
            dialog = ManageShowDatesDialog(task_id=None, initial_dates_set=self.temp_show_dates, parent=self)
            if dialog.exec():
                self.temp_show_dates = dialog.get_selected_dates()
        else:
            dialog = ManageShowDatesDialog(task_id=self.task_id, initial_dates_set=None, parent=self)
            dialog.exec()
            self.task_saved.emit()


# --- Manage Show Dates Dialog ---
class ManageShowDatesDialog(QDialog):
    def __init__(self, task_id=None, initial_dates_set=None, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        # Use the passed set (for new tasks) or create an empty one (for existing)
        self.selected_dates = initial_dates_set if initial_dates_set is not None else set()

        self.setWindowTitle("Manage 'Show On' Dates")
        self.setMinimumSize(400, 300)

        self.layout = QHBoxLayout(self)

        # Left side: Calendar
        calendar_layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self._on_date_clicked)
        calendar_layout.addWidget(QLabel("Click a date to add/remove it:"))
        calendar_layout.addWidget(self.calendar)

        # Right side: List of dates
        list_layout = QVBoxLayout()
        self.dates_list_widget = QListWidget()
        remove_button = QPushButton("Remove Selected Date")
        remove_button.clicked.connect(self._remove_date)
        list_layout.addWidget(QLabel("Scheduled Dates:"))
        list_layout.addWidget(self.dates_list_widget)
        list_layout.addWidget(remove_button)

        self.layout.addLayout(calendar_layout, 1)
        self.layout.addLayout(list_layout, 1)

        close_button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button_box.rejected.connect(self.accept) # Close maps to accept
        list_layout.addWidget(close_button_box)

        self._load_and_highlight_dates()

    def _load_and_highlight_dates(self):
        """ Fetches dates from DB (if task_id) or uses self.selected_dates, then populates UI. """
        self.dates_list_widget.clear()

        # Clear all previous formats
        default_format = QTextCharFormat()
        self.calendar.setDateTextFormat(QDate(), default_format)

        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#1F6AA5"))
        highlight_format.setForeground(QColor("white"))

        try:
            # If it's an existing task, load from DB into self.selected_dates
            if self.task_id and not self.selected_dates: # Only load if not already populated
                 dates_str_list = get_show_dates_for_task(self.task_id)
                 self.selected_dates = {QDate.fromString(d, "yyyy-MM-dd") for d in dates_str_list if QDate.fromString(d, "yyyy-MM-dd").isValid()}

            # Now use self.selected_dates (either from DB or passed in)
            sorted_dates = sorted(list(self.selected_dates))

            for q_date in sorted_dates:
                self.dates_list_widget.addItem(q_date.toString("yyyy-MM-dd"))
                self.calendar.setDateTextFormat(q_date, highlight_format)
        except Exception as e:
            print(f"Error loading show dates: {e}")

    def _on_date_clicked(self, q_date):
        """ Adds or removes the clicked date from the set/DB. """
        date_str = q_date.toString("yyyy-MM-dd")
        if q_date in self.selected_dates:
            # Date already exists, so remove it
            self.selected_dates.remove(q_date)
            if self.task_id: # If existing task, update DB
                try: remove_task_show_date(self.task_id, date_str)
                except Exception as e: QMessageBox.critical(self, "Database Error", f"Could not remove date: {e}")
        else:
            # Date does not exist, add it
            self.selected_dates.add(q_date)
            if self.task_id: # If existing task, update DB
                try: add_task_show_date(self.task_id, date_str)
                except Exception as e: QMessageBox.critical(self, "Database Error", f"Could not add date: {e}")

        self._load_and_highlight_dates() # Refresh list and highlights

    def _remove_date(self):
        """ Removes the selected date from the task's show_dates. """
        current_item = self.dates_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Remove Error", "Please select a date from the list to remove.")
            return

        date_str = current_item.text()
        q_date = QDate.fromString(date_str, "yyyy-MM-dd")

        if q_date in self.selected_dates:
            self.selected_dates.remove(q_date)
            if self.task_id: # If existing task, update DB
                try: remove_task_show_date(self.task_id, date_str)
                except Exception as e: QMessageBox.critical(self, "Database Error", f"Could not remove date: {e}")

        self._load_and_highlight_dates() # Refresh

    def get_selected_dates(self):
        """ Returns the set of selected QDate objects (for new tasks). """
        return self.selected_dates