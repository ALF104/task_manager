import uuid
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QGraphicsView, QGraphicsScene, QApplication, QMessageBox,
    QGraphicsPathItem, QGraphicsTextItem, QDialog
)
from PySide6.QtGui import (
    QFont, QColor, QPen, QPainter, QPainterPath
)
from PySide6.QtCore import (
    Qt, QRectF, QTimer, Slot
)

# --- CORRECTED IMPORT ---
from app.core.database import get_app_state

# --- Pomodoro Timer Widget ---
class PomodoroTimerWidget(QGroupBox):
    """
    A self-contained widget for the Pomodoro Timer.
    Manages its own UI, state, and timer logic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Member Variables ---
        self.pomodoro_timer = QTimer(self)
        self.pomodoro_timer.timeout.connect(self._countdown)
        self.pomodoro_running = False
        self.pomodoro_cycles = 0
        self.break_cycles = 0
        self.theme_mode = 'dark' # Default theme
        
        # --- Load Settings ---
        self._load_settings_from_db() 

        # --- Setup UI ---
        self._setup_ui() # <-- This creates self.timer_minutes_entry
        
        # --- Init State ---
        self._reset_timer_to_work()

    def _load_settings_from_db(self):
        """Loads timer settings from the database into member variables."""
        try:
            self.work_minutes = int(get_app_state('pomodoro_work_min') or 25)
            self.short_break_minutes = int(get_app_state('pomodoro_short_break_min') or 5)
            self.long_break_minutes = int(get_app_state('pomodoro_long_break_min') or 15)
            self.sessions_before_long_break = int(get_app_state('pomodoro_sessions') or 4)
        except Exception as e:
            print(f"Error loading pomodoro settings, using defaults: {e}")
            # Fallback to defaults
            self.work_minutes = 25
            self.short_break_minutes = 5
            self.long_break_minutes = 15
            self.sessions_before_long_break = 4

    @Slot()
    def reload_settings_and_reset_timer(self):
        """Public slot to reload settings from DB and update the timer."""
        self._load_settings_from_db()
        self._reset_timer_to_work() # Now reset the timer with the new values

    @Slot(str)
    def set_theme(self, theme_mode):
        """Public slot to update the timer's theme mode."""
        print(f"--- TIMER: Setting theme to '{theme_mode}' ---")
        self.theme_mode = theme_mode.lower()
        self._update_timer_display()

    def _setup_ui(self):
        """Builds the UI for the timer widget."""
        main_timer_layout = QVBoxLayout(self)
        
        title_label = QLabel("Pomodoro Timer")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; margin-top: -5px; margin-bottom: 5px; background-color: transparent;")
        main_timer_layout.addWidget(title_label)

        timer_controls_layout = QHBoxLayout()
        main_timer_layout.addLayout(timer_controls_layout)

        self.timer_view = QGraphicsView()
        self.timer_scene = QGraphicsScene()
        self.timer_view.setScene(self.timer_scene)
        self.timer_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.timer_view.setFixedSize(150, 150)
        self.timer_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timer_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timer_view.setStyleSheet("background-color: transparent; border: none;")
        timer_controls_layout.addWidget(self.timer_view)

        controls_stack = QVBoxLayout()
        timer_controls_layout.addLayout(controls_stack)

        timer_input_layout = QHBoxLayout()
        self.timer_minutes_entry = QLineEdit(str(self.work_minutes))
        self.timer_minutes_entry.setFixedWidth(50)
        timer_input_layout.addWidget(self.timer_minutes_entry)
        
        self.work_button = QPushButton("Work")
        self.work_button.clicked.connect(lambda: self._set_timer_preset(self.timer_minutes_entry.text(), "Work"))
        self.break_button = QPushButton("Break")
        self.break_button.clicked.connect(lambda: self._set_timer_preset(self.timer_minutes_entry.text(), "Break"))
        timer_input_layout.addWidget(self.work_button)
        timer_input_layout.addWidget(self.break_button)
        controls_stack.addLayout(timer_input_layout)

        start_pause_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start_timer)
        start_pause_layout.addWidget(self.start_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._pause_timer)
        self.pause_button.setEnabled(False)
        start_pause_layout.addWidget(self.pause_button)
        controls_stack.addLayout(start_pause_layout)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._reset_timer)
        controls_stack.addWidget(self.reset_button)
        
        controls_stack.addStretch()
        self.setFixedSize(self.sizeHint())

    # --- Pomodoro Timer Logic ---
    def _start_timer(self):
        if not self.pomodoro_running and self.timer_seconds > 0:
            self.pomodoro_running = True
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.timer_minutes_entry.setEnabled(False) 
            self.work_button.setEnabled(False) 
            self.break_button.setEnabled(False) 
            self.pomodoro_timer.start(1000)

    def _pause_timer(self):
        if self.pomodoro_running:
             self.pomodoro_running = False
             self.pomodoro_timer.stop()
             self.start_button.setText("Resume")
             self.start_button.setEnabled(True)
             self.pause_button.setEnabled(False)
             self.timer_minutes_entry.setEnabled(True)
             self.work_button.setEnabled(True) 
             self.break_button.setEnabled(True) 

    def _reset_timer(self):
        """Resets the timer to its *current* mode's full time."""
        self._pause_timer() 
        self.timer_seconds = self.total_timer_seconds
        self._update_timer_display()
        self.start_button.setText("Start")
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)

    def _reset_timer_to_work(self):
        """Resets the timer specifically to a full Work session."""
        self._pause_timer()
        self.timer_mode = "Work"
        self.timer_seconds = self.work_minutes * 60
        self.total_timer_seconds = self.work_minutes * 60
        # Check if widget has been created yet
        if hasattr(self, 'timer_minutes_entry'):
            self.timer_minutes_entry.setText(str(self.work_minutes))
        self._update_timer_display()
        self._update_timer_mode_highlight()
        if hasattr(self, 'start_button'):
            self.start_button.setText("Start")
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
        
    def _set_timer_preset(self, minutes_str, mode):
        default_minutes = self.work_minutes if mode == "Work" else self.short_break_minutes
        
        try: 
            minutes = int(minutes_str)
            assert minutes > 0
        except (ValueError, AssertionError): 
            minutes = default_minutes
            self.timer_minutes_entry.setText(str(default_minutes)) 
        
        self._pause_timer()
        self.timer_mode = mode
        self.timer_seconds = minutes * 60
        self.total_timer_seconds = minutes * 60
        self._update_timer_display()
        self.start_button.setText("Start")
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.timer_minutes_entry.setEnabled(True) 
        self.work_button.setEnabled(True)
        self.break_button.setEnabled(True)
        self._update_timer_mode_highlight()

    def _countdown(self):
        if self.pomodoro_running and self.timer_seconds > 0:
            self.timer_seconds -= 1
            self._update_timer_display()
        elif self.timer_seconds == 0:
            self.pomodoro_running = False
            self.pomodoro_timer.stop()
            self.start_button.setText("Start")
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.timer_minutes_entry.setEnabled(True)
            self.work_button.setEnabled(True)
            self.break_button.setEnabled(True)
            
            if self.timer_mode == "Work":
                self.pomodoro_cycles += 1
                if self.pomodoro_cycles % self.sessions_before_long_break == 0:
                    self._show_long_break_prompt()
                else: 
                    self._set_timer_preset(str(self.short_break_minutes), "Break")
                    QMessageBox.information(self, "Pomodoro Complete", f"Time for a short break ({self.short_break_minutes} min)!")
            elif self.timer_mode == "Break":
                self.break_cycles += 1
                self._set_timer_preset(str(self.work_minutes), "Work") 
                QMessageBox.information(self, "Break Over", "Time to get back to work!")
            
            self._update_timer_display() 
            self._play_sound() 
            
    def _update_timer_display(self):
        # Don't try to draw if the scene hasn't been created yet
        if not hasattr(self, 'timer_scene'):
            return
            
        self.timer_scene.clear()
        
        diameter = 130
        pen_width = 10
        scene_size = 150
        rect = QRectF((scene_size - diameter)/2, (scene_size - diameter)/2, diameter, diameter)
        
        # ***CHANGE***: Use the stored theme_mode
        is_dark_theme = self.theme_mode == 'dark'
            
        bg_track_color = QColor("#565B5E") if is_dark_theme else QColor("#DDDDDD")
        text_color = QColor("white") if is_dark_theme else QColor("black")
        cycle_text_color = QColor("gray") if is_dark_theme else QColor("#555555")

        # Background track
        bg_pen = QPen(bg_track_color, 2)
        self.timer_scene.addEllipse(rect, bg_pen)

        progress = 0
        if self.total_timer_seconds > 0:
             progress = max(0.0, min(1.0, self.timer_seconds / self.total_timer_seconds))
        
        if progress >= 0.999:
             span_angle = -359.9 * 16
        else:
             span_angle = -progress * 360 * 16 
        
        progress_color = QColor("#1F6AA5") if self.timer_mode == "Work" else QColor("#2AD577")
        progress_pen = QPen(progress_color, pen_width)
        progress_pen.setCapStyle(Qt.PenCapStyle.FlatCap) 

        path = QPainterPath()
        path.arcMoveTo(rect, 90)
        path.arcTo(rect, 90, span_angle / 16.0)
        
        arc_item = QGraphicsPathItem(path)
        arc_item.setPen(progress_pen)
        self.timer_scene.addItem(arc_item)
        
        mins, secs = divmod(self.timer_seconds, 60)
        time_text = f"{mins:02d}:{secs:02d}"
        
        text_item = QGraphicsTextItem(time_text)
        text_item.setDefaultTextColor(text_color) # Use theme-aware color
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        text_item.setFont(font)
        
        text_rect = text_item.boundingRect()
        text_x = (scene_size - text_rect.width()) / 2
        text_y = (scene_size - text_rect.height()) / 2 - 12
        text_item.setPos(text_x, text_y)
        self.timer_scene.addItem(text_item)
        
        cycle_text = f"Work: {self.pomodoro_cycles} | Breaks: {self.break_cycles}"
        cycle_text_item = QGraphicsTextItem(cycle_text)
        cycle_text_item.setDefaultTextColor(cycle_text_color) # Use theme-aware color
        font = QFont(); font.setPointSize(10);
        cycle_text_item.setFont(font)
        
        cycle_rect = cycle_text_item.boundingRect()
        cycle_x = (scene_size - cycle_rect.width()) / 2
        cycle_y = text_y + text_rect.height() - 5
        cycle_text_item.setPos(cycle_x, cycle_y)
        self.timer_scene.addItem(cycle_text_item)
    
    def _update_timer_mode_highlight(self):
        # Don't try to update if widgets don't exist yet
        if not hasattr(self, 'work_button'):
            return
            
        active_style = "background-color: #3B8ED0;"
        inactive_style = "background-color: #1F6AA5;"
        
        if self.timer_mode == "Work":
            self.work_button.setStyleSheet(active_style)
            self.break_button.setStyleSheet(inactive_style)
        else:
            self.work_button.setStyleSheet(inactive_style)
            self.break_button.setStyleSheet(active_style)
        
    def _show_long_break_prompt(self):
         reply = QMessageBox.question(self, 'Long Break Time!', f"Completed {self.sessions_before_long_break} sessions. Start a long break ({self.long_break_minutes} min)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes) 
         if reply == QMessageBox.StandardButton.Yes: 
             self._set_timer_preset(str(self.long_break_minutes), "Break")
             self._start_timer() 
         else: 
             self._set_timer_preset(str(self.work_minutes), "Work")
    
    def _play_sound(self):
        QApplication.beep()