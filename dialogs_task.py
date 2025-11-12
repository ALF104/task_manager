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
    get_categories,
    update_tags_for_task,
    get_all_pending_tasks, get_task_dependencies, # <-- NEW IMPORTS
    add_task_dependency, remove_task_dependency # <-- NEW IMPORTS
)


# --- Task Details Dialog (MODIFIED) ---
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

        self.category_combo = QComboBox()
        form_layout.addRow("Category:", self.category_combo)
        
        self.tags_entry = QLineEdit()
        self.tags_entry.setPlaceholderText("e.g., project-alpha, urgent, client")
        self.tags_entry.setText(self.task_data.get('tags', ''))
        form_layout.addRow("Tags (comma-sep):", self.tags_entry)

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
            
            try:
                total_minutes = get_total_focus_time_for_task(self.task_id)
                hours, minutes = divmod(total_minutes, 60)
                focus_time_str = f"{int(hours)}h {int(minutes)}m" if hours > 0 else f"{int(minutes)}m"
                focus_label = QLabel(focus_time_str)
                form_layout.addRow("Total Focus Time:", focus_label)
            except Exception as e:
                print(f"Error loading focus time for task {self.task_id}: {e}")

        self.layout.addLayout(form_layout)

        # --- Horizontal layout for Visibility and Dependencies ---
        middle_layout = QHBoxLayout()
        
        show_on_group = QGroupBox("Task Visibility")
        show_on_layout = QVBoxLayout(show_on_group)

        self.show_always_check = QCheckBox("Always show in Today's Tasks (until completed)")
        is_always_pending = self.task_data.get('show_mode', 'auto') == 'always_pending'
        self.show_always_check.setChecked(is_always_pending)
        self.show_always_check.setToolTip("Overrides all other visibility settings.")
        show_on_layout.addWidget(self.show_always_check)

        self.manage_show_dates_button = QPushButton("Manage 'Show On' Dates")
        self.manage_show_dates_button.clicked.connect(self._open_manage_show_dates)

        self.manage_show_dates_button.setEnabled(not is_always_pending)
        self.show_always_check.toggled.connect(
            lambda checked: self.manage_show_dates_button.setEnabled(not checked)
        )
        show_on_layout.addWidget(self.manage_show_dates_button)
        show_on_layout.addStretch()
        middle_layout.addWidget(show_on_group)
        
        # --- NEW: Dependencies Group Box ---
        # Only show if we are editing an *existing* task
        if not self.is_new_task and self.task_id:
            dep_group = QGroupBox("Dependencies (Prerequisites)")
            dep_layout = QVBoxLayout(dep_group)
            
            self.dependency_list_widget = QListWidget()
            self.dependency_list_widget.setToolTip("This task cannot be completed until these tasks are done.")
            dep_layout.addWidget(self.dependency_list_widget)
            
            dep_btn_layout = QHBoxLayout()
            add_dep_btn = QPushButton("Add Prerequisite...")
            add_dep_btn.clicked.connect(self._add_dependency)
            remove_dep_btn = QPushButton("Remove Selected")
            remove_dep_btn.clicked.connect(self._remove_dependency)
            
            dep_btn_layout.addWidget(add_dep_btn)
            dep_btn_layout.addWidget(remove_dep_btn)
            dep_layout.addLayout(dep_btn_layout)
            middle_layout.addWidget(dep_group)
            
            self._load_dependencies() # Load existing dependencies
        # --- END NEW ---
        
        self.layout.addLayout(middle_layout)
        
        # --- SUB-TASK SECTION ---
        if not self.is_new_task and self.task_id:
            sub_task_group = QGroupBox("Sub-tasks")
            sub_task_layout = QVBoxLayout(sub_task_group)
            
            self.sub_task_list_widget = QListWidget()
            self.sub_task_list_widget.setToolTip("Sub-tasks must be completed before the parent task can be completed.")
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
        
        self._load_categories()

    def _load_categories(self):
        """Loads categories from DB into the combo box."""
        try:
            self.category_combo.clear()
            categories = get_categories()
            category_names = [cat['name'] for cat in categories]
            self.category_combo.addItems(category_names)
            
            current_category = self.task_data.get('category', 'General')
            if current_category in category_names:
                self.category_combo.setCurrentText(current_category)
            elif "General" in category_names:
                self.category_combo.setCurrentText("General")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load categories: {e}")
            self.category_combo.addItem("General")

    def _select_deadline(self):
        dialog = DeadlineCalendarDialog(self.current_qdate_deadline, self)
        
        if dialog.exec():
            selected_qdate = dialog.get_selected_date()
            if selected_qdate.isValid():
                self.current_qdate_deadline = selected_qdate
                self.deadline_label.setText(selected_qdate.toString("yyyy-MM-dd"))
            else: # Reset was hit
                self.current_qdate_deadline = None
                self.deadline_label.setText("No Deadline")

    def save_details(self):
        new_desc = self.desc_entry.text().strip()
        if not new_desc:
            QMessageBox.warning(self, "Input Error", "Description cannot be empty.")
            return

        deadline_str = self.current_qdate_deadline.toString("yyyy-MM-dd") if self.current_qdate_deadline else None
        show_mode = 'always_pending' if self.show_always_check.isChecked() else 'auto'
        category = self.category_combo.currentText()
        if not category: 
            category = "General"
            
        tags_str = self.tags_entry.text().strip()
        tag_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

        try:
            conn = connect_db() 
            try:
                if self.is_new_task:
                    new_task_id = str(uuid.uuid4()) 
                    new_task_data = {
                        'id': new_task_id,
                        'description': new_desc,
                        'status': 'pending',
                        'date_added': datetime.now().strftime("%Y-%m-%d"),
                        'deadline': deadline_str,
                        'priority': self.priority_combo.currentText(),
                        'category': category,
                        'notes': self.notes_editor.toPlainText(),
                        'show_mode': show_mode,
                        'parent_task_id': None 
                    }
                    add_task(new_task_data) 

                    if tag_list:
                        update_tags_for_task(new_task_id, tag_list, db_conn=conn)
                    
                    if self.temp_show_dates:
                        for q_date in self.temp_show_dates:
                            add_task_show_date(new_task_id, q_date.toString("yyyy-MM-dd"), db_conn=conn)
                else:
                    update_task_details(
                        self.task_id, new_desc, self.priority_combo.currentText(),
                        category, 
                        deadline_str, self.notes_editor.toPlainText(),
                        show_mode
                    )
                    
                    update_tags_for_task(self.task_id, tag_list, db_conn=conn)

                conn.commit() 
            except Exception as e:
                conn.rollback()
                raise e 
            finally:
                conn.close()

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
            self.task_saved.emit() # Emit signal in case dates were changed

    # --- METHODS FOR SUB-TASKS ---

    def _load_sub_tasks(self):
        if not hasattr(self, 'sub_task_list_widget'):
            return 
            
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
                item.setData(Qt.ItemDataRole.UserRole, sub_task)
                self.sub_task_list_widget.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load sub-tasks: {e}")

    def _add_sub_task(self):
        desc, ok = QInputDialog.getText(self, "Add Sub-task", "Enter new sub-task description:")
        if ok and desc:
            try:
                new_sub_task_data = {
                    'id': str(uuid.uuid4()),
                    'description': desc,
                    'status': 'pending',
                    'date_added': datetime.now().strftime("%Y-%m-%d"),
                    'deadline': None, 
                    'priority': 'Medium', 
                    'category': self.task_data.get('category', 'General'), 
                    'notes': "",
                    'show_mode': 'auto',
                    'parent_task_id': self.task_id 
                }
                add_task(new_sub_task_data)
                self._load_sub_tasks() 
                self.task_saved.emit() 
            except Exception as e:
                 QMessageBox.critical(self, "Database Error", f"Failed to add sub-task: {e}")

    def _edit_sub_task(self):
        current_item = self.sub_task_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Edit Error", "Please select a sub-task to edit.")
            return
            
        sub_task_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        dialog = TaskDetailsDialog(sub_task_data, self, is_new_task=False)
        dialog.task_saved.connect(self._load_sub_tasks)
        dialog.task_saved.connect(self.task_saved)
        dialog.exec()

    def _delete_sub_task(self):
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
                delete_task(sub_task_id) 
                self._load_sub_tasks() 
                self.task_saved.emit() 
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete sub-task: {e}")

    # --- NEW: METHODS FOR DEPENDENCIES ---

    def _load_dependencies(self):
        """ Clears and re-loads the dependency list widget. """
        if not hasattr(self, 'dependency_list_widget'):
            return 
            
        self.dependency_list_widget.clear()
        try:
            dependencies = get_task_dependencies(self.task_id)
            if not dependencies:
                item = QListWidgetItem("No prerequisites.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray"))
                self.dependency_list_widget.addItem(item)
                return

            for task in dependencies:
                status_icon = "✓" if task['status'] == 'completed' else "☐"
                item_text = f"{status_icon} {task['description']}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, task) # Store task dict
                self.dependency_list_widget.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load dependencies: {e}")

    def _add_dependency(self):
        """ Opens a dialog to select a task to depend on. """
        dialog = SelectDependencyDialog(self.task_id, self)
        if dialog.exec():
            selected_task_id = dialog.get_selected_task_id()
            if selected_task_id:
                try:
                    add_task_dependency(self.task_id, selected_task_id)
                    self._load_dependencies() # Refresh the list
                    self.task_saved.emit() # Tell main tab to refresh
                except Exception as e:
                    QMessageBox.critical(self, "Database Error", f"Failed to add dependency: {e}")

    def _remove_dependency(self):
        """ Removes the selected dependency. """
        current_item = self.dependency_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Remove Error", "Please select a dependency to remove.")
            return

        dependency_task = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, 'Confirm Remove',
                                   f"Remove dependency on task:\n'{dependency_task['description']}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                remove_task_dependency(self.task_id, dependency_task['id'])
                self._load_dependencies() # Refresh the list
                self.task_saved.emit() # Tell main tab to refresh
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to remove dependency: {e}")
    # --- END NEW ---


# --- Manage Show Dates Dialog ---
class ManageShowDatesDialog(QDialog):
    # ... (omitted, no changes) ...
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


# --- NEW Reusable Deadline Dialog (Change 3) ---
class DeadlineCalendarDialog(QDialog):
    # ... (omitted, no changes) ...
    def __init__(self, current_qdate, parent=None):
        """
        A consolidated dialog for selecting a task deadline.
        current_qdate (QDate): The date to pre-select, or None.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Deadline")
        layout = QVBoxLayout(self)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        
        if current_qdate and current_qdate.isValid():
             self.calendar.setSelectedDate(current_qdate)
        else:
             self.calendar.setSelectedDate(QDate.currentDate()) 
        layout.addWidget(self.calendar)

        # Add Ok, Cancel, and Reset buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                      QDialogButtonBox.StandardButton.Cancel |
                                      QDialogButtonBox.StandardButton.Reset) 
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        # Reset button clears the date selection (sets it to invalid)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: self.calendar.setSelectedDate(QDate())) 

        layout.addWidget(button_box)

    def get_selected_date(self):
        """Returns the selected QDate (which may be invalid if Reset was hit)."""
        return self.calendar.selectedDate()
        
# --- NEW: Select Dependency Dialog ---
class SelectDependencyDialog(QDialog):
    def __init__(self, current_task_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Prerequisite Task")
        self.setMinimumWidth(400)
        self.selected_task_id = None
        self.current_task_id = current_task_id
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("Select a task that must be completed *before* this one:"))
        
        self.task_list_widget = QListWidget()
        self.layout.addWidget(self.task_list_widget, 1) # Give it stretch
        
        self._populate_tasks()
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
    def _populate_tasks(self):
        """ Loads all *other* pending tasks into the list. """
        self.task_list_widget.clear()
        try:
            # Get all pending tasks (parents and sub-tasks)
            tasks = get_all_pending_tasks() 
            if not tasks:
                item = QListWidgetItem("No other pending tasks available.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.task_list_widget.addItem(item)
                return
                
            task_map = {t['id']: t for t in tasks}
            
            for task in tasks:
                # --- Prevent circular dependencies ---
                if task['id'] == self.current_task_id:
                    continue # Can't depend on itself
                if task.get('parent_task_id') == self.current_task_id:
                    continue # Can't depend on one of its own sub-tasks
                # --- End Prevent ---

                desc = task['description']
                parent_id = task.get('parent_task_id')
                
                if parent_id and parent_id in task_map:
                    parent_name = task_map[parent_id].get('description', 'Parent')
                    display_text = f"{parent_name}: {desc}"
                else:
                    display_text = desc
                    
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, task['id']) # Store task ID
                self.task_list_widget.addItem(item)
                
        except Exception as e:
            print(f"Error populating dependency task dialog: {e}")
            self.task_list_widget.addItem("Error loading tasks.")

    def _on_accept(self):
        """ User chose to add the selected dependency. """
        current_item = self.task_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "No Selection", "Please select a task from the list.")
            return
            
        self.selected_task_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        
    def get_selected_task_id(self):
        """ Called by the parent to get the result. """
        return self.selected_task_id
# --- END NEW ---