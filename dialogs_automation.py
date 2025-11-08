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
    get_automation_rule_details, get_automations,
    delete_automation_rule, save_automation_rule
)


# --- Manage Automations Dialog ---
class ManageAutomationsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Manage Automations")
        self.setMinimumSize(500, 400)

        self.layout = QVBoxLayout(self)

        self.rules_list_widget = QListWidget()
        self.layout.addWidget(self.rules_list_widget)

        button_layout = QHBoxLayout()
        add_button = QPushButton("Add New Rule")
        add_button.clicked.connect(self._add_rule)
        edit_button = QPushButton("Edit Selected Rule")
        edit_button.clicked.connect(self._edit_rule)
        delete_button = QPushButton("Delete Selected Rule")
        delete_button.clicked.connect(self._delete_rule)

        button_layout.addWidget(add_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        self.layout.addLayout(button_layout)

        self._load_rules()

    def _load_rules(self):
        """ Loads automation rules into the list. """
        self.rules_list_widget.clear()
        try:
            rules = get_automations()
            if not rules:
                item = QListWidgetItem("No automation rules created.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray")) 
                self.rules_list_widget.addItem(item)
            else:
                for rule in rules:
                    display_text = f"{rule['rule_name']} (Trigger: '{rule['trigger_title']}')"
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, rule['id'])
                    self.rules_list_widget.addItem(item)
        except Exception as e:
            print(f"Error loading automations: {e}")

    def _add_rule(self):
        """ Opens the dialog to create a new automation rule. """
        dialog = AutomationRuleDialog(parent=self)
        if dialog.exec():
            self._load_rules()

    def _edit_rule(self):
        """ Opens the dialog to edit an existing automation rule. """
        current_item = self.rules_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Edit Error", "Please select a rule to edit.")
            return

        rule_id = current_item.data(Qt.ItemDataRole.UserRole)

        try:
            rule_data = get_automation_rule_details(rule_id)
            if not rule_data:
                QMessageBox.critical(self, "Error", "Could not find rule details.")
                return

            dialog = AutomationRuleDialog(parent=self, rule_data=rule_data)
            if dialog.exec():
                self._load_rules()

        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not load rule for editing: {e}")


    def _delete_rule(self):
        """ Deletes the selected automation rule. """
        current_item = self.rules_list_widget.currentItem()
        if not current_item or not current_item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Delete Error", "Please select a rule to delete.")
            return

        rule_id = current_item.data(Qt.ItemDataRole.UserRole)
        rule_text = current_item.text()

        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Delete automation rule:\n{rule_text}?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_automation_rule(rule_id)
                self._load_rules()
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not delete rule: {e}")


# --- Automation Action Dialogs (NEW) ---
class TaskActionDialog(QDialog):
    """A dialog to add or edit a 'create task' action."""
    def __init__(self, action_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Task Action")

        self.layout = QFormLayout(self)

        self.task_desc_entry = QLineEdit()
        self.task_desc_entry.setPlaceholderText("e.g., 'Dispatch Exhibits'")
        self.task_priority_combo = QComboBox()
        self.task_priority_combo.addItems(["Low", "Medium", "High"])
        self.task_category_entry = QLineEdit()
        self.task_category_entry.setPlaceholderText("e.g., 'Automation'")

        self.layout.addRow("Task Description:", self.task_desc_entry)
        self.layout.addRow("Task Priority:", self.task_priority_combo)
        self.layout.addRow("Task Category:", self.task_category_entry)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addRow(self.button_box)

        if action_data:
            self.task_desc_entry.setText(action_data.get('param1', ''))
            self.task_priority_combo.setCurrentText(action_data.get('param2', 'Medium'))
            self.task_category_entry.setText(action_data.get('param3', 'Automation'))

    def get_data(self):
        """Returns the action data from the form."""
        desc = self.task_desc_entry.text().strip()
        if not desc:
            QMessageBox.warning(self, "Input Error", "Task Description cannot be empty.")
            return None
        return {
            'id': str(uuid.uuid4()),
            'action_type': 'ensure_task_link',
            'param1': desc,
            'param2': self.task_priority_combo.currentText(),
            'param3': self.task_category_entry.text().strip() or "Automation"
        }

class ScheduleActionDialog(QDialog):
    """A dialog to add or edit a 'create schedule' action."""
    def __init__(self, action_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule Action")

        self.layout = QFormLayout(self)

        self.schedule_title_entry = QLineEdit()
        self.schedule_title_entry.setPlaceholderText("e.g., 'Dispatch'")
        self.schedule_time_edit = QTimeEdit()
        self.schedule_time_edit.setDisplayFormat("HH:mm")
        self.schedule_time_edit_end = QTimeEdit()
        self.schedule_time_edit_end.setDisplayFormat("HH:mm")

        self.layout.addRow("Block Title:", self.schedule_title_entry)
        self.layout.addRow("Start Time:", self.schedule_time_edit)
        self.layout.addRow("End Time:", self.schedule_time_edit_end)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addRow(self.button_box)

        if action_data:
            self.schedule_title_entry.setText(action_data.get('param1', ''))
            self.schedule_time_edit.setTime(QTime.fromString(action_data.get('param2', '14:00'), "HH:mm"))
            self.schedule_time_edit_end.setTime(QTime.fromString(action_data.get('param3', '15:00'), "HH:mm"))
        else:
            self.schedule_time_edit.setTime(QTime(14, 0))
            self.schedule_time_edit_end.setTime(QTime(15, 0))

    def get_data(self):
        """Returns the action data from the form."""
        title = self.schedule_title_entry.text().strip()
        if not title:
            QMessageBox.warning(self, "Input Error", "Block Title cannot be empty.")
            return None

        if self.schedule_time_edit_end.time() <= self.schedule_time_edit.time():
            QMessageBox.warning(self, "Input Error", "End Time must be after Start Time.")
            return None

        return {
            'id': str(uuid.uuid4()),
            'action_type': 'create_schedule_block',
            'param1': title,
            'param2': self.schedule_time_edit.time().toString("HH:mm"),
            'param3': self.schedule_time_edit_end.time().toString("HH:mm")
        }

# --- Automation Rule Creation Dialog (Overhauled) ---
class AutomationRuleDialog(QDialog):
    def __init__(self, parent=None, rule_data=None):
        super().__init__(parent)
        self.automation_id = rule_data.get('id') if rule_data else None
        self.setWindowTitle("Edit Automation Rule" if rule_data else "Create Automation Rule")
        self.setMinimumSize(500, 400)

        # This list will hold our action dictionaries
        self.actions_list = []

        self.layout = QVBoxLayout(self)

        # --- Rule Details ---
        form_layout = QFormLayout()
        self.rule_name_entry = QLineEdit()
        self.rule_name_entry.setPlaceholderText("e.g., 'Late Shift Prep'")
        form_layout.addRow("Rule Name:", self.rule_name_entry)

        self.trigger_title_entry = QLineEdit()
        self.trigger_title_entry.setPlaceholderText("e.g., 'Late Shift' (must match calendar event title)")
        form_layout.addRow("Trigger Event Title:", self.trigger_title_entry)
        self.layout.addLayout(form_layout)

        # --- Actions List ---
        actions_group = QGroupBox("Actions (Run on Trigger Day)")
        actions_layout = QVBoxLayout(actions_group)

        self.actions_list_widget = QListWidget()
        actions_layout.addWidget(self.actions_list_widget)

        # Action buttons
        action_button_layout = QHBoxLayout()
        add_task_btn = QPushButton("Add Task Action")
        add_task_btn.clicked.connect(self._add_task_action)
        add_schedule_btn = QPushButton("Add Schedule Action")
        add_schedule_btn.clicked.connect(self._add_schedule_action)

        action_button_layout.addWidget(add_task_btn)
        action_button_layout.addWidget(add_schedule_btn)
        actions_layout.addLayout(action_button_layout)

        # Edit/Remove buttons
        edit_remove_layout = QHBoxLayout()
        edit_action_btn = QPushButton("Edit Selected Action")
        edit_action_btn.clicked.connect(self._edit_action)
        remove_action_btn = QPushButton("Remove Selected Action")
        remove_action_btn.clicked.connect(self._remove_action)

        edit_remove_layout.addWidget(edit_action_btn)
        edit_remove_layout.addWidget(remove_action_btn)
        actions_layout.addLayout(edit_remove_layout)

        self.layout.addWidget(actions_group)
        self.layout.addStretch()

        # --- Save/Cancel Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_rule)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        if rule_data:
            self._load_rule(rule_data)

    def _load_rule(self, rule_data):
        """ Pre-fills the dialog fields with data from an existing rule. """
        self.rule_name_entry.setText(rule_data.get('rule_name', ''))
        self.trigger_title_entry.setText(rule_data.get('trigger_title', ''))

        # Load actions into our internal list and the list widget
        self.actions_list = rule_data.get('actions', [])
        self._refresh_actions_list_widget()

    def _refresh_actions_list_widget(self):
        """Clears and repopulates the QListWidget from self.actions_list."""
        self.actions_list_widget.clear()
        for i, action in enumerate(self.actions_list):
            action_type = action.get('action_type')
            desc = ""
            if action_type == 'ensure_task_link':
                desc = f"[Task] {action.get('param1', 'No Description')}"
            elif action_type == 'create_schedule_block':
                desc = f"[Schedule] {action.get('param1', 'No Title')} ({action.get('param2')} - {action.get('param3')})"

            item = QListWidgetItem(desc, self.actions_list_widget)
            item.setData(Qt.ItemDataRole.UserRole, i) # Store the index

    # --- START OF MISSING METHODS ---

    def _add_task_action(self):
        """Opens the TaskActionDialog to create a new task action."""
        dialog = TaskActionDialog(parent=self)
        if dialog.exec():
            action_data = dialog.get_data()
            if action_data:
                self.actions_list.append(action_data)
                self._refresh_actions_list_widget()

    def _add_schedule_action(self):
        """Opens the ScheduleActionDialog to create a new schedule action."""
        dialog = ScheduleActionDialog(parent=self)
        if dialog.exec():
            action_data = dialog.get_data()
            if action_data:
                self.actions_list.append(action_data)
                self._refresh_actions_list_widget()

    def _edit_action(self):
        """Edits the currently selected action."""
        current_item = self.actions_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Edit Error", "Please select an action to edit.")
            return

        index = current_item.data(Qt.ItemDataRole.UserRole)
        # Ensure index is valid
        if index < 0 or index >= len(self.actions_list):
             QMessageBox.warning(self, "Edit Error", "Selected action index is out of range.")
             return
             
        action_data = self.actions_list[index]

        if action_data['action_type'] == 'ensure_task_link':
            dialog = TaskActionDialog(action_data, self)
            if dialog.exec():
                new_data = dialog.get_data()
                if new_data:
                    self.actions_list[index] = new_data
                    self._refresh_actions_list_widget()

        elif action_data['action_type'] == 'create_schedule_block':
            dialog = ScheduleActionDialog(action_data, self)
            if dialog.exec():
                new_data = dialog.get_data()
                if new_data:
                    self.actions_list[index] = new_data
                    self._refresh_actions_list_widget()

    def _remove_action(self):
        """Removes the currently selected action."""
        current_item = self.actions_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Remove Error", "Please select an action to remove.")
            return

        index = current_item.data(Qt.ItemDataRole.UserRole)
        # Ensure index is valid
        if index < 0 or index >= len(self.actions_list):
             QMessageBox.warning(self, "Remove Error", "Selected action index is out of range.")
             return

        reply = QMessageBox.question(self, 'Confirm Remove',
                                   f"Remove action:\n{current_item.text()}?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            del self.actions_list[index]
            self._refresh_actions_list_widget()

    def save_rule(self):
        """ Saves the new rule and its list of actions to the database. """
        rule_name = self.rule_name_entry.text().strip()
        trigger_title = self.trigger_title_entry.text().strip()

        if not (rule_name and trigger_title):
            QMessageBox.warning(self, "Input Error", "Rule Name and Trigger Title cannot be empty.")
            return

        if not self.actions_list:
            QMessageBox.warning(self, "Input Error", "A rule must have at least one action.")
            return

        try:
            save_automation_rule(self.automation_id, rule_name, trigger_title, self.actions_list)
            self.accept()

        except sqlite3.IntegrityError:
             QMessageBox.critical(self, "Database Error", f"A rule with the trigger '{trigger_title}' already exists.")
        except ValueError as ve:
             QMessageBox.warning(self, "Input Error", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save automation rule: {e}")
            
    # --- END OF MISSING METHODS ---