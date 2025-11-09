import sys
from datetime import datetime, timedelta, time, date

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, 
    QGraphicsLineItem, QGraphicsTextItem, QMessageBox
)
from PySide6.QtGui import (
    QFont, QPainter, QColor, QPen
)
from PySide6.QtCore import (
    Qt, QTimer, QTime, QDate, QEvent, Signal, Slot
)

# --- Import from our new structure ---
from app.core.database import (
    get_schedule_events_for_date, add_schedule_event
)

from app.widgets.graphics_items import (
    ScheduleEventItem
)

from app.widgets.dialogs_schedule import (
    ScheduleEventDialog
)

# --- Constants ---
SCHEDULE_START_HOUR = 6   # <-- REVERTED (was 0)
SCHEDULE_END_HOUR = 23   
SCHEDULE_HOUR_HEIGHT = 60 
SCHEDULE_TIME_COLUMN_WIDTH = 70 
SCHEDULE_EVENT_LEFT_MARGIN = 5
SCHEDULE_EVENT_RIGHT_MARGIN = 5
SCHEDULE_HEADER_HEIGHT = 30 # Space above timeline

# --- Daily Schedule Tab Widget ---
class DailyScheduleTab(QWidget):
    """
    A self-contained widget for the "Daily Schedule" tab.
    Manages its own UI, QGraphicsScene, and event logic.
    """
    # Signal to tell MainWindow to refresh other tabs
    data_changed = Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Member Variables ---
        self.current_date = QDate.currentDate()
        self.theme_mode = 'dark' # Default theme

        # --- Setup UI ---
        self._setup_ui()

    def _setup_ui(self):
        """Builds the UI for this tab."""
        layout = QVBoxLayout(self)
        
        self.schedule_view = QGraphicsView()
        self.schedule_scene = QGraphicsScene()
        self.schedule_view.setScene(self.schedule_scene)
        self.schedule_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.schedule_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.schedule_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.schedule_view)
        
        # Install event filter to catch double clicks on the viewport
        self.schedule_view.viewport().installEventFilter(self)
        # Re-draw on resize
        self.schedule_view.viewport().resizeEvent = self._handle_schedule_resize

    def eventFilter(self, source, event):
        """Catches double-clicks on the schedule's background."""
        if source is self.schedule_view.viewport() and event.type() == QEvent.Type.MouseButtonDblClick:
            item = self.schedule_view.itemAt(event.position().toPoint()) 
            
            schedule_item = None
            while item is not None:
                if isinstance(item, ScheduleEventItem):
                    schedule_item = item
                    break
                item = item.parentItem() # Check parent

            if schedule_item is None:
                # We clicked the background, create a new event
                scene_pos = self.schedule_view.mapToScene(event.position().toPoint())
                self._handle_schedule_background_double_click(scene_pos, self.current_date)
                return True # Event handled
            
        return super().eventFilter(source, event) # Pass other events on

    def _handle_schedule_resize(self, event):
        """Redraws the schedule when the widget is resized."""
        if self.schedule_view.viewport():
            QWidget.resizeEvent(self.schedule_view.viewport(), event) 
        QTimer.singleShot(100, self.refresh_display)

    def refresh_display(self):
        """Public method to clear and redraw the schedule."""
        if not hasattr(self, 'schedule_scene'):
            return 
            
        self.schedule_scene.clear()
        
        try:
            view_width = self.schedule_view.viewport().width()
            if view_width <= 1: 
                 QTimer.singleShot(50, self.refresh_display) # Try again
                 return
        except Exception:
             return # Viewport not available

        self._draw_schedule_timeline(view_width)
        self._draw_schedule_events(view_width)

        total_height = (SCHEDULE_END_HOUR - SCHEDULE_START_HOUR + 1) * SCHEDULE_HOUR_HEIGHT + SCHEDULE_HEADER_HEIGHT
        self.schedule_scene.setSceneRect(0, 0, view_width, total_height)

    def _draw_schedule_timeline(self, view_width):
        """Draws the hour lines and times."""
        # ***CHANGE***: Use the stored theme_mode
        is_dark_theme = self.theme_mode == 'dark'
        
        line_color = QColor("#4A4D50") if is_dark_theme else QColor("#DDDDDD")
        text_color = QColor("white") if is_dark_theme else QColor("black")
        font = QFont(); font.setPointSize(9)

        for hour in range(SCHEDULE_START_HOUR, SCHEDULE_END_HOUR + 1):
            y = (hour - SCHEDULE_START_HOUR) * SCHEDULE_HOUR_HEIGHT + SCHEDULE_HEADER_HEIGHT
            
            time_dt = time(hour, 0)
            time_str = time_dt.strftime("%I:%M %p").lstrip('0')
            time_text = QGraphicsTextItem(time_str)
            time_text.setDefaultTextColor(text_color)
            time_text.setFont(font)
            text_height = time_text.boundingRect().height()
            time_text.setPos(5, y - text_height / 2) 
            self.schedule_scene.addItem(time_text)

            line = QGraphicsLineItem(SCHEDULE_TIME_COLUMN_WIDTH, y, view_width, y)
            line.setPen(QPen(line_color))
            self.schedule_scene.addItem(line)

            if hour < SCHEDULE_END_HOUR:
                y_half = y + SCHEDULE_HOUR_HEIGHT / 2
                half_line = QGraphicsLineItem(SCHEDULE_TIME_COLUMN_WIDTH + 10, y_half, view_width, y_half)
                pen = QPen(line_color); pen.setStyle(Qt.PenStyle.DashLine)
                half_line.setPen(pen)
                self.schedule_scene.addItem(half_line)

    def _draw_schedule_events(self, view_width):
        """Fetches and draws all event blocks for the current_date."""
        date_str = self.current_date.toString("yyyy-MM-dd")
        events = get_schedule_events_for_date(date_str)

        event_area_width = max(0, view_width - SCHEDULE_TIME_COLUMN_WIDTH - SCHEDULE_EVENT_LEFT_MARGIN - SCHEDULE_EVENT_RIGHT_MARGIN)

        for event_data in events:
            try:
                y_start = self._time_to_y(event_data['start_time'])
                y_end = self._time_to_y(event_data['end_time'])
                
                height = y_end - y_start
                if height <= 0: 
                    print(f"Skipping event '{event_data.get('title')}' due to zero/negative height ({height})")
                    continue 

                event_item = ScheduleEventItem(event_data, y_start, y_end, event_area_width, 
                                               self._open_schedule_event_dialog)
                event_item.setPos(SCHEDULE_TIME_COLUMN_WIDTH + SCHEDULE_EVENT_LEFT_MARGIN, y_start) 
                self.schedule_scene.addItem(event_item)

            except Exception as e:
                print(f"Error drawing event '{event_data.get('title')}': {e}")
                
    def _time_to_y(self, time_str):
        """Converts a 'HH:MM' time string to a Y-coordinate."""
        try:
             t = time.fromisoformat(time_str)
             total_minutes_from_start = (t.hour - SCHEDULE_START_HOUR) * 60 + t.minute
             y = (total_minutes_from_start / 60) * SCHEDULE_HOUR_HEIGHT + SCHEDULE_HEADER_HEIGHT
             return y
        except ValueError:
             print(f"Invalid time format for Y conversion: {time_str}")
             return SCHEDULE_HEADER_HEIGHT 

    def _y_to_time(self, y):
        """Converts a Y-coordinate back to a 'HH:MM' string, snapping to 15 mins."""
        y_relative = max(0, y - SCHEDULE_HEADER_HEIGHT)
        total_minutes_from_start = (y_relative / SCHEDULE_HOUR_HEIGHT) * 60
        snapped_total_minutes = round(total_minutes_from_start / 15) * 15
        hours = SCHEDULE_START_HOUR + (snapped_total_minutes // 60)
        minutes = snapped_total_minutes % 60
        hours = max(SCHEDULE_START_HOUR, min(SCHEDULE_END_HOUR, hours))
        if hours == SCHEDULE_END_HOUR:
             minutes = 0 
        return f"{int(hours):02d}:{int(minutes):02d}"

    def _handle_schedule_background_double_click(self, scene_pos, q_date):
        """Creates a new 1-hour event block at the clicked Y-position."""
        start_time_str = self._y_to_time(scene_pos.y())
        try:
             start_dt = datetime.strptime(start_time_str, "%H:%M")
             end_dt = start_dt + timedelta(hours=1)
             end_hour_dt = datetime.strptime(f"{SCHEDULE_END_HOUR}:00", "%H:%M")
             if end_dt > end_hour_dt: end_dt = end_hour_dt
             end_time_str = end_dt.strftime("%H:%M")
        except ValueError:
             end_time_str = "10:00" 
             
        self._open_schedule_event_dialog(date_str=q_date.toString("yyyy-MM-dd"), 
                                         start_time=start_time_str, end_time=end_time_str)

    def _open_schedule_event_dialog(self, event_data=None, date_str=None, start_time=None, end_time=None):
        """Opens the ScheduleEventDialog."""
        
        if event_data:
            date_str_to_use = event_data.get('date', self.current_date.toString("yyyy-MM-dd"))
        else:
            date_str_to_use = date_str if date_str else self.current_date.toString("yyyy-MM-dd")
            
        dialog = ScheduleEventDialog(date_str_to_use, event_data, start_time, end_time, self)
        if dialog.exec(): 
             self.refresh_display() # Refresh this tab
             self.data_changed.emit() # Tell main window to refresh other tabs

    # --- Public Slots ---
    @Slot(QDate)
    def set_current_date(self, q_date):
        """Public slot to update the date this tab should display."""
        self.current_date = q_date
        # Refresh the display if this tab is visible
        if self.isVisible():
            self.refresh_display()

    # ***CHANGE***: Add the new set_theme method
    @Slot(str)
    def set_theme(self, theme_mode):
        """Public slot to update the timer's theme mode."""
        print(f"--- SCHEDULE: Setting theme to '{theme_mode}' ---")
        self.theme_mode = theme_mode.lower()
        self.refresh_display() # Redraw with new colors