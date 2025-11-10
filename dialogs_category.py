import uuid
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QDialogButtonBox, QMessageBox,
    QInputDialog
)
from PySide6.QtCore import Qt, Signal # <-- Added Signal
from app.core.database import (
    get_categories, add_category, delete_category, category_exists
)

class ManageCategoriesDialog(QDialog):
    """
    Dialog for adding, removing, and re-ordering task categories.
    """
    # Signal to tell other parts of the app to reload their categories
    categories_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Task Categories")
        self.setMinimumSize(350, 400)

        self.layout = QVBoxLayout(self)

        self.layout.addWidget(QLabel("Manage your custom task categories."))

        self.category_list_widget = QListWidget()
        self.category_list_widget.setToolTip("Drag and drop to re-order (feature coming soon).")
        self.layout.addWidget(self.category_list_widget)

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add...")
        add_btn.clicked.connect(self._add_category)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_category)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(delete_btn)
        self.layout.addLayout(button_layout)

        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.rejected.connect(self.reject)
        self.layout.addWidget(close_button)

        self._load_categories()

    def _load_categories(self):
        """Reloads all categories from the database into the list."""
        self.category_list_widget.clear()
        try:
            categories = get_categories()
            for cat in categories:
                item = QListWidgetItem(cat['name'])
                item.setData(Qt.ItemDataRole.UserRole, cat['id'])
                
                # Make "General" non-deletable
                if cat['name'].lower() == 'general':
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                
                self.category_list_widget.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load categories: {e}")

    def _add_category(self):
        """Adds a new category."""
        text, ok = QInputDialog.getText(self, "Add Category", "Enter new category name:")
        if ok and text:
            text = text.strip()
            if not text:
                return
            
            # Check if category already exists
            if category_exists(text):
                QMessageBox.warning(self, "Duplicate", f"A category named '{text}' already exists.")
                return

            try:
                add_category(text)
                self._load_categories()
                self.categories_updated.emit() # Tell the app to update
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add category: {e}")

    def _delete_category(self):
        """Deletes the selected category."""
        current_item = self.category_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a category to delete.")
            return

        cat_id = current_item.data(Qt.ItemDataRole.UserRole)
        cat_name = current_item.text()

        if cat_name.lower() == 'general':
            QMessageBox.warning(self, "Cannot Delete", "The 'General' category cannot be deleted.")
            return

        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Are you sure you want to delete the category '{cat_name}'?\n"
                                   "All tasks using this category will be set to 'General'.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_category(cat_id)
                self._load_categories()
                self.categories_updated.emit() # Tell the app to update
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete category: {e}")

# We need to add this to the top of dialogs_main.py
# from app.widgets.dialogs_category import ManageCategoriesDialog