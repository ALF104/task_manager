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
    get_categories, 
    get_task_templates, instantiate_task_template,
    get_pending_dependency_count,
    get_all_unique_tags # <-- NEW IMPORT
)
from app.widgets.task_widgets import TaskWidget
from app.widgets.dialogs_task import TaskDetailsDialog, DeadlineCalendarDialog
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
        self._load_categories() 
        self._load_tags() # <-- NEW: Load tags
        self._load_templates() 
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

        self.template_combo = QComboBox()
        self.template_combo.setFixedWidth(120)
        self.template_combo.addItem("— Use Template —")
        self.template_combo.currentIndexChanged.connect(self._on_template_selected) 
        input_layout.addWidget(self.template_combo)

        self.deadline_button = QPushButton("No Deadline")
        self.deadline_button.clicked.connect(self._open_deadline_calendar)
        input_layout.addWidget(self.deadline_button)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("Medium")
        input_layout.addWidget(self.priority_combo)

        self.category_combo = QComboBox()
        self.category_combo.setFixedWidth(100)
        input_layout.addWidget(self.category_combo)

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
        
        # --- NEW: Tag Filter ---
        self.tag_filter_combo = QComboBox()
        self.tag_filter_combo.addItem("All Tags")
        self.tag_filter_combo.currentTextChanged.connect(self._display_tasks)
        filter_layout.addWidget(self.tag_filter_combo)
        # --- END NEW ---

        self.toggle_view_button = QPushButton("View Completed")
        self.toggle_view_button.clicked.connect(self._toggle_view)
        filter_layout.addWidget(self.toggle_view_button)
        layout.addLayout(filter_layout)
        
        # --- Task List Tree Widget (REPLACED) ---
        self.task_tree_widget = QTreeWidget()
        self.task_tree_widget.setHeaderHidden(True) # No header
        layout.addWidget(self.task_tree_widget, 1) # Give tree max space

    def _load_templates(self):
        """Loads task templates into the combo box."""
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("— Use Template —")
        
        try:
            templates = get_task_templates()
            for template in templates:
                self.template_combo.addItem(template['name'], template['id'])
        except Exception as e:
            print(f"Error loading templates: {e}")
            
        self.template_combo.blockSignals(False)
        
    def _on_template_selected(self, index):
        """Triggers task creation if a template is selected."""
        if index > 0:
            self.template_combo.blockSignals(True)
            try:
                self._add_task() 
            finally:
                self.template_combo.blockSignals(False)


    def _add_task(self):
        description = self.task_entry.text().strip()
        
        selected_template_index = self.template_combo.currentIndex()
        
        if selected_template_index > 0:
            # --- Instantiating from a Template ---
            template_id = self.template_combo.currentData()
            template_name = self.template_combo.currentText()
            try:
                instantiate_task_template(template_id)
                QMessageBox.information(self, "Template Created", 
                                        f"Successfully created task(s) from template: '{template_name}'.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create tasks from template: {e}")
                
            finally:
                self._reset_and_refresh_ui()
                return

        elif not description:
            # Open the full details dialog for a new task
            dialog = TaskDetailsDialog(task_data=None, parent=self, is_new_task=True)
            dialog.task_saved.connect(self.task_list_updated)
            dialog.exec()
            return

        # Simple task creation from the main bar
        category = self.category_combo.currentText()
        if not category:
            category = "General" # Safeguard
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
            "parent_task_id": None 
        }

        try:
            add_task(new_task)
            self._reset_and_refresh_ui()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to add task: {e}")


    def _reset_and_refresh_ui(self):
        """Helper to reset inputs and refresh display after saving/creation."""
        self.task_entry.clear()
        self.category_combo.setCurrentText("General")
        self.priority_combo.setCurrentText("Medium")
        self.selected_deadline = None
        self.deadline_button.setText("No Deadline")
        
        self.template_combo.blockSignals(True)
        self.template_combo.setCurrentIndex(0) # Reset template selector
        self.template_combo.blockSignals(False)
        
        if self.view_mode == "completed":
            self._toggle_view()
        else:
             self._display_tasks()
        
        self.task_list_updated.emit() # This will trigger _load_tags in main

    def _display_tasks(self):
        # Clear existing task widgets
        self.task_tree_widget.clear()
        
        main_window = self.window() # Get main window to connect info button

        if self.view_mode == "pending":
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

            # --- NEW: Apply Tag Filter ---
            selected_tag = self.tag_filter_combo.currentText()
            if selected_tag != "All Tags":
                # Filter tasks where the selected tag is in their comma-separated 'tags' string
                tasks_to_show = [
                    t for t in tasks_to_show 
                    if t.get('tags') and selected_tag in [tag.strip() for tag in t['tags'].split(',')]
                ]
            # --- END NEW ---

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
                 label_text = f"[{task.get('category', 'G')[:1]}] {task.get('description','')} (Completed: {task.get('date_completed', 'NA')})"
                 completed_label = QLabel(label_text)
                 completed_label.setStyleSheet("color: gray; padding: 5px; background-color: #343638; border-radius: 4px;") 
                 
                 item = QTreeWidgetItem(self.task_tree_widget)
                 self.task_tree_widget.setItemWidget(item, 0, completed_label)

    def _load_categories(self):
        """
        MODIFIED: This function now loads categories from the DB
        and populates *both* the filter and the 'add task' combo boxes.
        """
        current_filter_selection = self.category_filter_combo.currentText()
        current_add_selection = self.category_combo.currentText()
        
        self.category_filter_combo.blockSignals(True) 
        self.category_combo.blockSignals(True)
        
        self.category_filter_combo.clear()
        self.category_combo.clear()
        
        self.category_filter_combo.addItem("All Categories")
        
        try:
            categories = get_categories() 
            category_names = [cat['name'] for cat in categories]
            
            self.category_filter_combo.addItems(category_names)
            self.category_combo.addItems(category_names)
            
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
            self.category_filter_combo.blockSignals(False) 
            self.category_combo.blockSignals(False)
            
    # --- NEW: Load Tags ---
    def _load_tags(self):
        """Loads all unique tags into the tag filter combo box."""
        current_selection = self.tag_filter_combo.currentText()
        self.tag_filter_combo.blockSignals(True)
        
        self.tag_filter_combo.clear()
        self.tag_filter_combo.addItem("All Tags")
        
        try:
            tags = get_all_unique_tags()
            self.tag_filter_combo.addItems(tags)
            
            index = self.tag_filter_combo.findText(current_selection)
            if index != -1:
                self.tag_filter_combo.setCurrentIndex(index)
            else:
                self.tag_filter_combo.setCurrentIndex(0)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading tags: {e}")
            if self.tag_filter_combo.count() == 0:
                self.tag_filter_combo.addItem("All Tags")
        
        finally:
            self.tag_filter_combo.blockSignals(False)
    # --- END NEW ---

    def _toggle_view(self):
        if self.view_mode == "pending":
            self.view_mode = "completed"
            self.toggle_view_button.setText("View Pending")
        else:
            self.view_mode = "pending"
            self.toggle_view_button.setText("View Completed")
        self._display_tasks() # Refresh the list

    def _handle_task_status_change(self, task_id, is_checked):
        
        if is_checked:
            try:
                # Check 1: Sub-tasks
                pending_sub_count = get_pending_subtask_count(task_id)
                if pending_sub_count > 0:
                    QMessageBox.warning(self, "Task Not Empty",
                                        f"You cannot complete this task.\nIt still has {pending_sub_count} pending sub-task(s).")
                    self._display_tasks() # Revert checkbox
                    return # Stop processing
                    
                # Check 2: Dependencies
                pending_dep_count = get_pending_dependency_count(task_id)
                if pending_dep_count > 0:
                    QMessageBox.warning(self, "Task Blocked",
                                        f"This task is blocked by {pending_dep_count} pending prerequisite(s).\n"
                                        "Complete the other task(s) first.")
                    self._display_tasks() # Revert checkbox
                    return # Stop processing
                    
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not check for sub-tasks or dependencies: {e}")
                return

        new_status = 'completed' if is_checked else 'pending'
        date_completed = datetime.now().strftime("%Y-%m-%d") if is_checked else None
        
        try:
            update_task_status(task_id, new_status, date_completed)
            self._display_tasks()
            self.task_list_updated.emit()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update task status: {e}")
            self._display_tasks() # Full refresh on error

    def _handle_task_delete(self, task_id):
        
        reply = QMessageBox.question(self, 'Confirm Delete',
                                       f"Are you sure you want to delete this task?\n(This will also delete all its sub-tasks)",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_task(task_id) # This will cascade-delete sub-tasks
                self._display_tasks() 
                self.task_list_updated.emit()

            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete task: {e}")

    def _open_deadline_calendar(self):
        dialog = DeadlineCalendarDialog(self.selected_deadline, self)
        
        if dialog.exec(): 
            selected_qdate = dialog.get_selected_date()
            if selected_qdate.isValid():
                self.selected_deadline = selected_qdate 
                self.deadline_button.setText(selected_qdate.toString("yyyy-MM-dd"))
            else: # Reset was hit
                self.selected_deadline = None
                self.deadline_button.setText("No Deadline")
        elif self.selected_deadline is None: 
             self.deadline_button.setText("No Deadline")