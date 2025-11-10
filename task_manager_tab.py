import uuid
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QScrollArea, QFrame, QMessageBox, QDialog,
    QCalendarWidget, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import (
    Signal, Qt, QDate
)

# --- Import from our new structure ---
from app.core.database import (
    get_tasks, add_task, update_task_status, delete_task, get_all_tasks,
    get_sub_tasks, get_pending_subtask_count,
    get_categories # <-- NEW IMPORT
)
from app.widgets.task_widgets import TaskWidget
from app.widgets.dialogs_task import TaskDetailsDialog
# --- This is the file. There should be NO MORE IMPORTS after this line ---

# --- Task Manager Tab Widget ---
class TaskManagerTab(QWidget):
    """
    A self-contained widget for the "Task Manager" tab.
    Manages its own UI, filters, and task list.
    """
    # Signal emitted when the task list is changed (task added, deleted, status changed)
    task_list_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Member Variables ---
        self.selected_deadline = None
        self.view_mode = "pending" # "pending" or "completed"

        # --- Setup UI ---
        self._setup_ui()

        # --- Load Initial Data ---
        self._load_categories() # <-- Now loads *all* category boxes
        self._display_tasks()

    def _setup_ui(self):
        """Builds the UI for this tab."""
        layout = QVBoxLayout(self)
        
        # --- Input Layout ---
        input_layout = QHBoxLayout()
        self.task_entry = QLineEdit()
        self.task_entry.setPlaceholderText("Enter a new task... (or leave blank for details)")
        self.task_entry.returnPressed.connect(self._add_task)
        input_layout.addWidget(self.task_entry, 1)

        self.deadline_button = QPushButton("No Deadline")
        self.deadline_button.clicked.connect(self._open_deadline_calendar)
        input_layout.addWidget(self.deadline_button)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("Medium")
        input_layout.addWidget(self.priority_combo)

        # --- MODIFIED: Category QLineEdit replaced with QComboBox ---
        self.category_combo = QComboBox()
        self.category_combo.setFixedWidth(100)
        input_layout.addWidget(self.category_combo)
        # --- END MODIFIED ---

        add_button = QPushButton("Add Task")
        add_button.clicked.connect(self._add_task)
        input_layout.addWidget(add_button)
        layout.addLayout(input_layout)
        
        # --- Filter Layout ---
        filter_layout = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search tasks...")
        self.search_entry.textChanged.connect(self._display_tasks)
        filter_layout.addWidget(self.search_entry, 1)

        self.category_filter_combo = QComboBox()
        self.category_filter_combo.addItem("All Categories")
        self.category_filter_combo.currentTextChanged.connect(self._display_tasks)
        filter_layout.addWidget(self.category_filter_combo)

        self.toggle_view_button = QPushButton("View Completed")
        self.toggle_view_button.clicked.connect(self._toggle_view)
        filter_layout.addWidget(self.toggle_view_button)
        layout.addLayout(filter_layout)
        
        # --- Task List Tree Widget (REPLACED) ---
        self.task_tree_widget = QTreeWidget()
        self.task_tree_widget.setHeaderHidden(True) # No header
        layout.addWidget(self.task_tree_widget, 1) # Give tree max space

    def _add_task(self):
        description = self.task_entry.text().strip()
        
        if not description:
            # Open the full details dialog for a new task
            dialog = TaskDetailsDialog(task_data=None, parent=self, is_new_task=True)
            # Connect the dialog's signal to *this* widget's update signal
            dialog.task_saved.connect(self.task_list_updated)
            dialog.exec()
            return

        # Simple task creation from the main bar
        # --- MODIFIED: Read from category_combo ---
        category = self.category_combo.currentText()
        if not category:
            category = "General" # Safeguard
        # --- END MODIFIED ---
        priority = self.priority_combo.currentText()
        deadline_str = self.selected_deadline.toString("yyyy-MM-dd") if self.selected_deadline else None
        
        new_task = {
            "id": str(uuid.uuid4()),
            "description": description,
            "date_added": datetime.now().strftime("%Y-%m-%d"),
            "deadline": deadline_str,
            "priority": priority,
            "category": category,
            "notes": "",
            "show_mode": "auto",
            "parent_task_id": None # <-- Explicitly set as a top-level task
        }

        try:
            add_task(new_task)
            # Reset input fields
            self.task_entry.clear()
            # --- MODIFIED: Reset category_combo ---
            self.category_combo.setCurrentText("General")
            # --- END MODIFIED ---
            self.priority_combo.setCurrentText("Medium")
            self.selected_deadline = None
            self.deadline_button.setText("No Deadline")
            
            # Refresh UI
            # self._load_categories() # No longer needed here, _display_tasks does it
            if self.view_mode == "completed":
                self._toggle_view()
            else:
                 self._display_tasks()
            
            # Emit signal that data has changed
            self.task_list_updated.emit()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to add task: {e}")

    def _display_tasks(self):
        # Clear existing task widgets
        self.task_tree_widget.clear()
        
        main_window = self.window() # Get main window to connect info button

        if self.view_mode == "pending":
            # get_tasks() now only returns top-level tasks
            tasks_to_show = get_tasks('pending')
            
            # Sort by priority, then by deadline (tasks without deadline last)
            priority_map = {"High": 0, "Medium": 1, "Low": 2}
            tasks_to_show.sort(key=lambda t: (
                priority_map.get(t.get('priority', 'Medium'), 1), 
                t.get('deadline') is None,
                t.get('deadline') or ''
            ))
            
            # Apply search filter
            search_term = self.search_entry.text().lower()
            if search_term:
                tasks_to_show = [t for t in tasks_to_show if search_term in t.get('description', '').lower()]
            
            # Apply category filter
            selected_category = self.category_filter_combo.currentText()
            if selected_category != "All Categories":
                tasks_to_show = [t for t in tasks_to_show if t.get('category') == selected_category]

            # --- Create and add TaskWidget for each task ---
            for task in tasks_to_show:
                task_widget = TaskWidget(task)
                task_widget.status_changed.connect(self._handle_task_status_change)
                task_widget.delete_requested.connect(self._handle_task_delete)
                
                if hasattr(main_window, '_open_task_details_dialog'):
                    task_widget.info_requested.connect(main_window._open_task_details_dialog)
                
                # Create a top-level tree item
                parent_tree_item = QTreeWidgetItem(self.task_tree_widget)
                self.task_tree_widget.setItemWidget(parent_tree_item, 0, task_widget)
                
                # --- NEW: Check for and add sub-tasks ---
                # We get all sub-tasks so we can see completed ones
                sub_tasks = get_sub_tasks(task['id'], status="all")
                
                if sub_tasks:
                    # Sort sub-tasks as well
                    sub_tasks.sort(key=lambda t: (
                         t.get('status') == 'completed', # Show pending first
                         priority_map.get(t.get('priority', 'Medium'), 1)
                    ))
                
                    for sub_task in sub_tasks:
                        sub_task_widget = TaskWidget(sub_task)
                        sub_task_widget.status_changed.connect(self._handle_task_status_change)
                        sub_task_widget.delete_requested.connect(self._handle_task_delete)
                        
                        if hasattr(main_window, '_open_task_details_dialog'):
                            sub_task_widget.info_requested.connect(main_window._open_task_details_dialog)
                            
                        # Create a child tree item
                        child_tree_item = QTreeWidgetItem(parent_tree_item)
                        self.task_tree_widget.setItemWidget(child_tree_item, 0, sub_task_widget)

        elif self.view_mode == "completed":
            completed_tasks = get_tasks('completed')
            completed_tasks.sort(key=lambda t: t.get('date_completed', ''), reverse=True)
            for task in completed_tasks:
                 # Just show a simple label for completed tasks
                 label_text = f"[{task.get('category', 'G')[:1]}] {task.get('description','')} (Completed: {task.get('date_completed', 'NA')})"
                 completed_label = QLabel(label_text)
                 completed_label.setStyleSheet("color: gray; padding: 5px; background-color: #343638; border-radius: 4px;") 
                 
                 # Add as a top-level item in the tree
                 item = QTreeWidgetItem(self.task_tree_widget)
                 self.task_tree_widget.setItemWidget(item, 0, completed_label)

    def _load_categories(self):
        """
        MODIFIED: This function now loads categories from the DB
        and populates *both* the filter and the 'add task' combo boxes.
        """
        # --- Store current selections ---
        current_filter_selection = self.category_filter_combo.currentText()
        current_add_selection = self.category_combo.currentText()
        
        # --- Block Signals ---
        self.category_filter_combo.blockSignals(True) 
        self.category_combo.blockSignals(True)
        
        # --- Clear ---
        self.category_filter_combo.clear()
        self.category_combo.clear()
        
        # --- Repopulate ---
        self.category_filter_combo.addItem("All Categories")
        
        try:
            categories = get_categories() # Get from new DB table
            category_names = [cat['name'] for cat in categories]
            
            # Add to both boxes
            self.category_filter_combo.addItems(category_names)
            self.category_combo.addItems(category_names)
            
            # --- Restore selections ---
            index_filter = self.category_filter_combo.findText(current_filter_selection)
            if index_filter != -1:
                self.category_filter_combo.setCurrentIndex(index_filter)
            else:
                 self.category_filter_combo.setCurrentIndex(0) 
            
            index_add = self.category_combo.findText(current_add_selection)
            if index_add != -1:
                self.category_combo.setCurrentIndex(index_add)
            elif self.category_combo.findText("General") != -1:
                self.category_combo.setCurrentText("General")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading categories: {e}")
            if self.category_filter_combo.count() == 0:
                 self.category_filter_combo.addItem("All Categories")
            if self.category_combo.count() == 0:
                 self.category_combo.addItem("General")
                 
        finally:
            # --- Unblock Signals ---
            self.category_filter_combo.blockSignals(False) 
            self.category_combo.blockSignals(False)

    def _toggle_view(self):
        if self.view_mode == "pending":
            self.view_mode = "completed"
            self.toggle_view_button.setText("View Pending")
        else:
            self.view_mode = "pending"
            self.toggle_view_button.setText("View Completed")
        self._display_tasks() # Refresh the list

    def _handle_task_status_change(self, task_id, is_checked):
        
        # --- NEW LOGIC: Check for pending sub-tasks ---
        if is_checked:
            try:
                pending_count = get_pending_subtask_count(task_id)
                if pending_count > 0:
                    QMessageBox.warning(self, "Task Not Empty",
                                        f"You cannot complete this task.\nIt still has {pending_count} pending sub-task(s).")
                    # Refresh the whole tree. This is the simplest way
                    # to reset the checkbox to its original state.
                    self._display_tasks()
                    return # Stop processing
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not check for sub-tasks: {e}")
                return
        # --- END OF NEW LOGIC ---

        new_status = 'completed' if is_checked else 'pending'
        date_completed = datetime.now().strftime("%Y-%m-%d") if is_checked else None
        
        try:
            update_task_status(task_id, new_status, date_completed)
            
            # Instead of complex logic to find/remove the item,
            # just refresh the entire display. It's cleaner.
            self._display_tasks()
            
            # Emit signal that data has changed
            self.task_list_updated.emit()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update task status: {e}")
            self._display_tasks() # Full refresh on error

    def _handle_task_delete(self, task_id):
        # We don't need to find the widget anymore, as we'll refresh the list.
        # But we can still get the description for the dialog if we want.
        # For simplicity, we'll use a generic message.
        # (We could also query the DB for the task description first)
        
        reply = QMessageBox.question(self, 'Confirm Delete',
                                       f"Are you sure you want to delete this task?\n(This will also delete all its sub-tasks)",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_task(task_id) # This will cascade-delete sub-tasks
                
                # Refresh the entire display
                self._display_tasks() 
                
                # Emit signal that data has changed
                self.task_list_updated.emit()

            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete task: {e}")

    def _open_deadline_calendar(self):
        # This dialog is simple enough to keep inside this class
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Deadline")
        layout = QVBoxLayout(dialog)

        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        if self.selected_deadline: 
             calendar.setSelectedDate(self.selected_deadline)
        else:
             calendar.setSelectedDate(QDate.currentDate()) 

        layout.addWidget(calendar)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                      QDialogButtonBox.StandardButton.Cancel |
                                      QDialogButtonBox.StandardButton.Reset) 
        
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        # Reset button clears the date selection
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: calendar.setSelectedDate(QDate())) 

        layout.addWidget(button_box)

        if dialog.exec(): 
            selected_qdate = calendar.selectedDate()
            if selected_qdate.isValid():
                self.selected_deadline = selected_qdate 
                self.deadline_button.setText(selected_qdate.toString("yyyy-MM-dd"))
            else: # Reset was hit
                self.selected_deadline = None
                self.deadline_button.setText("No Deadline")
        elif self.selected_deadline is None: 
             # User cancelled, but had no deadline selected
             self.deadline_button.setText("No Deadline")