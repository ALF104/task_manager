import uuid
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QMessageBox, QInputDialog, QTreeWidget,
    QTreeWidgetItem, QSplitter, QToolBar,
    QLineEdit, QTreeWidgetItemIterator # <-- NEW IMPORT
)
from PySide6.QtGui import (
    QFont, QTextCharFormat, QColor, QTextListFormat  # Import QTextListFormat
)
from PySide6.QtCore import (
    Qt, Signal
)

# --- Import from our new structure ---
from app.core.database import (
    add_kb_topic, get_kb_topics_by_parent, update_kb_topic_note,
    delete_kb_topic, get_kb_topic_note,
    get_all_kb_topics_map, search_kb_topics # <-- NEW IMPORTS
)

# --- Knowledge Base Tab Widget ---
class KnowledgeBaseTab(QWidget):
    """
    A self-contained widget for the "Knowledge Base" tab.
    Manages its own UI, topic tree, and note editor.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Member Variables ---
        self.current_topic_id = None
        self.is_loading = False # Flag to prevent saving while loading
        self.all_topics_map = {} # <-- NEW: Cache for all topics
        self.current_search_text = "" # <-- NEW: Store search state
        self.original_matching_ids = set() # <-- NEW: For highlighting

        # --- Setup UI ---
        # All UI elements are created here
        self._setup_ui() 

        # --- Load Initial Data ---
        self._load_full_topic_map_and_tree() # <-- MODIFIED: Load cache first

    # --- Formatting Helpers ---
    # These methods are defined *before* _setup_ui connects to them
    # to prevent AttributeError on launch.

    def _update_format_buttons(self, format):
        """Updates the toolbar button states based on cursor format."""
        if not hasattr(self, 'action_bold'): return # Exit if UI not ready
        self.action_bold.setChecked(format.fontWeight() == QFont.Weight.Bold)
        self.action_italic.setChecked(format.fontItalic())
        self.action_underline.setChecked(format.fontUnderline())

    def _format_bullet_list(self, checked=False):
        """
        Applies bullet formatting to the selected text.
        Accepts 'checked' argument from the signal, but doesn't use it.
        """
        if not hasattr(self, 'note_editor'): return # Exit if UI not ready
        
        cursor = self.note_editor.textCursor()
        
        # --- THIS IS THE FIX ---
        # Use QTextListFormat for lists, not QTextCharFormat
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.ListDisc) # Set style to bullet points
        cursor.createList(list_format)
        # --- END OF FIX ---

    # --- Main UI Setup ---

    def _setup_ui(self):
        """Builds the UI for this tab."""
        layout = QHBoxLayout(self)
        
        # Use a splitter to make sections resizable
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter)

        # --- Left Side: Topic Tree ---
        tree_widget = QWidget()
        tree_layout = QVBoxLayout(tree_widget)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- NEW: Search Bar ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search topics and notes...")
        self.search_bar.textChanged.connect(self._on_search_changed)
        tree_layout.addWidget(self.search_bar)
        # --- END NEW ---
        
        self.topic_tree = QTreeWidget()
        self.topic_tree.setHeaderLabel("Topics")
        self.topic_tree.setHeaderHidden(True) 
        self.topic_tree.itemSelectionChanged.connect(self._on_topic_selected)
        tree_layout.addWidget(self.topic_tree)
        
        tree_button_layout = QHBoxLayout()
        add_topic_button = QPushButton("Add Topic")
        add_topic_button.clicked.connect(self._add_topic)
        add_subtopic_button = QPushButton("Add Subtopic")
        add_subtopic_button.clicked.connect(self._add_subtopic)
        delete_topic_button = QPushButton("Delete")
        delete_topic_button.clicked.connect(self._delete_topic)
        
        tree_button_layout.addWidget(add_topic_button)
        tree_button_layout.addWidget(add_subtopic_button)
        tree_button_layout.addWidget(delete_topic_button)
        tree_layout.addLayout(tree_button_layout)
        
        splitter.addWidget(tree_widget)

        # --- Right Side: Note Editor ---
        editor_wrapper = QWidget()
        editor_layout = QVBoxLayout(editor_wrapper)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Add Toolbar
        self.notes_toolbar = QToolBar("Knowledge Toolbar")
        editor_layout.addWidget(self.notes_toolbar)

        self.action_bold = self.notes_toolbar.addAction("Bold")
        self.action_bold.setCheckable(True)
        # We use a lambda to handle the 'checked' signal from the button
        self.action_bold.triggered.connect(lambda checked: self.note_editor.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal))

        self.action_italic = self.notes_toolbar.addAction("Italic")
        self.action_italic.setCheckable(True)
        self.action_italic.triggered.connect(lambda checked: self.note_editor.setFontItalic(checked))

        self.action_underline = self.notes_toolbar.addAction("Underline")
        self.action_underline.setCheckable(True)
        self.action_underline.triggered.connect(lambda checked: self.note_editor.setFontUnderline(checked))
        
        self.action_bullet = self.notes_toolbar.addAction("Bullets")
        # Connect to the helper method
        self.action_bullet.triggered.connect(self._format_bullet_list)

        # 2. Add Editor
        self.note_editor = QTextEdit() # Use QTextEdit for rich text
        self.note_editor.setPlaceholderText("Select a topic to view or edit its notes...")
        self.note_editor.textChanged.connect(self._on_note_changed)
        self.note_editor.currentCharFormatChanged.connect(self._update_format_buttons)
        self.note_editor.setEnabled(False) # Start disabled
        editor_layout.addWidget(self.note_editor)
        
        splitter.addWidget(editor_wrapper)
        
        # Set initial sizes for the splitter
        splitter.setSizes([250, 600])

    # --- Data and Logic Methods ---
    
    def _load_full_topic_map_and_tree(self):
        """
        NEW: Caches all topics in a map, then loads the full tree.
        """
        try:
            self.all_topics_map = get_all_kb_topics_map()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load topic map: {e}")
            self.all_topics_map = {}
            
        self._load_topics() # Now, build the tree

    def _load_topics(self, parent_item=None, parent_id=None):
        """Recursively loads topics from the database into the tree."""
        if parent_item is None:
            self.topic_tree.clear()
            parent_item = self.topic_tree.invisibleRootItem()
        
        try:
            # Get children for this parent_id
            # We can use a list comprehension on our cached map for speed
            children = [
                topic for topic in self.all_topics_map.values() 
                if topic.get('parent_id') == parent_id
            ]
            # Sort them by title
            children.sort(key=lambda t: t.get('title', ''))

            for topic in children:
                item = QTreeWidgetItem(parent_item, [topic['title']])
                item.setData(0, Qt.ItemDataRole.UserRole, topic['id']) # Store ID in the item
                # Recursively load children
                self._load_topics(item, topic['id'])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load topics: {e}")

    def _on_topic_selected(self):
        """Handles when a user clicks a topic in the tree."""
        selected_items = self.topic_tree.selectedItems()
        
        # Save previous note before proceeding
        self.save_current_note() 

        if not selected_items:
            self.current_topic_id = None
            self.note_editor.clear()
            self.note_editor.setPlaceholderText("Select a topic to view or edit its notes...")
            self.note_editor.setEnabled(False)
            return

        self.is_loading = True # Set flag to prevent autosave on load
        try:
            item = selected_items[0]
            topic_id = item.data(0, Qt.ItemDataRole.UserRole)
            
            # Load and display the new note
            note_content = get_kb_topic_note(topic_id)
            if note_content:
                self.note_editor.setHtml(note_content)
            else:
                self.note_editor.clear()
                self.note_editor.setPlaceholderText(f"Add notes for {item.text(0)}...")
            
            self.current_topic_id = topic_id
            self.note_editor.setEnabled(True) # Explicitly enable the editor
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load note: {e}")
        finally:
            self.is_loading = False # Unset flag

    def _on_note_changed(self):
        """
        This is a 'debounced' save. It will be called on every keystroke,
        but we will handle the actual saving in `save_current_note` when
        the user clicks away or closes the tab.
        """
        pass # We save when switching topics or tabs

    def save_current_note(self):
        """Saves the note for the currently selected topic to the DB."""
        # Don't save if we're in the middle of loading a new note
        if self.is_loading or self.current_topic_id is None:
            return
            
        try:
            content = self.note_editor.toHtml()
            # Don't save if it's just the placeholder
            if content.startswith("<!DOCTYPE HTML"):
                if "</body></html>" in content and self.note_editor.toPlainText().strip() == "":
                    content = ""
                    
            update_kb_topic_note(self.current_topic_id, content)
            print(f"Saved note for topic {self.current_topic_id}")
            
        except Exception as e:
            print(f"Error saving note for topic {self.current_topic_id}: {e}")
            # Don't show a messagebox, as this saves in the background

    def _add_topic(self):
        """Adds a new top-level topic."""
        text, ok = QInputDialog.getText(self, "Add Topic", "Enter new topic name:")
        if ok and text:
            try:
                add_kb_topic(text, parent_id=None)
                self._load_full_topic_map_and_tree() # Full refresh of cache and tree
                self.search_bar.clear() # Clear search
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add topic: {e}")

    def _add_subtopic(self):
        """Adds a subtopic to the currently selected topic."""
        selected_items = self.topic_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a parent topic first.")
            return

        parent_item = selected_items[0]
        parent_id = parent_item.data(0, Qt.ItemDataRole.UserRole)
        
        text, ok = QInputDialog.getText(self, "Add Subtopic", f"Enter subtopic for '{parent_item.text(0)}':")
        if ok and text:
            try:
                add_kb_topic(text, parent_id=parent_id)
                # Full refresh of cache and tree
                self._load_full_topic_map_and_tree() 
                self.search_bar.clear() # Clear search
                
                # --- NEW: Re-select the parent item after reload ---
                self._find_and_select_item(parent_id)
                new_parent_item = self.topic_tree.currentItem()
                if new_parent_item:
                    new_parent_item.setExpanded(True)
                # --- END NEW ---

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add subtopic: {e}")

    def _delete_topic(self):
        """Deletes the currently selected topic and all its subtopics."""
        selected_items = self.topic_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a topic to delete.")
            return
            
        item = selected_items[0]
        topic_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, 'Confirm Delete',
                                   f"Are you sure you want to delete '{item.text(0)}' and ALL its subtopics?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_kb_topic(topic_id)
                self._load_full_topic_map_and_tree() # Full refresh
                self.search_bar.clear() # Clear search
                self.note_editor.clear()
                self.note_editor.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete topic: {e}")

    # --- NEW: Search Logic Methods ---
    
    def _find_and_select_item(self, topic_id_to_find):
        """ Helper to find and select an item in the tree by its ID. """
        if not topic_id_to_find:
            return None
        
        # Iterate through all top-level items and their children
        iterator = QTreeWidgetItemIterator(self.topic_tree)
        while iterator.value():
            item = iterator.value()
            item_id = item.data(0, Qt.ItemDataRole.UserRole)
            if item_id == topic_id_to_find:
                self.topic_tree.setCurrentItem(item)
                return item
            iterator += 1
        return None

    def _on_search_changed(self, text):
        """Filters the tree based on the search text."""
        self.current_search_text = text.strip()
        
        if not self.current_search_text:
            # No search text, restore the full tree
            self.original_matching_ids = set()
            self._load_topics() # Load from cache
            return
            
        try:
            # 1. Get IDs of topics that match the search
            self.original_matching_ids = search_kb_topics(self.current_search_text)
            if not self.original_matching_ids:
                self.topic_tree.clear() # No matches
                return
                
            # 2. Get all parent IDs for those matches
            ids_to_show = self._get_all_parent_ids_for_matches(self.original_matching_ids)
            
            # 3. Rebuild the tree, showing only those IDs
            self._build_filtered_tree(ids_to_show)
            
        except Exception as e:
            print(f"Error during search: {e}")
            
    def _get_all_parent_ids_for_matches(self, matching_ids):
        """
        Takes a set of matching IDs and returns a new set containing
        all those IDs *plus* all their parent/grandparent/etc. IDs.
        """
        show_set = set()
        for topic_id in matching_ids:
            current_id = topic_id
            while current_id:
                if current_id in show_set: # Stop if we've already traced this path
                    break
                show_set.add(current_id)
                topic = self.all_topics_map.get(current_id)
                current_id = topic.get('parent_id') if topic else None
        return show_set

    def _build_filtered_tree(self, ids_to_show, parent_item=None, parent_id=None):
        """
        Recursively rebuilds the tree, but only adds items
        if their ID is in the `ids_to_show` set.
        """
        if parent_item is None:
            self.topic_tree.clear()
            parent_item = self.topic_tree.invisibleRootItem()

        # Find all children of parent_id that are in our set
        children = [
            topic for topic in self.all_topics_map.values()
            if topic.get('parent_id') == parent_id and topic.get('id') in ids_to_show
        ]
        children.sort(key=lambda t: t.get('title', ''))

        for topic in children:
            item = QTreeWidgetItem(parent_item, [topic['title']])
            item.setData(0, Qt.ItemDataRole.UserRole, topic['id'])
            
            # --- NEW: Highlight direct matches ---
            if topic['id'] in self.original_matching_ids:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            # --- END NEW ---

            # Recurse
            self._build_filtered_tree(ids_to_show, item, topic['id'])
            
            # Expand all items in the filtered view
            parent_item.setExpanded(True)