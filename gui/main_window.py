from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStackedWidget, QApplication, QMenuBar, QMenu, QAction, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, pyqtSlot

from gui.video_player import VideoPlayer
from gui.class_manager import SegmentationClassManagerWidget
from gui.media_importer import MediaImporterWidget
from gui.image_viewer import ImageViewerWidget
from gui.export_annotations import ExportAnnotationsDialog
from gui.import_annotations import ImportAnnotationsDialog


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
        
        # Создаем меню бар
        self.create_menu_bar()
        
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
        left_splitter.setSizes([500, 300])  # 5:3 соотношение для верх:низ
        
        # Добавляем левую и правую панели в главный разделитель
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.class_manager)
        
        # Устанавливаем начальные размеры главного разделителя
        main_splitter.setSizes([800, 400])  # Примерно 8:4 для лево:право
        
        # Подключаем сигналы
        self.media_importer.mediaSelected.connect(self.on_media_selected)
        self.media_importer.modeChanged.connect(self.on_mode_changed)
        
        # Подключаем сигнал сохранения кадра от VideoPlayer
        self.video_player.frameSaved.connect(self.on_frame_saved)
        
        # Устанавливаем связь между менеджером классов и просмотрщиком изображений
        self.image_viewer.set_class_manager(self.class_manager)
        
        # Подключаем сигналы изменения классов для обновления отображения
        if hasattr(self.class_manager, 'classesChanged'):
            self.class_manager.classesChanged.connect(self.media_importer.refresh_list)
            
        # Установка начального режима
        self.on_mode_changed(self.media_importer.mode)
        
        # Сохраняем ссылки на виджеты для управления видимостью
        self.view_widgets = {
            'media_viewer': self.media_stack,
            'thumbnails': self.media_importer,
            'filters': self.media_importer.filters_group if hasattr(self.media_importer, 'filters_group') else None,
            'class_list': self.class_manager
        }
    
    def create_menu_bar(self):
        """
        Создает меню бар с пунктами 'Экспорт аннотаций', 'Импорт аннотаций' и 'Вид'
        """
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        
        # Создаем меню
        annotations_menu = QMenu("Аннотации", self)
        menu_bar.addMenu(annotations_menu)
        
        # Создаем действия
        export_action = QAction("Экспорт аннотаций", self)
        import_action = QAction("Импорт аннотаций", self)
        
        # Добавляем действия в меню
        annotations_menu.addAction(export_action)
        annotations_menu.addAction(import_action)
        
        # Подключаем сигналы
        export_action.triggered.connect(self.open_export_dialog)
        import_action.triggered.connect(self.open_import_dialog)
        
        # Создаем меню "Вид"
        view_menu = QMenu("Вид", self)
        menu_bar.addMenu(view_menu)
        
        # Создаем действия для управления видимостью элементов
        self.view_actions = {}
        
        # Просмотр медиа
        media_viewer_action = QAction("Просмотр медиа", self)
        media_viewer_action.setCheckable(True)
        media_viewer_action.setChecked(True)
        media_viewer_action.triggered.connect(lambda: self.toggle_widget_visibility('media_viewer'))
        view_menu.addAction(media_viewer_action)
        self.view_actions['media_viewer'] = media_viewer_action
        
        # Миниатюры
        thumbnails_action = QAction("Миниатюры", self)
        thumbnails_action.setCheckable(True)
        thumbnails_action.setChecked(True)
        thumbnails_action.triggered.connect(lambda: self.toggle_widget_visibility('thumbnails'))
        view_menu.addAction(thumbnails_action)
        self.view_actions['thumbnails'] = thumbnails_action
        
        # Фильтры
        filters_action = QAction("Фильтры", self)
        filters_action.setCheckable(True)
        filters_action.setChecked(True)
        filters_action.triggered.connect(lambda: self.toggle_widget_visibility('filters'))
        view_menu.addAction(filters_action)
        self.view_actions['filters'] = filters_action
        
        # Список классов
        class_list_action = QAction("Список классов", self)
        class_list_action.setCheckable(True)
        class_list_action.setChecked(True)
        class_list_action.triggered.connect(lambda: self.toggle_widget_visibility('class_list'))
        view_menu.addAction(class_list_action)
        self.view_actions['class_list'] = class_list_action
    
    def toggle_widget_visibility(self, widget_name):
        """
        Переключает видимость виджета
        """
        if widget_name in self.view_widgets:
            widget = self.view_widgets[widget_name]
            if widget is not None:
                widget.setVisible(self.view_actions[widget_name].isChecked())
                
                # Если скрываем/показываем media_importer, нужно обновить размеры разделителя
                if widget_name == 'thumbnails' and hasattr(self, 'media_importer'):
                    left_splitter = self.findChild(QSplitter, '', Qt.FindChildrenRecursively)
                    if left_splitter:
                        if widget.isVisible():
                            left_splitter.setSizes([500, 300])  # Восстанавливаем стандартные размеры
                        else:
                            left_splitter.setSizes([800, 0])  # Растягиваем media_stack на всю высоту
    
    def open_export_dialog(self):
        """
        Открывает диалоговое окно экспорта аннотаций
        """
        export_dialog = ExportAnnotationsDialog(self)
        export_dialog.exec_()
    
    def open_import_dialog(self):
        """
        Открывает диалоговое окно импорта аннотаций
        """
        try:
            import_dialog = ImportAnnotationsDialog(self)
            import_dialog.exec_()
        except Exception as e:
            from logger import logger
            logger.error(f"Ошибка при открытии диалога импорта: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог импорта: {str(e)}")

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
        Обработчик сохранения кадра в VideoPlayer.
        Автоматически импортирует сохраненный кадр в MediaImporter.
        
        :param frame_path: путь к сохраненному кадру
        """
        self.media_importer.import_file(frame_path)

    @pyqtSlot(list)
    def on_frames_extracted(self, frame_paths):
        """
        Обработчик извлечения кадров из видео.
        Импортирует извлеченные кадры в MediaImporterWidget.
        
        :param frame_paths: список путей к извлеченным кадрам
        """
        # Обработка уже реализована в MediaImporterWidget.import_extracted_frames
        pass 