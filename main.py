import sys
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Создаем и запускаем главное окно
    main_window = MainWindow()
    main_window.show()
    
    sys.exit(app.exec_())
