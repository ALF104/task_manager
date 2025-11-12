import uuid
import sys
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
    QTextEdit, QInputDialog, QSpinBox,
    QMenu # <-- NEW IMPORT
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
    get_schedule_events_for_date, get_calendar_events_for_date, get_daily_note,
    get_all_pending_tasks, get_task_by_id, get_all_tasks, # <-- Added get_all_tasks
    get_focus_logs_for_date, update_focus_log_notes,
    get_task_templates, save_task_template, delete_task_template, # <-- NEW IMPORTS
    get_template_tasks, get_categories, # <-- NEW IMPORTS
    add_manual_focus_log # <-- NEW IMPORT
)
# We need this for the "Manage Automations" button
from app.widgets.dialogs_automation import ManageAutomationsDialog
try:
    from app.widgets.dialogs_stats import StatisticsDialog
except ImportError:
    print("Could not import StatisticsDialog. Make sure pyside6-addons is installed.")
    StatisticsDialog = None # Set to None as a safeguard
    
# --- NEW: Import for Category Dialog ---
from app.widgets.dialogs_category import ManageCategoriesDialog
# --- END NEW ---

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


# --- Schedule Settings Dialog (NEW) ---
class ScheduleSettingsDialog(QDialog):
    """
    A separate dialog just for managing Daily Schedule settings.
    """
    schedule_settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule View Settings")

        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.start_hour_spin = QSpinBox()
        self.start_hour_spin.setRange(0, 12)
        self.start_hour_spin.setValue(int(get_app_state('schedule_start_hour') or 6))

        self.end_hour_spin = QSpinBox()
        self.end_hour_spin.setRange(13, 23)
        self.end_hour_spin.setValue(int(get_app_state('schedule_end_hour') or 23))

        form_layout.addRow("Schedule View Start Hour (0-12):", self.start_hour_spin)
        form_layout.addRow("Schedule View End Hour (13-23):", self.end_hour_spin)

        self.layout.addLayout(form_layout)
        self.layout.addWidget(QLabel("Note: End hour must be greater than start hour."))

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._save_schedule_settings)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _save_schedule_settings(self):
        """Saves schedule settings to the database."""
        start_hour = self.start_hour_spin.value()
        end_hour = self.end_hour_spin.value()

        if end_hour <= start_hour:
            QMessageBox.warning(self, "Input Error", "End hour must be after start hour.")
            return

        try:
            set_app_state('schedule_start_hour', str(start_hour))
            set_app_state('schedule_end_hour', str(end_hour))

            self.schedule_settings_changed.emit()
            QMessageBox.information(self, "Saved", "Schedule settings saved!")
            self.accept() # Close the dialog

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save schedule settings: {e}")
# --- END Schedule Settings Dialog ---


# --- Manage Task Templates Dialog (NEW) ---
class ManageTaskTemplatesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Task Templates")
        self.setMinimumSize(600, 500)

        self.layout = QHBoxLayout(self)

        # Left Side: List of Templates
        list_group = QGroupBox("Saved Templates")
        list_layout = QVBoxLayout(list_group)
        
        self.template_list_widget = QListWidget()
        self.template_list_widget.itemSelectionChanged.connect(self._load_selected_template)
        list_layout.addWidget(self.template_list_widget)
        
        button_layout = QHBoxLayout()
        add_btn = QPushButton("New")
        add_btn.clicked.connect(self._new_template)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_template)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_template)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        list_layout.addLayout(button_layout)
        self.layout.addWidget(list_group, 1)

        # Right Side: Template Editor
        self.editor_widget = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_widget)
        self.editor_widget.setEnabled(False) # Start disabled
        self.layout.addWidget(self.editor_widget, 2)
        
        self._setup_editor_ui() # Build the editor fields
        self._load_templates()

    def _setup_editor_ui(self):
        """Sets up the detailed editor fields."""
        
        # --- Template Metadata ---
        meta_group = QGroupBox("Template Details")
        meta_layout = QFormLayout(meta_group)
        self.template_id = None
        
        self.template_name_entry = QLineEdit()
        self.template_name_entry.setPlaceholderText("e.g., 'Weekly Planning Routine'")
        meta_layout.addRow("Template Name:", self.template_name_entry)
        
        self.template_desc_entry = QPlainTextEdit()
        self.template_desc_entry.setFixedHeight(50)
        self.template_desc_entry.setPlaceholderText("Optional description...")
        meta_layout.addRow("Description:", self.template_desc_entry)
        
        # --- FIX: Ensure self.category_combo is correctly defined as QComboBox ---
        self.category_combo = QComboBox() 
        self._load_categories()
        meta_layout.addRow("Default Category:", self.category_combo)
        # --- END FIX ---
        
        self.editor_layout.addWidget(meta_group)
        
        # --- Template Tasks (Sub-tasks) ---
        tasks_group = QGroupBox("Tasks in Template (Parent task is first)")
        tasks_layout = QVBoxLayout(tasks_group)
        
        self.template_tasks_list = QListWidget()
        tasks_layout.addWidget(self.template_tasks_list)
        
        task_btn_layout = QHBoxLayout()
        
        # --- FIX: Connect buttons to methods ---
        self.add_task_btn = QPushButton("Add Task/Step")
        self.add_task_btn.clicked.connect(self._add_template_task)
        self.edit_task_btn = QPushButton("Edit Selected")
        self.edit_task_btn.clicked.connect(self._edit_template_task)
        self.remove_task_btn = QPushButton("Remove Selected")
        self.remove_task_btn.clicked.connect(self._remove_template_task)
        
        task_btn_layout.addWidget(self.add_task_btn)
        task_btn_layout.addWidget(self.edit_task_btn)
        task_btn_layout.addWidget(self.remove_task_btn)
        # --- END FIX ---
        
        tasks_layout.addLayout(task_btn_layout)
        self.editor_layout.addWidget(tasks_group, 1) # Tasks list gets vertical stretch
        
        # --- Save/Cancel Buttons ---
        self.save_button = QPushButton("Save Template")
        self.save_button.clicked.connect(self._save_template)
        self.editor_layout.addWidget(self.save_button)
    
    def _load_categories(self):
        """Loads categories into the combo box for the editor."""
        try:
            self.category_combo.clear()
            categories = get_categories()
            category_names = [cat['name'] for cat in categories]
            self.category_combo.addItems(category_names)
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not load categories: {e}")
             self.category_combo.addItem("General")

    def _load_templates(self):
        """Loads all saved templates into the list widget."""
        self.template_list_widget.clear()
        try:
            templates = get_task_templates()
            if not templates:
                item = QListWidgetItem("No templates saved.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray")) 
                self.template_list_widget.addItem(item)
                self._new_template() # Open a fresh editor for a new template
                return
            
            for template in templates:
                item = QListWidgetItem(template['name'])
                item.setData(Qt.ItemDataRole.UserRole, template) # Store the whole dict
                self.template_list_widget.addItem(item)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load templates: {e}")

    def _load_selected_template(self):
        """Loads the details of the selected template into the editor."""
        current_item = self.template_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            self.editor_widget.setEnabled(False)
            return
            
        template_data = current_item.data(Qt.ItemDataRole.UserRole)
        self.template_id = template_data['id']
        
        self.template_name_entry.setText(template_data['name'])
        self.template_desc_entry.setPlainText(template_data.get('description', ''))
        self.category_combo.setCurrentText(template_data.get('default_category', 'General'))
        
        self._load_template_tasks(self.template_id)
        self.editor_widget.setEnabled(True)
        self.save_button.setText("Save Changes")

    def _load_template_tasks(self, template_id):
        """Loads the tasks/steps for the current template into the sub-list."""
        self.template_tasks_list.clear()
        try:
            tasks = get_template_tasks(template_id)
            if not tasks:
                item = QListWidgetItem("Template has no steps. Add the main task first.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.template_tasks_list.addItem(item)
                return
                
            for task in tasks:
                status_icon = "T" if not task['is_sub_task'] else "—" # T for Top-level/Parent
                item_text = f"[{status_icon}] {task['description']} (P: {task['priority']})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, task) # Store the task dict
                self.template_tasks_list.addItem(item)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load template tasks: {e}")

    def _new_template(self):
        """Clears the editor for creating a brand new template."""
        self.template_id = None
        self.template_name_entry.clear()
        self.template_desc_entry.clear()
        self.category_combo.setCurrentText(self.category_combo.itemText(0))
        self.template_tasks_list.clear()
        self.editor_widget.setEnabled(True)
        self.save_button.setText("Create Template")
        self.template_list_widget.clearSelection()
        
    def _edit_template(self):
        """Triggered by the edit button, same as list selection for now."""
        self._load_selected_template()

    def _delete_template(self):
        """Deletes the selected template after confirmation."""
        current_item = self.template_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "No Selection", "Please select a template to delete.")
            return

        template_data = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Are you sure you want to delete the template '{template_data['name']}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_task_template(template_data['id'])
                self._load_templates()
                self._new_template() # Reset editor
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not delete template: {e}")

    def _save_template(self):
        """Gathers data from the editor and saves it to the database."""
        name = self.template_name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Template name cannot be empty.")
            return
            
        # Get tasks from list widget
        template_tasks_list = []
        for i in range(self.template_tasks_list.count()):
            item = self.template_tasks_list.item(i)
            template_tasks_list.append(item.data(Qt.ItemDataRole.UserRole))

        # Must have at least one task (the parent)
        if not template_tasks_list:
             QMessageBox.warning(self, "Input Error", "Template must contain at least one task (the Parent).")
             return

        # Ensure the first item is marked as the parent task (is_sub_task=False)
        if template_tasks_list[0]['is_sub_task']:
            QMessageBox.warning(self, "Template Error", "The first task in the list must be the Parent task (Is Sub-task: No).")
            return
            
        template_data = {
            'id': self.template_id,
            'name': name,
            'description': self.template_desc_entry.toPlainText().strip(),
            'default_category': self.category_combo.currentText(),
            'default_priority': template_tasks_list[0]['priority'] # Use parent task's priority as template default
        }

        try:
            # We save the template tasks list with the original IDs from the list widget.
            # The DB function will handle ID mapping for linking sub-tasks to the parent.
            save_task_template(template_data, template_tasks_list)
            QMessageBox.information(self, "Saved", f"Template '{name}' saved successfully.")
            self._load_templates()
            self.template_id = None # Forces a new template if re-edited
            self._new_template()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save template: {e}")
            
    # --- Template Task List Management ---
    def _get_selected_template_task(self):
        """Helper to get the dict of the selected item."""
        current_item = self.template_tasks_list.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            return None
        return current_item.data(Qt.ItemDataRole.UserRole)

    def _add_template_task(self):
        """Opens the TaskEditor dialog to create a new task/step."""
        # The parent_task_id is relative_parent_id in the template_tasks table, 
        # but here we use the ID of the *first* task in the list to simplify.
        is_parent = self.template_tasks_list.count() == 0
        parent_task_id_in_list = None
        if not is_parent:
            # Get the ID of the task that will become the parent in the *next* step.
            # This is the ID of the first task currently in the list.
            parent_task_id_in_list = self.template_tasks_list.item(0).data(Qt.ItemDataRole.UserRole)['id']
        
        dialog = TemplateTaskEditorDialog(is_parent=is_parent, parent_id=parent_task_id_in_list, parent=self)
        if dialog.exec():
            new_task_dict = dialog.get_task_data()
            if not new_task_dict: return
            
            if is_parent:
                 # Ensure parent is first and clear list if adding a new parent
                 self.template_tasks_list.clear()
                 
            item_text = f"[T] {new_task_dict['description']} (P: {new_task_dict['priority']})" if not new_task_dict['is_sub_task'] else f"[—] {new_task_dict['description']} (P: {new_task_dict['priority']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, new_task_dict)
            self.template_tasks_list.addItem(item)
            
    def _edit_template_task(self):
        """Opens the TaskEditor dialog to edit the selected task/step."""
        selected_task = self._get_selected_template_task()
        if not selected_task:
            QMessageBox.warning(self, "No Selection", "Please select a task to edit.")
            return

        is_parent = not selected_task['is_sub_task']
        
        dialog = TemplateTaskEditorDialog(task_data=selected_task, is_parent=is_parent, parent=self)
        if dialog.exec():
            new_task_dict = dialog.get_task_data()
            if not new_task_dict: return

            current_item = self.template_tasks_list.currentItem()
            current_item.setData(Qt.ItemDataRole.UserRole, new_task_dict)
            
            item_text = f"[T] {new_task_dict['description']} (P: {new_task_dict['priority']})" if not new_task_dict['is_sub_task'] else f"[—] {new_task_dict['description']} (P: {new_task_dict['priority']})"
            current_item.setText(item_text)

    def _remove_template_task(self):
        """Removes the selected task/step from the list."""
        current_item = self.template_tasks_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a task to remove.")
            return

        if not current_item.data(Qt.ItemDataRole.UserRole)['is_sub_task']:
            QMessageBox.warning(self, "Error", "You cannot remove the Parent Task directly. Please delete the entire template.")
            return

        row = self.template_tasks_list.row(current_item)
        self.template_tasks_list.takeItem(row)


# --- Template Task Editor Dialog (NEW) ---
class TemplateTaskEditorDialog(QDialog):
    """Dialog for editing a single task (parent or sub-task) within a template."""
    def __init__(self, task_data=None, is_parent=False, parent_id=None, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.is_parent = is_parent
        self.relative_parent_id = parent_id # ID of the template's *parent* task
        
        self.setWindowTitle("Edit Template Task" if task_data else "Add Template Task")
        
        self.layout = QFormLayout(self)
        
        self.desc_entry = QLineEdit(task_data.get('description', '') if task_data else '')
        self.layout.addRow("Description:", self.desc_entry)
        
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText(task_data.get('priority', 'Medium') if task_data else 'Medium')
        self.layout.addRow("Priority:", self.priority_combo)
        
        # --- FIX: Removed unnecessary is_sub_task_check for clarity ---
        # Since the logic in _add_template_task determines parent/sub-task status 
        # based on list position, we don't need a confusing checkbox here.
        
        self.notes_editor = QPlainTextEdit(task_data.get('notes', '') if task_data else '')
        self.notes_editor.setFixedHeight(50)
        self.layout.addRow("Notes:", self.notes_editor)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_task_data(self):
        """Returns the dictionary representing this task/step."""
        desc = self.desc_entry.text().strip()
        if not desc:
            QMessageBox.warning(self, "Input Error", "Description cannot be empty.")
            return None
        
        # is_sub is determined by the calling method, not the dialog's UI
        is_sub = not self.is_parent

        # Generate a temporary unique ID for mapping purposes within the template
        temp_id = self.task_data.get('id') if self.task_data else str(uuid.uuid4())
        
        return {
            'id': temp_id, # Temporary ID
            'description': desc,
            'notes': self.notes_editor.toPlainText().strip(),
            'priority': self.priority_combo.currentText(),
            'is_sub_task': is_sub,
            # Link sub-tasks to the ID of the template parent task (the first item in the list)
            'relative_parent_id': self.relative_parent_id if is_sub else None 
        }

# --- Settings Dialog (MODIFIED) ---
class SettingsDialog(QDialog):
    theme_changed = Signal()
    pomodoro_settings_changed = Signal()
    personalization_changed = Signal()
    # --- NEW SIGNALS ---
    categories_updated = Signal()
    schedule_settings_changed = Signal()

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
        
        self.schedule_settings_button = QPushButton("Manage Schedule View Settings...")
        self.schedule_settings_button.clicked.connect(self._open_schedule_settings)
        other_layout.addWidget(self.schedule_settings_button)
        
        # --- NEW: Template Button ---
        self.template_button = QPushButton("Manage Task Templates")
        self.template_button.clicked.connect(self._open_templates_dialog)
        other_layout.addWidget(self.template_button)
        # --- END NEW ---

        self.automation_button = QPushButton("Manage Automations")
        self.automation_button.clicked.connect(self._open_automations_dialog)
        other_layout.addWidget(self.automation_button)
        
        self.categories_button = QPushButton("Manage Task Categories")
        self.categories_button.clicked.connect(self._open_categories_dialog)
        other_layout.addWidget(self.categories_button)

        self.export_button = QPushButton("Export Tasks to CSV")
        self.export_button.clicked.connect(self.parent_window._export_tasks)
        other_layout.addWidget(self.export_button)

        self.prev_notes_button = QPushButton("View Daily History")
        self.prev_notes_button.clicked.connect(self.parent_window._open_history_dialog)
        other_layout.addWidget(self.prev_notes_button)

        self.stats_button = QPushButton("View Productivity Stats")
        self.stats_button.clicked.connect(self._open_stats_dialog)
        if StatisticsDialog is None:
            self.stats_button.setEnabled(False)
            self.stats_button.setText("View Productivity Stats (Module Missing)")
            self.stats_button.setToolTip("Please install pyside6-addons to enable this feature.")
        other_layout.addWidget(self.stats_button)

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
        
    def _open_schedule_settings(self):
        """Opens the separate dialog for Schedule settings."""
        dialog = ScheduleSettingsDialog(self)
        # We catch the signal from the sub-dialog and pass it up
        dialog.schedule_settings_changed.connect(self.schedule_settings_changed)
        dialog.exec()

    def _open_automations_dialog(self):
        dialog = ManageAutomationsDialog(self)
        dialog.exec()

    def _open_categories_dialog(self):
        dialog = ManageCategoriesDialog(self)
        # Connect the dialog's signal to this dialog's signal
        dialog.categories_updated.connect(self.categories_updated)
        dialog.exec()
        
    def _open_templates_dialog(self):
        dialog = ManageTaskTemplatesDialog(self)
        dialog.exec()

    def _open_stats_dialog(self):
        if StatisticsDialog:
            # We pass 'self' as the parent so the dialog can read the theme
            dialog = StatisticsDialog(self)
            dialog.exec()
        else:
            QMessageBox.critical(self, "Error", 
                "The statistics module could not be loaded.\n"
                "Please ensure 'pyside6-addons' is installed in your environment.\n"
                "(Try: pip install pyside6-addons)")

# --- NEW: Manual Time Log Dialog ---
class ManualTimeLogDialog(QDialog):
    def __init__(self, initial_qdate, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Manual Time")
        
        self.layout = QFormLayout(self)
        
        self.date_label = QLabel(initial_qdate.toString("yyyy-MM-dd"))
        self.selected_qdate = initial_qdate
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 1440) # 1 min to 24 hours
        self.duration_spin.setValue(30)
        self.duration_spin.setSuffix(" minutes")
        
        self.task_combo = QComboBox()
        self._populate_tasks()
        
        self.layout.addRow("Date:", self.date_label)
        self.layout.addRow("Duration:", self.duration_spin)
        self.layout.addRow("Link to Task:", self.task_combo)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._save_log)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _populate_tasks(self):
        """Loads all tasks (pending and completed) into the combo box."""
        self.task_combo.clear()
        self.task_combo.addItem("Unassigned", None) # Add "Unassigned" as the default
        try:
            tasks = get_all_tasks() # Get all tasks
            task_map = {t['id']: t for t in tasks}
            
            # Sort by status (pending first), then by description
            tasks.sort(key=lambda t: (t['status'], t['description']))
            
            for task in tasks:
                desc = task['description']
                parent_id = task.get('parent_task_id')
                
                if parent_id and parent_id in task_map:
                    parent_name = task_map[parent_id].get('description', 'Parent')
                    display_text = f"{parent_name}: {desc}"
                else:
                    display_text = desc
                
                if task['status'] == 'completed':
                    display_text = f"(Done) {display_text}"
                    
                self.task_combo.addItem(display_text, task['id']) # Store ID as data
                
        except Exception as e:
            print(f"Error populating task list for manual log: {e}")

    def _save_log(self):
        """Saves the manual log entry to the database."""
        try:
            date_str = self.selected_qdate.toString("yyyy-MM-dd")
            duration = self.duration_spin.value()
            task_id = self.task_combo.currentData() # This will be None for "Unassigned"
            
            add_manual_focus_log(date_str, duration, task_id)
            QMessageBox.information(self, "Saved", "Manual log entry saved successfully.")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save manual log: {e}")


# --- History Dialog (MODIFIED) ---
class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Daily History")
        self.setMinimumSize(800, 600)
        
        self.selected_qdate = QDate.currentDate() # Store selected date

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
        
        # --- NEW: Top Bar (Date + Log Button) ---
        top_bar_layout = QHBoxLayout()
        self.selected_date_label = QLabel("Select a date")
        font = QFont(); font.setPointSize(14); font.setBold(True)
        self.selected_date_label.setFont(font)
        
        self.log_manual_time_btn = QPushButton("Log Manual Time for this Date")
        self.log_manual_time_btn.clicked.connect(self._open_manual_log_dialog)
        
        top_bar_layout.addWidget(self.selected_date_label)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.log_manual_time_btn)
        data_layout.addLayout(top_bar_layout)
        # --- END NEW ---

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
        columns_layout.addWidget(tasks_group, 1)

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
        columns_layout.addWidget(schedule_group, 1)
        
        # --- NEW: Column 3: Focus Sessions ---
        focus_group = QGroupBox("Focus Sessions")
        focus_layout = QVBoxLayout(focus_group)
        self.focus_scroll_area = QScrollArea()
        self.focus_scroll_area.setWidgetResizable(True)
        focus_list_widget = QWidget()
        self.focus_list_layout = QVBoxLayout(focus_list_widget)
        self.focus_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.focus_scroll_area.setWidget(focus_list_widget)
        focus_layout.addWidget(self.focus_scroll_area)
        columns_layout.addWidget(focus_group, 1)
        # --- END NEW ---

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
        self.selected_qdate = q_date # <-- Store the date
        date_str = q_date.toString("yyyy-MM-dd")
        self.selected_date_label.setText(q_date.toString("dddd, MMM d, yyyy"))

        # Clear previous data
        self._clear_layout(self.tasks_list_layout)
        self._clear_layout(self.schedule_list_layout)
        self._clear_layout(self.focus_list_layout) # <-- NEW
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
            
        # --- NEW: Load Focus Sessions ---
        try:
            focus_logs = get_focus_logs_for_date(date_str)
            if not focus_logs:
                self.focus_list_layout.addWidget(QLabel("No focus sessions logged."))
            else:
                for log in focus_logs:
                    log_id = log['id']
                    task_desc = log['task_description']
                    duration = log['duration_minutes']
                    session_type = log['session_type']
                    notes = log['notes'] or ""
                    
                    # Create a small frame for each log
                    log_frame = QFrame()
                    log_frame.setObjectName("todayScheduleLabel") # Re-use style
                    log_layout = QVBoxLayout(log_frame)
                    log_layout.setSpacing(2)
                    
                    desc_label = ""
                    if session_type == 'break':
                        desc_label = f"<b>Break Session</b> ({duration}m)"
                    elif task_desc == "Unassigned":
                        desc_label = f"<b>Unassigned Work</b> ({duration}m)"
                    else:
                        desc_label = f"<b>Task:</b> {task_desc} ({duration}m)"
                        
                    if log['notes'] == 'Manually Logged':
                        desc_label += " <i>(Manual)</i>"
                        
                    log_layout.addWidget(QLabel(desc_label))
                    
                    if notes and notes != 'Manually Logged':
                        notes_label = QLabel(f"<i>Notes: {notes}</i>")
                        notes_label.setWordWrap(True)
                        log_layout.addWidget(notes_label)
                        
                    # Add/Edit note button (disable for breaks)
                    edit_note_btn = QPushButton("Add/Edit Note")
                    if session_type == 'break':
                        edit_note_btn.setEnabled(False)
                        edit_note_btn.setText("Add Note (N/A for Breaks)")
                    
                    # Use a lambda to pass the log_id and current notes
                    edit_note_btn.clicked.connect(lambda checked, l_id=log_id, c_notes=notes: self._edit_focus_note(l_id, c_notes))
                    log_layout.addWidget(edit_note_btn)
                    
                    self.focus_list_layout.addWidget(log_frame)
                    
        except Exception as e:
            print(f"Error loading history focus logs: {e}")
            self.focus_list_layout.addWidget(QLabel("Error loading focus logs."))
        # --- END NEW ---

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
            
    # --- NEW: Method to edit focus log notes ---
    def _edit_focus_note(self, log_id, current_notes):
        """ Opens an input dialog to add/edit notes for a focus log. """
        
        # Don't try to edit the default "Manually Logged" note
        notes_to_edit = "" if current_notes == "Manually Logged" else current_notes
        
        # Use QInputDialog.getMultiLineText for a bigger text box
        text, ok = QInputDialog.getMultiLineText(self, "Edit Session Notes", 
                                                 "Log notes for this session:", 
                                                 notes_to_edit)
        
        if ok: # User clicked OK
            try:
                # If the session was manual, and text is still empty, keep the manual note
                final_notes = text
                if current_notes == "Manually Logged" and not text.strip():
                    final_notes = "Manually Logged"
                
                update_focus_log_notes(log_id, final_notes)
                # Refresh the entire view to show the new notes
                self._on_date_selected(self.selected_qdate)
                
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not save notes: {e}")
                
    # --- NEW: Method to open manual log dialog ---
    def _open_manual_log_dialog(self):
        """Opens the dialog to manually add a focus log entry."""
        dialog = ManualTimeLogDialog(self.selected_qdate, self)
        if dialog.exec():
            # If saved, refresh the view for the current date
            self._on_date_selected(self.selected_qdate)


# --- Select Focus Task Dialog (for Feature 2) ---
class SelectFocusTaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Task to Focus On")
        self.setMinimumWidth(400)
        self.selected_task_id = None # This will store the result
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("Which task are you working on?"))
        
        self.task_list_widget = QListWidget()
        self.layout.addWidget(self.task_list_widget, 1) # Give it stretch
        
        self._populate_tasks()
        
        # --- Button Box ---
        self.button_box = QDialogButtonBox()
        link_button = self.button_box.addButton("Link to Selected Task", QDialogButtonBox.ButtonRole.AcceptRole)
        unassigned_button = self.button_box.addButton("Start Unassigned Session", QDialogButtonBox.ButtonRole.ActionRole)
        cancel_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        
        link_button.clicked.connect(self._on_link)
        unassigned_button.clicked.connect(self._on_unassigned)
        cancel_button.clicked.connect(self.reject) # Reject (cancel)
        
        self.layout.addWidget(self.button_box)
        
    def _populate_tasks(self):
        """ Loads all pending tasks and sub-tasks into the list. """
        self.task_list_widget.clear()
        try:
            tasks = get_all_pending_tasks() # Gets parents and children
            if not tasks:
                item = QListWidgetItem("No pending tasks.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.task_list_widget.addItem(item)
                return
                
            # --- To show sub-tasks nicely, we need parent info ---
            task_map = {t['id']: t for t in tasks}
            
            for task in tasks:
                desc = task['description']
                parent_id = task.get('parent_task_id')
                
                if parent_id and parent_id in task_map:
                    # It's a sub-task, find its parent's name
                    parent_name = task_map[parent_id].get('description', 'Parent')
                    display_text = f"{parent_name}: {desc}"
                else:
                    # It's a top-level task
                    display_text = desc
                    
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, task['id']) # Store task ID
                self.task_list_widget.addItem(item)
                
        except Exception as e:
            print(f"Error populating focus task dialog: {e}")
            self.task_list_widget.addItem("Error loading tasks.")

    def _on_link(self):
        """ User chose to link the selected task. """
        current_item = self.task_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "No Selection", "Please select a task from the list.")
            return
            
        self.selected_task_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.accept() # Accept (close)

    def _on_unassigned(self):
        """ User chose to work without a task. """
        self.selected_task_id = None # Set to None
        self.accept() # Accept (close)
        
    def get_selected_task_id(self):
        """ Called by the parent to get the result. """
        return self.selected_task_id