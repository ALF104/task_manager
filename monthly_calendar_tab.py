import sys
from datetime import datetime, time, date

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QCalendarWidget, QMessageBox
)
from PySide6.QtGui import (
    QFont, QColor, QTextCharFormat
)
from PySide6.QtCore import (
    Qt, QDate, Signal
)

# --- Import from our new structure ---
from app.core.database import (
    get_calendar_events_for_month, get_tasks_for_month
)

from app.widgets.dialogs_schedule import (
    CalendarDateDialog
)

# --- Monthly Calendar Tab Widget ---
class MonthlyCalendarTab(QWidget):
    """
    A self-contained widget for the "Monthly Calendar" tab.
    Manages its own UI, date marking, and event dialogs.
    """
    # Signal to tell MainWindow to refresh other tabs
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Setup UI ---
        self._setup_ui()
        
        # --- Load Initial Data ---
        self.update_display()

    def _setup_ui(self):
        """Builds the UI for this tab."""
        layout = QVBoxLayout(self)
        
        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setGridVisible(True) 
        # When user navigates to a new month/year, re-mark the dates
        self.calendar_widget.currentPageChanged.connect(self._mark_calendar_dates)
        # When user clicks a date, open the dialog for it
        self.calendar_widget.clicked.connect(self._open_calendar_date_dialog)
        
        layout.addWidget(self.calendar_widget, 1) # Calendar fills the tab

    def update_display(self):
        """Public method to trigger a calendar refresh."""
        self._mark_calendar_dates()

    def _mark_calendar_dates(self):
        """Applies formatting to calendar dates based on events and deadlines."""
        if not hasattr(self, 'calendar_widget'):
            return # Not ready yet
            
        year = self.calendar_widget.yearShown()
        month = self.calendar_widget.monthShown()
        
        default_format = QTextCharFormat() 
        self.calendar_widget.setDateTextFormat(QDate(), default_format) # Clears all
        
        # --- Define formats ---
        # ***CHANGE***: Use colored, bold text instead of background
        deadline_format = QTextCharFormat()
        deadline_format.setFontWeight(QFont.Weight.Bold)
        deadline_format.setForeground(QColor("#C62828")) # Red
        deadline_format.setToolTip("Task Deadline") 

        rota_format = QTextCharFormat()
        rota_format.setFontWeight(QFont.Weight.Bold)
        rota_format.setForeground(QColor("#1F6AA5")) # Blue
        rota_format.setToolTip("Planned Event")
        
        date_formats = {} # To combine tooltips

        try:
            # Get Rota Events
            rota_events = get_calendar_events_for_month(year, month)
            for event in rota_events:
                event_date_str = event.get('date')
                if event_date_str:
                    q_date = QDate.fromString(event_date_str, "yyyy-MM-dd")
                    if q_date.isValid() and q_date.year() == year and q_date.month() == month:
                        if q_date not in date_formats:
                            date_formats[q_date] = {'format': QTextCharFormat(rota_format), 'tooltips': []}
                        title = event.get('title')
                        start_time = event.get('start_time')
                        tooltip_text = f"Event: {title} ({start_time})" if start_time else f"Event: {title}"
                        date_formats[q_date]['tooltips'].append(tooltip_text)

            # Get Task Deadlines
            tasks_in_month = get_tasks_for_month(year, month)
            for task in tasks_in_month:
                deadline_date_str = task.get('deadline')
                if deadline_date_str:
                     q_date = QDate.fromString(deadline_date_str, "yyyy-MM-dd")
                     if q_date.isValid() and q_date.year() == year and q_date.month() == month:
                        if q_date not in date_formats:
                             date_formats[q_date] = {'format': QTextCharFormat(deadline_format), 'tooltips': []}
                        else:
                             # ***CHANGE***: Use colored, bold text for combined
                             date_formats[q_date]['format'].setFontWeight(QFont.Weight.Bold)
                             date_formats[q_date]['format'].setForeground(QColor("#6A1B9A")) # Purple
                        
                        date_formats[q_date]['tooltips'].append(f"Deadline: {task.get('description', '')}")

            # Apply all formats
            for q_date, data in date_formats.items():
                data['format'].setToolTip("\n".join(data['tooltips']))
                self.calendar_widget.setDateTextFormat(q_date, data['format'])
                          
        except Exception as e: 
            QMessageBox.critical(self, "Error", f"Error marking calendar dates: {e}")
            
    def _open_calendar_date_dialog(self, q_date):
        """Opens the dialog to manage events for a specific date."""
        dialog = CalendarDateDialog(q_date, self)
        # Connect the dialog's signal to our own methods
        dialog.events_changed.connect(self.update_display) # Refresh this calendar
        dialog.events_changed.connect(self.data_changed)  # Tell main window to refresh
        dialog.exec()