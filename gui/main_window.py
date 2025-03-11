from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStackedWidget, QApplication
)
from PyQt5.QtCore import Qt, QSize, pyqtSlot

from gui.video_player import VideoPlayer
from gui.class_manager import SegmentationClassManagerWidget
from gui.media_importer import MediaImporterWidget
from gui.image_viewer import ImageViewerWidget


class MainWindow(QMainWindow):
    """
    Главное окно приложения, объединяющее все виджеты:
    - MediaImporterWidget (внизу слева)
    - SegmentationClassManagerWidget (справа)
    - Стек с ImageViewerWidget и VideoPlayer (вверху слева)
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Segmentation Tool")
        self.resize(1200, 800)  # Стартовый размер окна
        
        # Создаем центральный виджет
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Главный макет для всего окна
        main_layout = QHBoxLayout(central_widget)
        
        # Создаем разделитель между левой и правой панелями
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Левая панель: MediaImporter внизу и стек (ImageViewer/VideoPlayer) вверху
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем разделитель для левой панели
        left_splitter = QSplitter(Qt.Vertical)
        left_layout.addWidget(left_splitter)
        
        # Стек для ImageViewer и VideoPlayer
        self.media_stack = QStackedWidget()
        
        # Создаем менеджер классов сегментации
        self.class_manager = SegmentationClassManagerWidget()
        
        # Создаем ImageViewer и связываем его с менеджером классов
        self.image_viewer = ImageViewerWidget(class_manager=self.class_manager)
        
        # Создаем VideoPlayer
        self.video_player = VideoPlayer()
        
        self.media_stack.addWidget(self.image_viewer)  # Индекс 0
        self.media_stack.addWidget(self.video_player)  # Индекс 1
        
        # MediaImporter внизу
        self.media_importer = MediaImporterWidget()
        
        # Добавляем виджеты в левый разделитель
        left_splitter.addWidget(self.media_stack)
        left_splitter.addWidget(self.media_importer)
        
        # Устанавливаем начальные размеры разделителей
        left_splitter.setSizes([600, 200])  # 3:1 соотношение для верх:низ
        
        # Добавляем левую и правую панели в главный разделитель
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.class_manager)
        
        # Устанавливаем начальные размеры главного разделителя
        main_splitter.setSizes([700, 500])  # Примерно 7:5 для лево:право
        
        # Подключаем сигналы
        self.media_importer.mediaSelected.connect(self.on_media_selected)
        self.media_importer.modeChanged.connect(self.on_mode_changed)
        
        # Подключаем сигнал сохранения кадра от VideoPlayer
        self.video_player.frameSaved.connect(self.on_frame_saved)
        
        # Установка начального режима
        self.on_mode_changed(self.media_importer.mode)
    
    @pyqtSlot(str, str)
    def on_media_selected(self, file_path, media_type):
        """
        Обработчик выбора медиа-файла.
        Переключает соответствующий виджет в зависимости от типа медиа.
        
        :param file_path: путь к медиа-файлу
        :param media_type: тип медиа ("image" или "video")
        """
        if media_type == "image":
            self.media_stack.setCurrentIndex(0)  # Переключиться на ImageViewer
            self.image_viewer.load_image(file_path)
        elif media_type == "video":
            self.media_stack.setCurrentIndex(1)  # Переключиться на VideoPlayer
            self.video_player.load_video(file_path)
    
    @pyqtSlot(str)
    def on_mode_changed(self, mode):
        """
        Обработчик изменения режима в MediaImporterWidget.
        Переключает соответствующий виджет в зависимости от текущего режима.
        
        :param mode: текущий режим ("image" или "video")
        """
        if mode == "image":
            self.media_stack.setCurrentIndex(0)  # Показать ImageViewer
        elif mode == "video":
            self.media_stack.setCurrentIndex(1)  # Показать VideoPlayer 

    @pyqtSlot(str)
    def on_frame_saved(self, frame_path):
        """
        Обработчик сохранения кадра видео.
        Импортирует сохраненный кадр в MediaImporterWidget.
        
        :param frame_path: путь к сохраненному файлу кадра
        """
        # Принудительно переключаемся в режим изображений
        self.media_importer.switch_to_images()
        # Импортируем изображение
        self.media_importer.import_file(frame_path)
        # Обновляем список
        self.media_importer.refresh_list() 