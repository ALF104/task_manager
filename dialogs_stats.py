import sys
from datetime import datetime, timedelta

# --- PySide6 Imports ---
# We no longer need QtCharts!
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDialog, QDialogButtonBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QAbstractItemView
)
from PySide6.QtGui import (
    QPainter, QColor, QFont
)
from PySide6.QtCore import (
    Qt, QDate
)

# --- Import from our new structure ---
from app.core.database import (
    get_focus_time_by_task_for_range, 
    get_tasks_completed_summary_for_range,
    get_focus_time_summary_for_range,
    get_app_state 
)

# --- Helper function to format minutes ---
def format_minutes(total_minutes):
    """Converts total minutes to a 'Xh Ym' string."""
    if total_minutes == 0:
        return "0m"
    hours, minutes = divmod(total_minutes, 60) # Was div_mod
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m"
    return f"{int(minutes)}m"

# --- Statistics Dialog ---
class StatisticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Productivity Statistics")
        self.setMinimumSize(800, 600)
        self.theme_mode = 'dark' # Default
        
        # Get theme from parent if possible
        if parent and hasattr(parent, 'parent_window') and hasattr(parent.parent_window, 'app'):
             try:
                 theme_setting = get_app_state('theme') or 'system'
                 if theme_setting == 'light':
                     self.theme_mode = 'light'
                 elif theme_setting == 'dark':
                     self.theme_mode = 'dark'
                 else: # system
                     app_palette = parent.parent_window.app.palette()
                     if app_palette.window().color().lightness() < 128:
                         self.theme_mode = 'dark'
                     else:
                         self.theme_mode = 'light'
             except Exception as e:
                 print(f"Could not detect theme, defaulting to dark: {e}")
                 self.theme_mode = 'dark'
        
        self.layout = QVBoxLayout(self)
        
        # --- 1. Top Controls ---
        controls_layout = QHBoxLayout()
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(["Last 7 Days", "This Month", "Last 30 Days"])
        self.date_range_combo.currentTextChanged.connect(self._update_all_tabs)
        
        controls_layout.addWidget(QLabel("Date Range:"))
        controls_layout.addWidget(self.date_range_combo)
        controls_layout.addStretch()
        self.layout.addLayout(controls_layout)
        
        # --- 2. Tab Widget ---
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        # --- Tab 1: Summary ---
        self.summary_tab = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_tab)
        self.tab_widget.addTab(self.summary_tab, "Summary")
        
        # --- Tab 2: Focus by Task ---
        self.focus_tab = QWidget()
        self.focus_layout = QVBoxLayout(self.focus_tab)
        self.tab_widget.addTab(self.focus_tab, "Focus by Task")

        # --- Tab 3: Completion Stats ---
        self.completion_tab = QWidget()
        self.completion_layout = QVBoxLayout(self.completion_tab)
        self.tab_widget.addTab(self.completion_tab, "Completion Stats")

        # --- 3. Close Button ---
        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.rejected.connect(self.reject)
        self.layout.addWidget(close_button)
        
        # --- Build UI for Tabs ---
        self._setup_summary_tab()
        self._setup_focus_tab()
        self._setup_completion_tab()
        
        # --- Initial Load ---
        self._update_all_tabs()

    def _get_date_range(self):
        """Calculates start and end date strings based on combo box."""
        range_text = self.date_range_combo.currentText()
        end_date = datetime.now()
        start_date = datetime.now()
        
        if range_text == "Last 7 Days":
            start_date = end_date - timedelta(days=6) # 6 days ago + today = 7 days
        elif range_text == "Last 30 Days":
            start_date = end_date - timedelta(days=29)
        elif range_text == "This Month":
            start_date = end_date.replace(day=1)
            
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def _update_all_tabs(self):
        """Fetches data and re-renders all tabs."""
        start_date, end_date = self._get_date_range()
        
        try:
            self._update_summary_tab(start_date, end_date)
            self._update_focus_tab(start_date, end_date)
            self._update_completion_tab(start_date, end_date)
        except Exception as e:
            QMessageBox.critical(self, "Stats Error", f"Could not load statistics: {e}")
            print(f"Stats Error: {e}")

    # --- Formats total minutes into a 'Xh Ym' string ---
    def _format_minutes(self, total_minutes):
        if total_minutes == 0:
            return "0m"
        hours, minutes = divmod(total_minutes, 60) # Corrected
        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m"
        return f"{int(minutes)}m"

    # --- ================== ---
    # --- Setup Summary Tab  ---
    # --- ================== ---
    def _setup_summary_tab(self):
        # Work vs Break Table
        self.summary_table = QTableWidget(2, 2) # Changed to 2x2
        self.summary_table.setHorizontalHeaderLabels(["Total Time", "Percentage"])
        self.summary_table.setVerticalHeaderLabels(["Work", "Break"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # --- REMOVED THE INCORRECT FIX ---
        
        self.summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_layout.addWidget(self.summary_table)
        
        # Completion Stats
        self.completion_label = QLabel("Total Tasks Completed: 0")
        font = QFont(); font.setPointSize(12)
        self.completion_label.setFont(font)
        self.summary_layout.addWidget(self.completion_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.summary_layout.addStretch()

    def _update_summary_tab(self, start_date, end_date):
        # 1. Update Work vs Break Table
        try:
            data = get_focus_time_summary_for_range(start_date, end_date)
            work_min = data.get('work', 0)
            break_min = data.get('break', 0)
            total_min = work_min + break_min
            
            work_perc = (work_min / total_min * 100) if total_min > 0 else 0
            break_perc = (break_min / total_min * 100) if total_min > 0 else 0
            
            self.summary_table.setItem(0, 0, QTableWidgetItem(self._format_minutes(work_min)))
            self.summary_table.setItem(0, 1, QTableWidgetItem(f"{work_perc:.1f}%"))
            self.summary_table.setItem(1, 0, QTableWidgetItem(self._format_minutes(break_min)))
            self.summary_table.setItem(1, 1, QTableWidgetItem(f"{break_perc:.1f}%"))

            # Align text
            self.summary_table.item(0, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary_table.item(0, 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary_table.item(1, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary_table.item(1, 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        except Exception as e:
            print(f"Error updating summary tab: {e}")

        # 2. Update Total Tasks Completed
        try:
            # We can re-use the completion stats function for this
            stats = get_tasks_completed_summary_for_range(start_date, end_date)
            total_completed = sum(stats['daily'].values())
            self.completion_label.setText(f"Total Tasks Completed: {total_completed}")
        except Exception as e:
            print(f"Error updating completion label: {e}")

    # --- =================== ---
    # --- Setup Focus Tab (MODIFIED) ---
    # --- =================== ---
    def _setup_focus_tab(self):
        self.focus_layout.addWidget(QLabel("<b>Pending Tasks</b> (Ranked by focus time)"))
        self.pending_tasks_table = QTableWidget(0, 2)
        self.pending_tasks_table.setHorizontalHeaderLabels(["Task", "Total Focus Time"])
        self.pending_tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.pending_tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.pending_tasks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.focus_layout.addWidget(self.pending_tasks_table, 1)
        
        self.focus_layout.addWidget(QLabel("<b>Completed Tasks</b> (Ranked by focus time)"))
        self.completed_tasks_table = QTableWidget(0, 2)
        self.completed_tasks_table.setHorizontalHeaderLabels(["Task", "Total Focus Time"])
        self.completed_tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.completed_tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.completed_tasks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.focus_layout.addWidget(self.completed_tasks_table, 1)
        
        # --- NEW: Unassigned Work Table ---
        self.focus_layout.addWidget(QLabel("<b>Unassigned Work</b> (Ranked by focus time)"))
        self.unassigned_work_table = QTableWidget(0, 2)
        self.unassigned_work_table.setHorizontalHeaderLabels(["Label", "Total Focus Time"])
        self.unassigned_work_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.unassigned_work_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.unassigned_work_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.focus_layout.addWidget(self.unassigned_work_table, 1) # Give it 1 stretch factor

    def _update_focus_tab(self, start_date, end_date):
        self.pending_tasks_table.setRowCount(0)
        self.completed_tasks_table.setRowCount(0)
        self.unassigned_work_table.setRowCount(0) # <-- NEW
        
        try:
            data = get_focus_time_by_task_for_range(start_date, end_date)
            
            for row in data:
                task_desc = row['description']
                task_status = row['status']
                total_min = row['total_minutes']
                time_str = self._format_minutes(total_min)
                
                # --- MODIFIED: Route to the correct table ---
                table_to_use = None
                if task_desc == 'Unassigned':
                    table_to_use = self.unassigned_work_table
                elif task_status == 'pending':
                    table_to_use = self.pending_tasks_table
                else: # 'completed' or NULL (for old tasks)
                    table_to_use = self.completed_tasks_table
                # --- END MODIFIED ---

                row_count = table_to_use.rowCount()
                table_to_use.insertRow(row_count)
                
                item_desc = QTableWidgetItem(task_desc)
                item_time = QTableWidgetItem(time_str)
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                table_to_use.setItem(row_count, 0, item_desc)
                table_to_use.setItem(row_count, 1, item_time)
                
        except Exception as e:
            print(f"Error updating focus tab: {e}")

    # --- ======================= ---
    # --- Setup Completion Tab  ---
    # --- ======================= ---
    def _setup_completion_tab(self):
        controls = QHBoxLayout()
        self.completion_timeline_combo = QComboBox()
        self.completion_timeline_combo.addItems(["Daily", "Weekly", "Monthly", "Yearly"])
        self.completion_timeline_combo.currentTextChanged.connect(self._update_all_tabs)
        controls.addWidget(QLabel("Group by:"))
        controls.addWidget(self.completion_timeline_combo)
        controls.addStretch()
        self.completion_layout.addLayout(controls)
        
        self.completion_table = QTableWidget(0, 2)
        self.completion_table.setHorizontalHeaderLabels(["Time Period", "Tasks Completed"])
        self.completion_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.completion_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.completion_layout.addWidget(self.completion_table, 1)

    def _update_completion_tab(self, start_date, end_date):
        self.completion_table.setRowCount(0)
        timeline = self.completion_timeline_combo.currentText().lower()
        
        try:
            stats = get_tasks_completed_summary_for_range(start_date, end_date)
            data = stats.get(timeline, {})
            
            if not data:
                self.completion_table.setRowCount(1)
                item = QTableWidgetItem("No tasks completed in this period.")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.completion_table.setItem(0, 0, item)
                self.completion_table.setSpan(0, 0, 1, 2)
                return

            # Sort data by the time period (key)
            sorted_keys = sorted(data.keys(), reverse=True)
            
            self.completion_table.setRowCount(len(sorted_keys))
            
            for i, period_key in enumerate(sorted_keys):
                count = data[period_key]
                
                item_period = QTableWidgetItem(period_key)
                item_count = QTableWidgetItem(str(count))
                item_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                self.completion_table.setItem(i, 0, item_period)
                self.completion_table.setItem(i, 1, item_count)

        except Exception as e:
            print(f"Error updating completion tab: {e}")