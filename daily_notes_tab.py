import sys
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QTextEdit, QMessageBox,
    QHBoxLayout, QPushButton, QDateEdit, QLabel
)
from PySide6.QtGui import (
    QFont, QTextCharFormat, QTextListFormat
)
from PySide6.QtCore import QDate # <-- NEW IMPORT

from app.core.database import (
    save_daily_note, get_daily_note,
    get_completed_tasks_for_date, get_focus_logs_for_date # <-- NEW IMPORTS
)

# --- Daily Notes Tab Widget ---
class DailyNotesTab(QWidget):
    """
    A self-contained widget for the "Daily Notes" tab.
    Manages its own UI, toolbar, and loading/saving logic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Setup UI ---
        self._setup_ui()

        # --- Load Initial Data ---
        self._load_current_note()

    def _setup_ui(self):
        """Builds the UI for this tab."""
        layout = QVBoxLayout(self) 
        
        # Add a toolbar
        self.notes_toolbar = QToolBar("Notes Toolbar")
        layout.addWidget(self.notes_toolbar)
        
        self.action_bold = self.notes_toolbar.addAction("Bold")
        self.action_bold.setCheckable(True)
        self.action_bold.triggered.connect(lambda: self.notes_editor.setFontWeight(QFont.Weight.Bold if self.action_bold.isChecked() else QFont.Weight.Normal))

        self.action_italic = self.notes_toolbar.addAction("Italic")
        self.action_italic.setCheckable(True)
        self.action_italic.triggered.connect(lambda: self.notes_editor.setFontItalic(self.action_italic.isChecked()))

        self.action_underline = self.notes_toolbar.addAction("Underline")
        self.action_underline.setCheckable(True)
        self.action_underline.triggered.connect(lambda: self.notes_editor.setFontUnderline(self.action_underline.isChecked()))

        self.action_bullet = self.notes_toolbar.addAction("Bullets")
        self.action_bullet.triggered.connect(self._format_bullet_list)
        
        # --- NEW: Daily Review Section ---
        review_layout = QHBoxLayout()
        review_layout.addWidget(QLabel("Generate Review for:"))
        
        self.review_date_edit = QDateEdit()
        self.review_date_edit.setCalendarPopup(True)
        self.review_date_edit.setDate(QDate.currentDate().addDays(-1)) # Default to yesterday
        
        # --- THIS IS THE FIX ---
        self.review_date_edit.setDisplayFormat("dd/MM/yyyy")
        # --- END OF FIX ---
        
        review_layout.addWidget(self.review_date_edit)
        
        generate_review_btn = QPushButton("Generate Review")
        generate_review_btn.clicked.connect(self._generate_daily_review)
        review_layout.addWidget(generate_review_btn)
        review_layout.addStretch()
        
        layout.addLayout(review_layout)
        # --- END NEW ---
        
        self.notes_editor = QTextEdit()
        self.notes_editor.setPlaceholderText("Start writing your notes for today...")
        self.notes_editor.currentCharFormatChanged.connect(self._update_format_buttons)
        
        layout.addWidget(self.notes_editor, 1) # Add editor below toolbar

    def _load_current_note(self):
        """Loads the note for today into the editor."""
        if not hasattr(self, 'notes_editor'):
            return 
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        content = get_daily_note(today_str) or "" 
        
        self.notes_editor.blockSignals(True) 
        if not content:
             self.notes_editor.clear()
             self.notes_editor.setCurrentCharFormat(QTextCharFormat())
             self.notes_editor.setPlaceholderText("Start writing notes...")
        else:
             self.notes_editor.setHtml(content)
        self.notes_editor.blockSignals(False)

    def _save_current_note(self):
        """Saves the current content of the editor."""
        if not hasattr(self, 'notes_editor'):
            return 
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        content = self.notes_editor.toHtml()
        
        # Avoid saving if it's just the default placeholder
        if content.startswith("<!DOCTYPE HTML"):
            if "</body></html>" in content and self.notes_editor.toPlainText().strip() == "":
                 content = ""

        try:
            save_daily_note(today_str, content)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error saving note: {e}")

    def _update_format_buttons(self, format):
        """Updates the toolbar button states based on cursor format."""
        self.action_bold.setChecked(format.fontWeight() == QFont.Weight.Bold)
        self.action_italic.setChecked(format.fontItalic())
        self.action_underline.setChecked(format.fontUnderline())

    def _format_bullet_list(self):
        """Applies bullet formatting to the selected text."""
        cursor = self.notes_editor.textCursor()
        # ***FIX: Use QTextListFormat.ListDisc for correct bullet points***
        cursor.createList(QTextListFormat.ListDisc)
        
    # --- NEW: Daily Review Methods ---
    
    def _generate_daily_review(self):
        """Fetches data for the selected date and appends it to the note."""
        review_qdate = self.review_date_edit.date()
        review_date_str = review_qdate.toString("yyyy-MM-dd")
        
        review_html = f"<h2>Daily Review for {review_date_str}</h2>"
        
        try:
            # 1. Get Completed Tasks
            completed_tasks = get_completed_tasks_for_date(review_date_str)
            review_html += "<h3>Tasks Completed</h3>"
            if not completed_tasks:
                review_html += "<ul><li>No tasks completed.</li></ul>"
            else:
                review_html += "<ul>"
                for task in completed_tasks:
                    review_html += f"<li>{task['description']}</li>"
                review_html += "</ul>"
                
            # 2. Get Focus Sessions
            focus_logs = get_focus_logs_for_date(review_date_str)
            review_html += "<h3>Focus Sessions Logged</h3>"
            if not focus_logs:
                review_html += "<ul><li>No focus sessions logged.</li></ul>"
            else:
                review_html += "<ul>"
                for log in focus_logs:
                    duration = log['duration_minutes']
                    task_desc = log['task_description']
                    
                    if log['session_type'] == 'break':
                        review_html += f"<li>Break ({duration}m)</li>"
                    else:
                        review_html += f"<li>{task_desc} ({duration}m)</li>"
                review_html += "</ul>"
            
            # 3. Add section for thoughts
            review_html += "<h3>My Thoughts</h3>"
            review_html += "<p>...</p><br>"
            
            # Append to the editor
            self.notes_editor.moveCursor(self.notes_editor.textCursor().MoveOperation.End)
            self.notes_editor.insertHtml(review_html)
            self.notes_editor.insertHtml("<br>") # Add extra space
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not generate review: {e}")
    # --- END NEW ---