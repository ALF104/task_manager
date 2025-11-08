import sys
import os
from PySide6.QtWidgets import QApplication

# This line adds your project folder to Python's path
# This ensures that Python can find your 'app' package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Now we can import MainWindow from our app package
from app.core.main import MainWindow

def main():
    """
    Main function to initialize and run the QApplication.
    """
    app = QApplication(sys.argv)

    try:
        window = MainWindow(app)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        # In a real app, you might log this to a file
        sys.exit(1)

if __name__ == "__main__":
    main()