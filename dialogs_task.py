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
    get_show_dates_for_task, remove_task_show_date,
    get_sub_tasks, delete_task,
    get_total_focus_time_for_task,
    get_categories # <-- NEW IMPORT
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

        # --- MODIFIED: Category QLineEdit replaced with QComboBox ---
        self.category_combo = QComboBox()
        form_layout.addRow("Category:", self.category_combo)
        # --- END MODIFIED ---

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

        if not self.is_new_task:
            added_label = QLabel(self.task_data.get('date_added', 'N/A'))
            form_layout.addRow("Date Added:", added_label)
            
            # --- NEW: Show Focus Time (for Feature 2) ---
            try:
                # Get total minutes from DB
                total_minutes = get_total_focus_time_for_task(self.task_id)
                # Format into hours and minutes
                hours, minutes = divmod(total_minutes, 60)
                focus_time_str = f"{int(hours)}h {int(minutes)}m" if hours > 0 else f"{int(minutes)}m"
                
                focus_label = QLabel(focus_time_str)
                form_layout.addRow("Total Focus Time:", focus_label)
            except Exception as e:
                print(f"Error loading focus time for task {self.task_id}: {e}")
            # --- END NEW ---

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
        
        # --- SUB-TASK SECTION ---
        # Only show the sub-task section if we are editing an *existing* task
        if not self.is_new_task and self.task_id:
            sub_task_group = QGroupBox("Sub-tasks")
            sub_task_layout = QVBoxLayout(sub_task_group)
            
            self.sub_task_list_widget = QListWidget()
            sub_task_layout.addWidget(self.sub_task_list_widget)
            
            sub_task_button_layout = QHBoxLayout()
            add_sub_task_btn = QPushButton("Add Sub-task")
            add_sub_task_btn.clicked.connect(self._add_sub_task)
            edit_sub_task_btn = QPushButton("Edit Sub-task")
            edit_sub_task_btn.clicked.connect(self._edit_sub_task)
            delete_sub_task_btn = QPushButton("Delete Sub-task")
            delete_sub_task_btn.clicked.connect(self._delete_sub_task)
            
            sub_task_button_layout.addWidget(add_sub_task_btn)
            sub_task_button_layout.addWidget(edit_sub_task_btn)
            sub_task_button_layout.addWidget(delete_sub_task_btn)
            sub_task_layout.addLayout(sub_task_button_layout)
            
            self.layout.addWidget(sub_task_group)
            
            self._load_sub_tasks() # Load existing sub-tasks
        # --- END OF SUB-TASK SECTION ---

        self.notes_editor = QPlainTextEdit(self.task_data.get('notes', ''))
        self.notes_editor.setPlaceholderText("Enter notes for this task...")
        self.layout.addWidget(QLabel("Notes:"))
        self.layout.addWidget(self.notes_editor, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_details)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
        # --- NEW: Load categories into combo box ---
        self._load_categories()
        # --- END NEW ---

    # --- NEW: Category Loader ---
    def _load_categories(self):
        """Loads categories from DB into the combo box."""
        try:
            self.category_combo.clear()
            categories = get_categories()
            category_names = [cat['name'] for cat in categories]
            self.category_combo.addItems(category_names)
            
            # Set the task's current category
            current_category = self.task_data.get('category', 'General')
            if current_category in category_names:
                self.category_combo.setCurrentText(current_category)
            elif "General" in category_names:
                self.category_combo.setCurrentText("General")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load categories: {e}")
            self.category_combo.addItem("General")
    # --- END NEW ---

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
        # --- MODIFIED: Read from category_combo ---
        category = self.category_combo.currentText()
        if not category: # Safeguard if list is empty
            category = "General"
        # --- END MODIFIED ---

        try:
            if self.is_new_task:
                new_task_data = {
                    'id': str(uuid.uuid4()),
                    'description': new_desc,
                    'status': 'pending',
                    'date_added': datetime.now().strftime("%Y-%m-%d"),
                    'deadline': deadline_str,
                    'priority': self.priority_combo.currentText(),
                    'category': category, # <-- Use new variable
                    'notes': self.notes_editor.toPlainText(),
                    'show_mode': show_mode,
                    'parent_task_id': None # Explicitly set new tasks as top-level
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
                    category, # <-- Use new variable
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

    # --- METHODS FOR SUB-TASKS ---

    def _load_sub_tasks(self):
        """ Clears and re-loads the sub-task list widget. """
        if not hasattr(self, 'sub_task_list_widget'):
            return # Should not happen, but a good safeguard
            
        self.sub_task_list_widget.clear()
        try:
            sub_tasks = get_sub_tasks(self.task_id, status="all")
            if not sub_tasks:
                item = QListWidgetItem("No sub-tasks created.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray"))
                self.sub_task_list_widget.addItem(item)
                return

            for sub_task in sub_tasks:
                status_icon = "✓" if sub_task['status'] == 'completed' else "☐"
                item_text = f"{status_icon} {sub_task['description']}"
                item = QListWidgetItem(item_text)
                # Store the *entire* sub-task dictionary in the item
                item.setData(Qt.ItemDataRole.UserRole, sub_task)
                self.sub_task_list_widget.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load sub-tasks: {e}")

    def _add_sub_task(self):
        """ Adds a new sub-task to the current task. """
        desc, ok = QInputDialog.getText(self, "Add Sub-task", "Enter new sub-task description:")
        if ok and desc:
            try:
                # Create a new sub-task, inheriting parent's category
                new_sub_task_data = {
                    'id': str(uuid.uuid4()),
                    'description': desc,
                    'status': 'pending',
                    'date_added': datetime.now().strftime("%Y-%m-%d"),
                    'deadline': None, # Sub-tasks start with no deadline
                    'priority': 'Medium', # Default priority
                    'category': self.task_data.get('category', 'General'), # Inherit category
                    'notes': "",
                    'show_mode': 'auto',
                    'parent_task_id': self.task_id # <-- THIS IS THE LINK
                }
                add_task(new_sub_task_data)
                self._load_sub_tasks() # Refresh the list
                self.task_saved.emit() # Tell the main tab to refresh
            except Exception as e:
                 QMessageBox.critical(self, "Database Error", f"Failed to add sub-task: {e}")

    def _edit_sub_task(self):
        """ Opens the TaskDetailsDialog for the selected sub-task. """
        current_item = self.sub_task_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Edit Error", "Please select a sub-task to edit.")
            return
            
        sub_task_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        # We can re-use the *same* TaskDetailsDialog class to edit the sub-task
        dialog = TaskDetailsDialog(sub_task_data, self, is_new_task=False)
        # When the sub-task dialog saves, we want to:
        # 1. Refresh *this* dialog's sub-task list
        dialog.task_saved.connect(self._load_sub_tasks)
        # 2. Tell the *main window* that data has changed
        dialog.task_saved.connect(self.task_saved)
        dialog.exec()

    def _delete_sub_task(self):
        """ Deletes the selected sub-task. """
        current_item = self.sub_task_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Delete Error", "Please select a sub-task to delete.")
            return

        sub_task_data = current_item.data(Qt.ItemDataRole.UserRole)
        sub_task_id = sub_task_data['id']
        sub_task_desc = sub_task_data['description']
        
        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Are you sure you want to delete sub-task:\n'{sub_task_desc}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_task(sub_task_id) # This will cascade if needed
                self._load_sub_tasks() # Refresh the list
                self.task_saved.emit() # Tell the main tab to refresh
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete sub-task: {e}")


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