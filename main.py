import sys
import sqlite3
import os
import csv
from datetime import datetime, timedelta, time, date
import uuid

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QLineEdit, QPushButton, QComboBox, 
    QScrollArea, QFrame, QMessageBox,
    QFileDialog, QSizePolicy, QSpacerItem, QCalendarWidget,
    QGraphicsView, QGraphicsScene, QGraphicsLineItem,
    QGraphicsPathItem, QGroupBox, QToolBar, QTextEdit,
    QGraphicsTextItem, QDialog, QDialogButtonBox,
    QSystemTrayIcon, QStyle 
)
from PySide6.QtGui import (
    QFont, QPainter, QColor, QPen, QTextCharFormat,
    QPainterPath,
    QIcon, QPixmap 
)
from PySide6.QtCore import (
    Qt, QTimer, QTime, QDate, QRectF, QEvent, Signal, Slot 
)

# --- Import from our new structure ---
from app.core.database import (
    create_tables, get_tasks, get_all_tasks, get_task_by_automation_id,
    get_completed_tasks_for_date, get_tasks_for_month, update_task_status,
    delete_task, link_task_to_event, get_tasks_by_deadline,
    get_tasks_by_show_date, get_tasks_always_pending, is_task_logged_complete,
    add_task_show_date, get_show_dates_for_task, log_task_completion,
    remove_task_completion_log, save_daily_note, get_daily_note,
    add_schedule_event, get_schedule_events_for_date,
    get_app_state, set_app_state, get_calendar_events_for_date, 
    get_calendar_events_for_month, get_automations,
    get_actions_for_automation, add_task
)
# --- Import all our widgets ---
from app.widgets.task_widgets import TodayTaskWidget
from app.widgets.dialogs_task import TaskDetailsDialog
from app.widgets.dialogs_schedule import ScheduleEventDialog
from app.widgets.dialogs_main import SettingsDialog, HistoryDialog
from app.widgets.pomodoro_timer import PomodoroTimerWidget
# --- Import all our tabs ---
from app.tabs.task_manager_tab import TaskManagerTab
from app.tabs.today_dashboard_tab import TodayDashboardTab
from app.tabs.daily_notes_tab import DailyNotesTab
from app.tabs.daily_schedule_tab import DailyScheduleTab
from app.tabs.monthly_calendar_tab import MonthlyCalendarTab
from app.tabs.knowledge_base_tab import KnowledgeBaseTab
# --- Import App Version ---
from app import APP_VERSION


# --- Main Window Class ---
class MainWindow(QMainWindow):
    
    # --- NEW: Constant for schedule check ---
    # We'll notify at 15, 5, and 0 minutes (at start time)
    SCHEDULE_NOTIFY_WINDOWS = [15, 5, 0]

    def __init__(self, app):
        super().__init__()
        
        self.app = app
        
        # Initialize database tables
        try:
            create_tables()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to create database tables: {e}\n\nPlease check file permissions.")
            sys.exit(1) # Exit if we can't even make the tables
        
        # --- Load the app icon ---
        self.app_icon = self._load_app_icon()
        self.setWindowIcon(self.app_icon)
        
        self._setup_tray_icon()
        self._update_window_title() 
        self.setGeometry(100, 100, 1100, 800) 
        
        # Member variables
        self.selected_deadline = None 
        self.view_mode = "pending" 
        self.current_tab_index = 0
        self.current_app_date = QDate.currentDate()
        # --- MODIFIED: Use a dict to track *which* notifications were sent ---
        self.notified_event_windows = {} # e.g., {'event_id': {15, 5}}
        
        # --- Central Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top Bar
        top_bar_layout = QHBoxLayout()
        self.settings_button = QPushButton("⚙️") 
        self.settings_button.setFixedWidth(40) 
        self.settings_button.clicked.connect(self._open_settings_dialog) 
        top_bar_layout.addWidget(self.settings_button)
        
        top_bar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.date_time_label = QLabel("Loading date/time...")
        top_bar_layout.addWidget(self.date_time_label)
        main_layout.addLayout(top_bar_layout)
        
        # Tab Widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, 1)
        self.tab_widget.currentChanged.connect(self._on_tab_changed) 
        
        # --- Create Tabs ---
        self.today_tab = TodayDashboardTab()
        self.today_tab.task_list_updated.connect(self._on_task_data_changed)
        self.today_tab.note_list_updated.connect(self._on_note_data_changed)

        self.task_manager_tab = TaskManagerTab()
        self.task_manager_tab.task_list_updated.connect(self._on_task_data_changed)
        
        self.daily_notes_tab = DailyNotesTab()
        
        self.daily_schedule_tab = DailyScheduleTab()
        self.daily_schedule_tab.data_changed.connect(self._on_task_data_changed)
        
        self.monthly_calendar_tab = MonthlyCalendarTab()
        self.monthly_calendar_tab.data_changed.connect(self._on_task_data_changed)
        
        self.knowledge_base_tab = KnowledgeBaseTab()
        
        self.today_tab.dashboard_date_changed.connect(self.daily_schedule_tab.set_current_date)

        self.tab_widget.insertTab(0, self.today_tab, "Today")
        self.tab_widget.insertTab(1, self.task_manager_tab, "Task Manager")
        self.tab_widget.insertTab(2, self.daily_notes_tab, "Daily Notes")
        self.tab_widget.insertTab(3, self.daily_schedule_tab, "Daily Schedule")
        self.tab_widget.insertTab(4, self.monthly_calendar_tab, "Monthly Calendar")
        self.tab_widget.insertTab(5, self.knowledge_base_tab, "Knowledge Base")
        
        # --- Setup Persistent Timer UI ---
        self.persistent_timer_frame = PomodoroTimerWidget(self)
        
        # --- Connect timer signal to notification slot ---
        self.persistent_timer_frame.timer_finished.connect(self._show_notification)
        
        timer_wrapper_layout = QHBoxLayout()
        timer_wrapper_layout.addWidget(self.persistent_timer_frame)
        timer_wrapper_layout.addStretch(1)
        main_layout.addLayout(timer_wrapper_layout)
        
        # --- Load Theme and Set Initial States ---
        self.load_theme() 

        # --- Start Timers ---
        self.datetime_timer = QTimer(self)
        self.datetime_timer.timeout.connect(self._update_date_time_label)
        self.datetime_timer.start(1000) 
        self._update_date_time_label()
        
        # --- NEW: Master Clock for Schedule Notifications ---
        self.schedule_notification_timer = QTimer(self)
        self.schedule_notification_timer.timeout.connect(self._check_schedule_notifications)
        self.schedule_notification_timer.start(60000) # Check every 60 seconds
        QTimer.singleShot(1000, self._check_schedule_notifications) # Check once on startup
        # --- END NEW ---
        
        # --- Run Automations ---
        # Run *after* all UI is loaded, on a single-shot timer
        QTimer.singleShot(500, self._run_startup_automations)
        
    def load_theme(self):
        """Loads the stylesheet based on the setting in the database."""
        theme_setting = get_app_state('theme') or 'system'
        theme_to_load = theme_setting.lower()
        
        if theme_to_load == 'system':
            try:
                app_palette = self.app.palette()
                # Check lightness of the window background color
                if app_palette.window().color().lightness() < 128:
                    theme_to_load = 'dark'
                else:
                    theme_to_load = 'light'
            except Exception as e:
                print(f"Error detecting system theme, defaulting to light: {e}")
                theme_to_load = 'light' # Default to light on error
        
        style_file = f"style_{theme_to_load}.qss"
        
        try:
            # Get path to 'app/core/' directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to 'app/', then into 'resources/'
            resources_dir = os.path.join(os.path.dirname(current_dir), 'resources')
            style_file_path = os.path.join(resources_dir, style_file)
            
            if not os.path.exists(style_file_path):
                print(f"Warning: Stylesheet file not found at {style_file_path}")
                # Try fallback path (relative to root)
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                style_file_path = os.path.join(base_dir, 'app', 'resources', style_file)
                if not os.path.exists(style_file_path):
                     print(f"Error: Fallback stylesheet not found either: {style_file_path}")
                     self.setStyleSheet("")
                     return

            with open(style_file_path, 'r') as f:
                stylesheet_content = f.read()
                self.setStyleSheet(stylesheet_content)
            
            print(f"Successfully loaded theme: {style_file_path}")

        except Exception as e:
            print(f"Error loading theme '{style_file}'. Path: {style_file_path}. Error: {e}")
            self.setStyleSheet("") # Clear stylesheet on error
            
        # --- Tell all widgets to update their theme ---
        theme_to_pass = 'dark' if theme_to_load == 'dark' else 'light'
        
        if hasattr(self, 'persistent_timer_frame'):
            self.persistent_timer_frame.set_theme(theme_to_pass)
        if hasattr(self, 'daily_schedule_tab'):
            self.daily_schedule_tab.set_theme(theme_to_pass)
            
        # Refresh other UI elements that might be theme-dependent
        if hasattr(self, 'daily_notes_tab'):
            self._on_note_data_changed()
        if hasattr(self, 'task_manager_tab'):
            self.task_manager_tab._display_tasks()

    # --- METHODS FOR SYSTEM TRAY (MODIFIED) ---
    
    def _load_app_icon(self):
        """Loads the app icon from resources, provides a fallback."""
        icon = QIcon() # Start with a blank icon
        
        # --- 1. Try to load your custom icon.ico ---
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            resources_dir = os.path.join(os.path.dirname(current_dir), 'resources')
            icon_path = os.path.join(resources_dir, 'icon.ico') # <-- CHECKING FOR .ico
            if os.path.exists(icon_path):
                print(f"Found custom icon at: {icon_path}")
                icon = QIcon(icon_path)
            else:
                print(f"Warning: 'icon.ico' not found at {icon_path}")
        except Exception as e:
            print(f"Error loading custom icon: {e}")

        # --- 2. Fallback: Create a generic icon if custom one failed ---
        # This GUARANTEES the tray icon is visible.
        if icon.isNull():
            print("No custom icon found. Creating fallback icon.")
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.darkGray) # A simple gray square
            icon = QIcon(pixmap)
        
        return icon

    def _setup_tray_icon(self):
        """Initializes the QSystemTrayIcon."""
        # Re-use the app_icon that was loaded during __init__
        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.tray_icon.setToolTip("Task Manager")
        self.tray_icon.show()
        print(f"Tray icon created. Is it visible? {self.tray_icon.isVisible()}")

    @Slot(str, str)
    def _show_notification(self, title, message):
        """Shows a system tray notification."""
        
        print(f"[Notification] Slot triggered! Title: {title}, Message: {message}")
        
        if not hasattr(self, 'tray_icon'):
            print("[Notification] Error: self.tray_icon object does not exist!")
            return
            
        print(f"[Notification] Tray icon visible? {self.tray_icon.isVisible()}")

        # We will try to show the message regardless of visibility
        self.tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000 # Show for 5 seconds
        )
        
        # --- FALLBACK ---
        # If it's still not visible, it means the tray icon itself
        # failed to show. We'll use a QMessageBox as a backup.
        if not self.tray_icon.isVisible():
            print("[Notification] Fallback: Tray icon not visible. Showing QMessageBox.")
            QMessageBox.information(self, title, message)
    # --- END NEW ---

    def _update_window_title(self):
        """Sets the window title based on the user's name in settings."""
        user_name = get_app_state('user_name') or ''
        if user_name:
            self.setWindowTitle(f"{user_name}'s Task Manager")
        else:
            self.setWindowTitle("Task Manager")

    def _update_date_time_label(self):
        now = datetime.now()
        self.date_time_label.setText(now.strftime("%A, %b %d, %Y | %I:%M:%S %p"))
        
        # --- NEW: Check if the day has rolled over ---
        today = QDate.currentDate()
        if today != self.current_app_date:
            print(f"New day detected. Resetting notification log for {today.toString()}.")
            self.current_app_date = today
            # --- MODIFIED: Clear the new tracking dict ---
            self.notified_event_windows.clear()
        # --- END NEW ---
        
    def _on_tab_changed(self, index):
        """ Handle actions when the selected tab changes. """
        # First, find out which tab we *were* on
        try:
            prev_widget = self.tab_widget.widget(self.current_tab_index)
        except Exception:
            prev_widget = None

        # Save notes from tabs that need it
        if prev_widget == self.daily_notes_tab:
            self.daily_notes_tab._save_current_note()
        elif prev_widget == self.knowledge_base_tab:
            self.knowledge_base_tab.save_current_note()
            
        self.current_tab_index = index
        current_widget = self.tab_widget.widget(index)
        
        # Load data for tabs that need it
        if current_widget == self.today_tab:
            self.today_tab._refresh_today_dashboard()
        elif current_widget == self.daily_notes_tab:
            self.daily_notes_tab._load_current_note()
        elif current_widget == self.monthly_calendar_tab:
            self.monthly_calendar_tab.update_display()
        elif current_widget == self.daily_schedule_tab:
             self.daily_schedule_tab.set_current_date(self.today_tab.dashboard_date)
             # Use a QTimer to ensure the viewport is ready before resizing
             QTimer.singleShot(50, self.daily_schedule_tab.refresh_display)

    def _open_task_details_dialog(self, task_data):
        """ 
        This function is kept in MainWindow because it's shared
        by the TaskManagerTab and the TodayDashboardTab (in the future).
        """
        dialog = TaskDetailsDialog(task_data, self, is_new_task=False)
        dialog.task_saved.connect(self._on_task_data_changed)
        dialog.exec() 

    def _on_task_data_changed(self):
        """
        Slot to refresh all UI elements that depend on the task list.
        """
        print("[Refresh] Task data changed. Refreshing tabs...")
        if hasattr(self, 'task_manager_tab'):
            self.task_manager_tab._display_tasks()
            self.task_manager_tab._load_categories()
        
        if hasattr(self, 'today_tab'):
            self.today_tab._refresh_today_dashboard()
        
        if hasattr(self, 'daily_schedule_tab') and self.daily_schedule_tab.isVisible():
            self.daily_schedule_tab.refresh_display()
            
        if hasattr(self, 'monthly_calendar_tab') and self.monthly_calendar_tab.isVisible():
            self.monthly_calendar_tab.update_display()

    def _on_note_data_changed(self):
        """
        Slot to refresh the notes tab when a quick note is added.
        """
        print("[Refresh] Note data changed. Refreshing notes tab...")
        if hasattr(self, 'daily_notes_tab'):
            # Only reload if the tab is currently visible
            if self.tab_widget.currentWidget() == self.daily_notes_tab:
                self.daily_notes_tab._load_current_note()

    # --- Settings Dialog Functions ---
    def _open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.theme_changed.connect(self.load_theme)
        dialog.pomodoro_settings_changed.connect(self.persistent_timer_frame.reload_settings_and_reset_timer)
        dialog.personalization_changed.connect(self._update_window_title)
        dialog.exec()
        
    def _export_tasks(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Tasks", "", "CSV Files (*.csv);;All Files (*)")
        
        if not file_path:
            return

        try:
            tasks_to_export = get_all_tasks()
            if not tasks_to_export:
                 QMessageBox.information(self, "Export Tasks", "No tasks to export.")
                 return

            # Ensure all potential headers are included
            headers = ['id', 'description', 'status', 'priority', 'category', 'deadline', 
                       'date_added', 'date_completed', 'notes', 'schedule_event_id',
                       'created_by_automation_id', 'show_mode', 'parent_task_id'] # <-- Added new header

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(tasks_to_export)
                
            QMessageBox.information(self, "Export Successful", f"Tasks successfully exported to:\n{file_path}")

        except Exception as e:
            print(f"Error exporting tasks: {e}") 
            QMessageBox.critical(self, "Export Error", f"Failed to export tasks: {e}")

    def _open_history_dialog(self):
        dialog = HistoryDialog(self)
        dialog.exec()

    def _render_note_html(self, html_content, text_browser_widget):
        """
        Applies theme-aware CSS to the loaded HTML for the preview.
        This is used by HistoryDialog.
        """
        theme_setting = get_app_state('theme') or 'system'
        current_theme = theme_setting.lower()
        
        is_dark_theme = False
        if current_theme == 'dark':
            is_dark_theme = True
        elif current_theme == 'system':
            try:
                app_palette = self.app.palette()
                if app_palette.window().color().lightness() < 128:
                    is_dark_theme = True
            except Exception as e:
                print(f"Error in _render_note_html theme check: {e}")
                is_dark_theme = False
        
        if is_dark_theme:
            style = """
            body {{ color: white; background-color: #343638; font-family: Segoe UI, sans-serif; font-size: 10pt;}}
            pre {{ background-color: #2B2B2B; padding: 10px; border-radius: 4px; border: 1px solid #4A4D50; }}
            code {{ font-family: Consolas, monospace; }}
            table {{ border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #4A4D50; padding: 8px; }}
            th {{ background-color: #4A4D50; }}
            a {{ color: #3B8ED0; }}
            del, s {{ color: #999; }} 
            """
        else: # Light theme
            style = """
            body {{ color: black; background-color: #FFFFFF; font-family: Segoe UI, sans-serif; font-size: 10pt;}}
            pre {{ background-color: #F0F0F0; padding: 10px; border-radius: 4px; border: 1px solid #DDDDDD; }}
            code {{ font-family: Consolas, monospace; }}
            table {{ border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #DDDDDD; padding: 8px; }}
            th {{ background-color: #E0E0E0; }}
            a {{ color: #0078D7; }}
            del, s {{ color: #777; }} 
            """

        styled_html = f"<style>{style}</style><body>{html_content}</body>"
        text_browser_widget.setHtml(styled_html)
        
    # --- MODIFIED: Schedule Notification Checker ---
    @Slot()
    def _check_schedule_notifications(self):
        """
        Called by a QTimer every minute to check for upcoming schedule events.
        """
        try:
            today_str = self.current_app_date.toString("yyyy-MM-dd")
            current_time = datetime.now().time()
            
            events_today = get_schedule_events_for_date(today_str)
            if not events_today:
                return # No events to check

            for event in events_today:
                event_id = event['id']
                start_time_str = event['start_time']
                
                try:
                    event_time = time.fromisoformat(start_time_str)
                except ValueError:
                    print(f"Invalid time format in schedule: {start_time_str}")
                    continue
                
                # Get the set of notifications already sent for this event
                sent_windows = self.notified_event_windows.setdefault(event_id, set())
                
                # Calculate time difference in minutes
                time_diff_seconds = (datetime.combine(date.today(), event_time) - 
                                     datetime.combine(date.today(), current_time)).total_seconds()
                minutes_until_event = time_diff_seconds / 60
                
                # --- NEW: Loop through all notification windows ---
                for window_minutes in self.SCHEDULE_NOTIFY_WINDOWS:
                    
                    # Check if this window is in range AND has not been sent
                    
                    # Special case for "0 minutes" (at start time)
                    # We give it a 1-minute grace period *after* start time
                    # in case the timer ticks at 08:00:01 for an 08:00:00 event.
                    is_in_window = False
                    if window_minutes == 0:
                        if -1 < minutes_until_event <= 0:
                            is_in_window = True
                    else:
                        if window_minutes - 1 < minutes_until_event <= window_minutes:
                            is_in_window = True

                    if is_in_window and window_minutes not in sent_windows:
                        
                        # --- Create notification message ---
                        title = ""
                        message = ""
                        if window_minutes == 0:
                            title = "Event Starting Now"
                            message = f"{event['title']} is starting now at {start_time_str}."
                        else:
                            title = f"Event Starting in {window_minutes} Minutes"
                            message = f"{event['title']} is starting at {start_time_str}."
                        
                        print(f"[Notification] Sending: {title}")
                        self._show_notification(title, message)
                        QApplication.beep() 
                        
                        # Add to set to prevent re-notifying for this window
                        sent_windows.add(window_minutes)

        except Exception as e:
            print(f"Error checking schedule notifications: {e}")
    # --- END MODIFIED ---

    # --- Reusable automation runner (added for bugfix) ---
    def run_automations_for_event(self, event_title, event_date_str):
        """
        Checks a specific event title and date against all automation rules
        and runs any matching actions.
        Returns True if actions were run, False otherwise.
        """
        if not event_title:
            return False
            
        print(f"[Automation] Checking event '{event_title}' for date {event_date_str}...")
        actions_run = False
        try:
            all_rules = get_automations()
            if not all_rules:
                return False # No rules to run

            rules_map = {rule['trigger_title'].lower(): rule for rule in all_rules}
            event_title_lower = event_title.lower()

            if event_title_lower in rules_map:
                rule = rules_map[event_title_lower]
                automation_id = rule['id']
                print(f"[Automation] MATCH FOUND: Rule '{rule['rule_name']}'")

                actions = get_actions_for_automation(automation_id)
                if not actions:
                    print(f"[Automation] Rule found, but it has no actions.")
                    return False

                created_task_ids = []
                created_event_ids = []

                # Run task actions
                task_actions = [a for a in actions if a['action_type'] == 'ensure_task_link']
                for action in task_actions:
                    task_id = self._execute_automation_action(action, event_date_str, automation_id)
                    if task_id:
                        created_task_ids.append(task_id)
                        actions_run = True

                # Run schedule actions
                schedule_actions = [a for a in actions if a['action_type'] == 'create_schedule_block']
                for action in schedule_actions:
                    event_id = self._execute_automation_action(action, event_date_str, automation_id)
                    if event_id:
                        created_event_ids.append(event_id)
                        actions_run = True

                # Link tasks to events
                if created_task_ids and created_event_ids:
                    print(f"[Automation] Linking {len(created_task_ids)} task(s) to {len(created_event_ids)} event(s).")
                    for task_id in created_task_ids:
                        for event_id in created_event_ids:
                            try:
                                link_task_to_event(task_id, event_id)
                                print(f"[Automation]   > Linked task {task_id} to event {event_id}")
                            except Exception as e:
                                print(f"[Automation]   > FAILED to link task {task_id} to event {event_id}: {e}")

                if actions_run:
                    print(f"[Automation] Actions completed for '{event_title}'. Refreshing UI.")
                    # Trigger a refresh of all tabs that need it
                    self._on_task_data_changed() 

        except Exception as e:
            QMessageBox.critical(self, "Automation Error", f"Error during on-demand automation: {e}")
            
        return actions_run

    def _run_startup_automations(self):
        """ Checks today's events and runs any matching automations. """
        today_str = datetime.now().strftime("%Y-m-%d")
        
        last_run = get_app_state('last_automation_run_date')
        if last_run == today_str:
            print(f"[Automation] Automations already run for {today_str}. Skipping.")
            return
            
        print(f"[Automation] Running startup automations for {today_str}...")
        
        try:
            events_today = get_calendar_events_for_date(today_str)
            if not events_today:
                print("[Automation] No calendar events scheduled for today.")
                set_app_state('last_automation_run_date', today_str)
                return

            print(f"[Automation] Checking {len(events_today)} event(s) for today...")
            
            actions_run = False
            for event in events_today:
                # Use our new reusable function
                if self.run_automations_for_event(event.get('title', ''), today_str):
                    actions_run = True
                        
            set_app_state('last_automation_run_date', today_str)
            print("[Automation] Startup automation run complete.")
            
            if actions_run:
                # We still need to refresh if startup actions ran
                self._on_task_data_changed() 

        except Exception as e:
            QMessageBox.critical(self, "Automation Error", f"Error during startup automations: {e}")
            
    def _execute_automation_action(self, action, date_str, automation_id):
        """ 
        Executes a single automation action for a specific date.
        Returns the ID of the newly created item, or None.
        """
        action_type = action.get('action_type')
        
        try:
            if action_type == 'ensure_task_link':
                desc = action.get('param1')
                if not desc: 
                    print("[Automation]   > Skipping task action: No description (param1) provided.")
                    return None

                # --- FIX: Find task by automation_id *AND* description ---
                all_tasks = get_all_tasks()
                existing_task = next((t for t in all_tasks 
                                      if t.get('created_by_automation_id') == automation_id 
                                      and t.get('description') == desc
                                      and t.get('status') == 'pending'), None)

                if existing_task:
                    task_id = existing_task['id']
                    print(f"[Automation]   > Found existing task: '{desc}' (ID: {task_id}).")
                else:
                    print(f"[Automation]   > Creating new task: '{desc}'")
                    new_task = {
                        "id": str(uuid.uuid4()),
                        "description": desc,
                        "status": "pending",
                        "date_added": date_str,
                        "deadline": None,
                        "priority": action.get('param2', 'Medium'), 
                        "category": action.get('param3', 'Automation'), 
                        "notes": "Auto-generated by automation rule.",
                        "created_by_automation_id": automation_id,
                        "show_mode": "auto", # Default show mode
                        "parent_task_id": None # Always create as top-level
                    }
                    task_id = add_task(new_task)
                    if task_id:
                         print(f"[Automation]   > New task created with ID: {task_id}")
                    else:
                         print(f"[Automation]   > FAILED to create new task.")
                         return None
                
                # Regardless of new or found, add today to its show dates
                if task_id:
                    add_task_show_date(task_id, date_str)
                    print(f"[Automation]   > Ensured task {task_id} will show on {date_str}.")
                    return task_id
                return None

            elif action_type == 'create_schedule_block':
                title = action.get('param1')
                start_time = action.get('param2')
                end_time = action.get('param3')
                
                if title and start_time and end_time:
                    new_event = {
                        'id': str(uuid.uuid4()),
                        'date': date_str,
                        'title': title,
                        'start_time': start_time,
                        'end_time': end_time,
                        'color': "#6A1B9A" # Automation color
                    }
                    new_event_id = add_schedule_event(new_event) 
                    print(f"[Automation]   > Created schedule block '{title}' at {start_time}. ID: {new_event_id}")
                    return new_event_id
                else:
                    print(f"[Automation]   > Skipping schedule block: Missing params.")
        
        except Exception as e:
            print(f"[Automation]   > ERROR executing action {action_type}: {e}")
        
        return None