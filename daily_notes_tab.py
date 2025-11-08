import sys
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QTextEdit, QMessageBox
)
from PySide6.QtGui import (
    QFont, QTextCharFormat, QTextListFormat
)
from app.core.database import (
    save_daily_note, get_daily_note
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
        
        self.notes_editor = QTextEdit()
        self.notes_editor.setPlaceholderText("Start writing your notes for today...")
        self.notes_editor.currentCharFormatChanged.connect(self._update_format_buttons)
        
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