import os
import hashlib
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QFileDialog, QMessageBox, QMenu, QAction, QGroupBox, QCheckBox, QFrame
)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QBrush, QColor, QDragEnterEvent, QDropEvent, QPen
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QTimer

# Поддерживаемые расширения
SUPPORTED_IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.bmp')
SUPPORTED_VIDEO_EXT = ('.mp4', '.avi', '.mov', '.mkv')

# Размер миниатюры (квадрат)
THUMB_SIZE = 120

class MediaItem:
    def __init__(self, file_path, media_type):
        self.file_path = file_path
        self.media_type = media_type  # "image" или "video"
        self.annotation = None        # для разметки
        self.hash = None
        self.dataset_type = "none"    # "train", "val", "test", "none"

    def compute_hash(self):
        if self.media_type != "image":
            return None
        try:
            with open(self.file_path, "rb") as f:
                data = f.read()
            self.hash = hashlib.md5(data).hexdigest()
            return self.hash
        except Exception:
            return None

def generate_image_thumbnail(file_path, annotation_status="none", dataset_type="none"):
    """
    Генерирует миниатюру изображения с индикатором статуса аннотации и типа выборки
    
    Args:
        file_path: Путь к изображению
        annotation_status: Статус аннотации ('none', 'incomplete', 'complete')
        dataset_type: Тип выборки ('train', 'val', 'test', 'none')
    """
    # Загружаем изображение через QPixmap и принудительно масштабируем до THUMB_SIZE×THUMB_SIZE
    pix = QPixmap(file_path)
    if pix.isNull():
        pix = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pix.fill(Qt.gray)
    else:
        # Чтобы получить квадратную миниатюру без искажений, используем режим IgnoreAspectRatio
        pix = pix.scaled(THUMB_SIZE, THUMB_SIZE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    
    # Добавляем индикаторы
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Выбираем цвет в зависимости от статуса аннотации
    if annotation_status == "none":
        color = QColor(255, 0, 0)  # Красный - нет разметки
    elif annotation_status == "incomplete":
        color = QColor(255, 255, 0)  # Желтый - есть метки без класса
    else:  # "complete"
        color = QColor(0, 255, 0)  # Зеленый - валидная разметка
    
    # Рисуем круг в левом нижнем углу (статус аннотации)
    circle_size = THUMB_SIZE // 8
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(Qt.black, 1))
    painter.drawEllipse(5, THUMB_SIZE - circle_size - 5, circle_size, circle_size)
    
    # Добавляем индикатор типа выборки (буква в правом нижнем углу)
    if dataset_type != "none":
        dataset_letters = {"train": "О", "val": "В", "test": "Т", "none": "Н"}
        letter = dataset_letters.get(dataset_type, "Н")
        
        # Настройки для текста
        font = painter.font()
        font.setPointSize(max(8, THUMB_SIZE // 15))
        font.setBold(True)
        painter.setFont(font)
        
        # Фон для буквы
        text_rect_size = THUMB_SIZE // 6
        text_x = THUMB_SIZE - text_rect_size - 5
        text_y = THUMB_SIZE - text_rect_size - 5
        
        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))  # Полупрозрачный белый фон
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(text_x, text_y, text_rect_size, text_rect_size)
        
        # Рисуем букву
        painter.setPen(QPen(Qt.black))
        painter.drawText(text_x, text_y, text_rect_size, text_rect_size, Qt.AlignCenter, letter)
    
    painter.end()
    return pix

def generate_video_thumbnail(file_path):
    # Используем OpenCV для чтения первого кадра
    cap = cv2.VideoCapture(file_path)
    ret, frame = cap.read()
    cap.release()
    if ret:
        # Преобразуем BGR в RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        qimg = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        # Масштабируем до квадрата
        pix = QPixmap.fromImage(qimg).scaled(THUMB_SIZE, THUMB_SIZE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        return pix
    else:
        # Если не удалось извлечь кадр, возвращаем заглушку
        pix = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pix.fill(Qt.black)
        painter = QPainter(pix)
        painter.setPen(Qt.white)
        painter.drawText(pix.rect(), Qt.AlignCenter, "VIDEO")
        painter.end()
        return pix

class MediaImporterWidget(QWidget):
    # Сигнал для передачи выбранного файла (путь, тип)
    mediaSelected = pyqtSignal(str, str)
    # Сигнал для уведомления об изменении режима
    modeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Разрешаем Drag & Drop
        self.setAcceptDrops(True)
        # Режим по умолчанию – изображения
        self.mode = "image"
        self.imported_items = {"image": [], "video": []}
        self.copied_annotation = None
        # Кэш для миниатюр (для оптимизации производительности)
        self.thumbnail_cache = {}
        self.init_ui()

    def init_ui(self):
        mainLayout = QVBoxLayout(self)

        # Панель переключения режимов – две кнопки: "Изображения" и "Видео"
        modeLayout = QHBoxLayout()
        self.btnImages = QPushButton("Изображения")
        self.btnImages.setCheckable(True)
        self.btnImages.setChecked(True)
        self.btnImages.clicked.connect(self.switch_to_images)
        modeLayout.addWidget(self.btnImages)
        self.btnVideos = QPushButton("Видео")
        self.btnVideos.setCheckable(True)
        self.btnVideos.clicked.connect(self.switch_to_videos)
        modeLayout.addWidget(self.btnVideos)
        
        # Добавляем кнопку обновления
        refresh_btn = QPushButton("Обновить список")
        refresh_btn.clicked.connect(self.refresh_list)
        modeLayout.addWidget(refresh_btn)
        
        mainLayout.addLayout(modeLayout)

        # Создаем горизонтальный layout для основной области (миниатюры + фильтры)
        contentLayout = QHBoxLayout()
        
        # Виджет для отображения миниатюр (в виде плитки) - слева
        self.listWidget = QListWidget()
        self.listWidget.setViewMode(QListWidget.IconMode)
        self.listWidget.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.listWidget.setGridSize(QSize(THUMB_SIZE + 10, THUMB_SIZE + 30))
        self.listWidget.setMovement(QListWidget.Static)
        self.listWidget.setSpacing(5)
        self.listWidget.setSelectionMode(QListWidget.ExtendedSelection)
        self.listWidget.itemClicked.connect(self.on_item_clicked)
        self.listWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listWidget.customContextMenuRequested.connect(self.show_context_menu)
        contentLayout.addWidget(self.listWidget, 3)  # 3/4 пространства для миниатюр

        # Панель фильтров (только для изображений) - справа
        self.filters_group = QGroupBox("Фильтры")
        self.filters_group.setMaximumWidth(300)  # Ограничиваем ширину панели фильтров
        filters_layout = QVBoxLayout(self.filters_group)
        
        # Фильтры по статусу аннотаций
        annotation_filters_layout = QVBoxLayout()  # Изменено на вертикальный для экономии места
        annotation_filters_layout.addWidget(QLabel("<b>Статус разметки:</b>"))
        
        self.filter_no_annotations = QCheckBox("Нет разметки")
        self.filter_no_annotations.setChecked(True)
        self.filter_no_annotations.stateChanged.connect(self.on_filter_changed)
        annotation_filters_layout.addWidget(self.filter_no_annotations)
        
        self.filter_incomplete_annotations = QCheckBox("Есть метки без класса")
        self.filter_incomplete_annotations.setChecked(True)
        self.filter_incomplete_annotations.stateChanged.connect(self.on_filter_changed)
        annotation_filters_layout.addWidget(self.filter_incomplete_annotations)
        
        self.filter_complete_annotations = QCheckBox("Валидная разметка")
        self.filter_complete_annotations.setChecked(True)
        self.filter_complete_annotations.stateChanged.connect(self.on_filter_changed)
        annotation_filters_layout.addWidget(self.filter_complete_annotations)
        
        filters_layout.addLayout(annotation_filters_layout)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        filters_layout.addWidget(separator)
        
        # Фильтры по типам выборки
        dataset_filters_layout = QVBoxLayout()  # Изменено на вертикальный для экономии места
        dataset_filters_layout.addWidget(QLabel("<b>Тип выборки:</b>"))
        
        self.filter_train_dataset = QCheckBox("Обучающая (О)")
        self.filter_train_dataset.setChecked(True)
        self.filter_train_dataset.stateChanged.connect(self.on_filter_changed)
        dataset_filters_layout.addWidget(self.filter_train_dataset)
        
        self.filter_val_dataset = QCheckBox("Валидационная (В)")
        self.filter_val_dataset.setChecked(True)
        self.filter_val_dataset.stateChanged.connect(self.on_filter_changed)
        dataset_filters_layout.addWidget(self.filter_val_dataset)
        
        self.filter_test_dataset = QCheckBox("Тестовая (Т)")
        self.filter_test_dataset.setChecked(True)
        self.filter_test_dataset.stateChanged.connect(self.on_filter_changed)
        dataset_filters_layout.addWidget(self.filter_test_dataset)
        
        self.filter_none_dataset = QCheckBox("Нет выборки (Н)")
        self.filter_none_dataset.setChecked(True)
        self.filter_none_dataset.stateChanged.connect(self.on_filter_changed)
        dataset_filters_layout.addWidget(self.filter_none_dataset)
        
        filters_layout.addLayout(dataset_filters_layout)
        
        # Разделитель
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        filters_layout.addWidget(separator2)
        
        # Кнопки быстрого управления фильтрами
        filter_buttons_layout = QVBoxLayout()  # Изменено на вертикальный
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.clicked.connect(self.select_all_filters)
        filter_buttons_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Снять все")
        deselect_all_btn.clicked.connect(self.deselect_all_filters)
        filter_buttons_layout.addWidget(deselect_all_btn)
        
        filters_layout.addLayout(filter_buttons_layout)
        
        # Добавляем растяжку в конец панели фильтров
        filters_layout.addStretch()
        
        contentLayout.addWidget(self.filters_group, 1)  # 1/4 пространства для фильтров
        
        mainLayout.addLayout(contentLayout)

        # Панель кнопок импорта (перемещена под список)
        btnLayout = QHBoxLayout()
        self.btnImportDir = QPushButton("Импортировать из директории")
        self.btnImportDir.clicked.connect(self.import_directory)
        btnLayout.addWidget(self.btnImportDir)
        self.btnImportFiles = QPushButton("Импортировать файл(ы)")
        self.btnImportFiles.clicked.connect(self.import_files)
        btnLayout.addWidget(self.btnImportFiles)
        mainLayout.addLayout(btnLayout)

        self.setLayout(mainLayout)
        
        # Подключаемся к сигналам изменения классов, если от родителя доступен класс-менеджер
        main_window = self.get_main_window()
        if main_window and hasattr(main_window, 'class_manager') and hasattr(main_window.class_manager, 'classesChanged'):
            main_window.class_manager.classesChanged.connect(self.refresh_list)

    def switch_to_images(self):
        self.mode = "image"
        self.btnImages.setChecked(True)
        self.btnVideos.setChecked(False)
        # Показываем панель фильтров для изображений
        self.filters_group.setVisible(True)
        self.refresh_list()
        # Отправляем сигнал об изменении режима
        self.modeChanged.emit(self.mode)

    def switch_to_videos(self):
        self.mode = "video"
        self.btnVideos.setChecked(True)
        self.btnImages.setChecked(False)
        # Скрываем панель фильтров для видео
        self.filters_group.setVisible(False)
        self.refresh_list()
        # Отправляем сигнал об изменении режима
        self.modeChanged.emit(self.mode)

    def import_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if not dir_path:
            return
        if self.mode == "image":
            supported = SUPPORTED_IMAGE_EXT
        else:
            supported = SUPPORTED_VIDEO_EXT
        files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                 if f.lower().endswith(supported)]
        for file in files:
            self.import_file(file)
        self.refresh_list()

    def import_files(self):
        if self.mode == "image":
            filter_str = "Изображения (*.png *.jpg *.jpeg *.bmp *.gif)"
        else:
            filter_str = "Видео (*.mp4 *.avi *.mov *.mkv)"
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы", "", filter_str)
        if not files:
            return
        for file in files:
            self.import_file(file)
        self.refresh_list()

    def import_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        # Если тип файла не соответствует текущему режиму, переключаемся
        if ext in SUPPORTED_IMAGE_EXT and self.mode != "image":
            self.switch_to_images()
        elif ext in SUPPORTED_VIDEO_EXT and self.mode != "video":
            self.switch_to_videos()
        # Устанавливаем тип на основе расширения
        media_type = "image" if ext in SUPPORTED_IMAGE_EXT else "video"
        # Для изображений проверяем дубликаты
        if media_type == "image":
            for item in self.imported_items["image"]:
                if os.path.basename(item.file_path) == os.path.basename(file_path):
                    new_item = MediaItem(file_path, "image")
                    new_hash = new_item.compute_hash()
                    if new_hash and item.hash == new_hash:
                        reply = QMessageBox.question(
                            self, "Дубликат найден",
                            f"Изображение '{os.path.basename(file_path)}' уже импортировано. Импортировать всё равно?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.No:
                            return
                        else:
                            break
        new_item = MediaItem(file_path, media_type)
        if media_type == "image":
            new_item.compute_hash()
        self.imported_items[media_type].append(new_item)

    def get_cached_thumbnail(self, file_path, annotation_status, dataset_type, media_type):
        """Получает миниатюру из кэша или генерирует новую"""
        cache_key = (file_path, annotation_status, dataset_type, media_type)
        
        if cache_key in self.thumbnail_cache:
            return self.thumbnail_cache[cache_key]
        
        # Генерируем новую миниатюру
        if media_type == "image":
            thumb = generate_image_thumbnail(file_path, annotation_status, dataset_type)
        else:
            thumb = generate_video_thumbnail(file_path)
        
        # Сохраняем в кэш (ограничиваем размер кэша)
        if len(self.thumbnail_cache) > 1000:  # Максимум 1000 миниатюр в кэше
            # Удаляем старые элементы (простой FIFO)
            oldest_key = next(iter(self.thumbnail_cache))
            del self.thumbnail_cache[oldest_key]
        
        self.thumbnail_cache[cache_key] = thumb
        return thumb
    
    def update_specific_items(self, items):
        """Обновляет отображение только для конкретных элементов списка"""
        # Получаем доступ к AnnotationManager для проверки статуса аннотаций
        annotation_manager = None
        main_window = self.get_main_window()
        if main_window and hasattr(main_window, 'image_viewer') and hasattr(main_window.image_viewer, 'annotation_manager'):
            annotation_manager = main_window.image_viewer.annotation_manager
        
        for item in items:
            media_item = item.data(Qt.UserRole)
            if media_item and media_item.media_type == "image":
                # Определяем статус аннотации
                annotation_status = "none"
                if annotation_manager:
                    annotation_status = annotation_manager.get_image_annotation_status(media_item.file_path)
                
                # Инвалидируем кэш для этого элемента (так как dataset_type изменился)
                old_keys_to_remove = [key for key in self.thumbnail_cache.keys() if key[0] == media_item.file_path]
                for key in old_keys_to_remove:
                    del self.thumbnail_cache[key]
                
                # Генерируем новую миниатюру
                thumb = self.get_cached_thumbnail(media_item.file_path, annotation_status, media_item.dataset_type, media_item.media_type)
                item.setIcon(QIcon(thumb))
    
    def refresh_list(self):
        self.listWidget.clear()
        
        # Получаем доступ к AnnotationManager для проверки статуса аннотаций
        annotation_manager = None
        main_window = self.get_main_window()
        if main_window and hasattr(main_window, 'image_viewer') and hasattr(main_window.image_viewer, 'annotation_manager'):
            annotation_manager = main_window.image_viewer.annotation_manager
        
        filtered_count = 0
        total_count = len(self.imported_items[self.mode])
        
        for item in self.imported_items[self.mode]:
            # Определяем статус аннотации для изображений
            annotation_status = "none"
            if item.media_type == "image" and annotation_manager:
                annotation_status = annotation_manager.get_image_annotation_status(item.file_path)
            
            # Проверяем фильтрацию
            if self.item_passes_filter(item, annotation_status):
                filtered_count += 1
                list_item = QListWidgetItem()
                
                if item.media_type == "image":
                    thumb = self.get_cached_thumbnail(item.file_path, annotation_status, item.dataset_type, item.media_type)
                else:
                    thumb = self.get_cached_thumbnail(item.file_path, "none", "none", item.media_type)
                    
                list_item.setIcon(QIcon(thumb))
                list_item.setText(os.path.basename(item.file_path))
                list_item.setData(Qt.UserRole, item)
                self.listWidget.addItem(list_item)
        
        # Обновляем заголовок группы фильтров с информацией о количестве
        if self.mode == "image":
            if total_count > 0:
                self.filters_group.setTitle(f"Фильтры (показано: {filtered_count} из {total_count})")
            else:
                self.filters_group.setTitle("Фильтры")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            # Если тип файла не соответствует текущему режиму, переключаемся
            if ext in SUPPORTED_IMAGE_EXT and self.mode != "image":
                self.switch_to_images()
            elif ext in SUPPORTED_VIDEO_EXT and self.mode != "video":
                self.switch_to_videos()
            self.import_file(file_path)
        self.refresh_list()

    def on_item_clicked(self, item: QListWidgetItem):
        media_item = item.data(Qt.UserRole)
        self.mediaSelected.emit(media_item.file_path, media_item.media_type)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or Qt.Key_Backspace:
            self.delete_selected_items()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, pos):
        item = self.listWidget.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        
        # Получаем объект медиа, связанный с элементом
        media_item = item.data(Qt.UserRole)
        
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.delete_item(item))
        menu.addAction(delete_action)
        
        # Для видео добавляем опцию извлечения кадров
        if media_item.media_type == "video":
            extract_frames_action = QAction("Extract frames", self)
            extract_frames_action.triggered.connect(lambda: self.open_video_extractor(media_item.file_path))
            menu.addAction(extract_frames_action)
        
        # Для изображений добавляем опции работы с разметкой и выборкой
        if media_item.media_type == "image":
            copy_action = QAction("Копировать разметку", self)
            copy_action.triggered.connect(lambda: self.copy_annotation(item))
            menu.addAction(copy_action)
            
            if self.copied_annotation is not None:
                paste_action = QAction("Вставить разметку", self)
                paste_action.triggered.connect(lambda: self.paste_annotation(item))
                menu.addAction(paste_action)
                
            # Добавляем разделитель
            menu.addSeparator()
            
            # Получаем выбранные элементы для оптимизации
            selected_items = self.listWidget.selectedItems()
            if not selected_items:
                selected_items = [item]
            
            # Фильтруем только изображения
            image_items = [item for item in selected_items 
                          if item.data(Qt.UserRole) and item.data(Qt.UserRole).media_type == "image"]
            
            count = len(image_items)
            count_text = f" ({count})" if count > 1 else ""
            
            # Добавляем пункт изменения выборки
            dataset_menu = QMenu(f"Изменить выборку{count_text}", self)
            
            train_action = QAction(f"Обучающая (О){count_text}", self)
            train_action.triggered.connect(lambda: self.change_dataset_type(image_items, "train"))
            dataset_menu.addAction(train_action)
            
            val_action = QAction(f"Валидационная (В){count_text}", self)
            val_action.triggered.connect(lambda: self.change_dataset_type(image_items, "val"))
            dataset_menu.addAction(val_action)
            
            test_action = QAction(f"Тестовая (Т){count_text}", self)
            test_action.triggered.connect(lambda: self.change_dataset_type(image_items, "test"))
            dataset_menu.addAction(test_action)
            
            none_action = QAction(f"Нет выборки (Н){count_text}", self)
            none_action.triggered.connect(lambda: self.change_dataset_type(image_items, "none"))
            dataset_menu.addAction(none_action)
            
            menu.addMenu(dataset_menu)
            
        menu.exec_(self.listWidget.mapToGlobal(pos))
    
    def open_video_extractor(self, video_path):
        """Открывает диалог извлечения кадров из видео"""
        from gui.video_extractor import VideoExtractorWidget
        
        # Создаем виджет извлечения кадров
        extractor = VideoExtractorWidget(video_path)
        extractor.setWindowTitle("Извлечение кадров из видео")
        extractor.resize(1200, 800)
        
        # Подключаем сигнал извлечения кадров
        extractor.framesExtracted.connect(self.import_extracted_frames)
        
        # Показываем диалог
        extractor.show()
    
    def import_extracted_frames(self, frame_paths):
        """Импортирует извлеченные кадры в режим изображений"""
        # Переключаемся в режим изображений
        self.switch_to_images()
        
        # Импортируем каждый кадр
        for frame_path in frame_paths:
            self.import_file(frame_path)
            
        # Обновляем список
        self.refresh_list()

    def delete_selected_items(self):
        # Создаем копию списка выбранных элементов
        selected_items = list(self.listWidget.selectedItems())
        if not selected_items:
            return
        for item in selected_items:
            media_item = item.data(Qt.UserRole)
            try:
                self.imported_items[media_item.media_type].remove(media_item)
            except ValueError:
                pass
        self.refresh_list()

    def delete_item(self, item: QListWidgetItem):
        media_item = item.data(Qt.UserRole)
        try:
            self.imported_items[media_item.media_type].remove(media_item)
        except ValueError:
            pass
        self.refresh_list()

    def copy_annotation(self, item: QListWidgetItem):
        media_item = item.data(Qt.UserRole)
        if media_item.media_type != "image":
            QMessageBox.information(self, "Информация", "Копирование разметки поддерживается только для изображений")
            return
            
        # Ищем главное окно приложения, чтобы получить доступ к ImageViewer
        main_window = self.get_main_window()
        if not main_window or not hasattr(main_window, 'image_viewer'):
            QMessageBox.warning(self, "Предупреждение", "Не удалось получить доступ к ImageViewer")
            return
            
        # Получаем AnnotationManager из ImageViewer
        annotation_manager = main_window.image_viewer.annotation_manager
        if not annotation_manager:
            QMessageBox.warning(self, "Предупреждение", "Не удалось получить доступ к AnnotationManager")
            return
            
        # Проверяем, есть ли аннотации для выбранного изображения
        file_path = media_item.file_path
        if file_path not in annotation_manager.annotations_by_image or not annotation_manager.annotations_by_image[file_path]:
            QMessageBox.information(self, "Информация", "У выбранного изображения нет разметки для копирования")
            return
            
        # Копируем разметку
        self.copied_annotation = {
            'source_file': file_path,
            'annotations': annotation_manager.annotations_by_image[file_path]
        }
        
        QMessageBox.information(self, "Копирование", f"Разметка скопирована из {os.path.basename(file_path)}")

    def paste_annotation(self, item: QListWidgetItem):
        if self.copied_annotation is None:
            QMessageBox.information(self, "Информация", "Нет скопированной разметки")
            return
            
        media_item = item.data(Qt.UserRole)
        if media_item.media_type != "image":
            QMessageBox.information(self, "Информация", "Вставка разметки поддерживается только для изображений")
            return
            
        # Ищем главное окно приложения, чтобы получить доступ к ImageViewer
        main_window = self.get_main_window()
        if not main_window or not hasattr(main_window, 'image_viewer'):
            QMessageBox.warning(self, "Предупреждение", "Не удалось получить доступ к ImageViewer")
            return
            
        # Получаем AnnotationManager из ImageViewer
        annotation_manager = main_window.image_viewer.annotation_manager
        if not annotation_manager:
            QMessageBox.warning(self, "Предупреждение", "Не удалось получить доступ к AnnotationManager")
            return
            
        # Вставляем аннотации в целевое изображение
        target_file = media_item.file_path
        annotation_manager.annotations_by_image[target_file] = self.copied_annotation['annotations']
        
        # Если это изображение сейчас открыто в ImageViewer, обновляем его отображение
        if main_window.image_viewer.current_image_path == target_file:
            main_window.image_viewer.load_annotations_for_image(target_file)
            
        source_file = os.path.basename(self.copied_annotation['source_file'])
        target_file = os.path.basename(target_file)
        QMessageBox.information(self, "Вставка", f"Разметка из {source_file} вставлена в {target_file}")
        
        # Обновляем список после вставки разметки
        self.refresh_list()
        
    def get_main_window(self):
        """Получает ссылку на главное окно приложения"""
        parent = self.parent()
        while parent is not None:
            # Проверяем, имеет ли родитель атрибуты, характерные для главного окна
            if hasattr(parent, 'image_viewer') and hasattr(parent, 'media_importer'):
                return parent
            parent = parent.parent()
        return None

    def change_dataset_type(self, items, dataset_type):
        """Изменяет тип выборки для выбранных элементов"""
        if not items:
            return
            
        changed_items = []
        
        # Блокируем обновления UI во время пакетной операции
        self.listWidget.setUpdatesEnabled(False)
        
        try:
            for item in items:
                media_item = item.data(Qt.UserRole)
                if media_item and media_item.media_type == "image":
                    # Проверяем, действительно ли изменяется тип
                    if media_item.dataset_type != dataset_type:
                        media_item.dataset_type = dataset_type
                        changed_items.append(item)
            
            # Обновляем только измененные элементы
            if changed_items:
                self.update_specific_items(changed_items)
                
        finally:
            # Восстанавливаем обновления UI
            self.listWidget.setUpdatesEnabled(True)

    def clear_thumbnail_cache(self):
        """Очищает кэш миниатюр"""
        self.thumbnail_cache.clear()

    def on_filter_changed(self):
        """Обработчик изменения фильтров"""
        # Используем таймер для отложенного обновления, чтобы избежать множественных обновлений
        if not hasattr(self, '_filter_timer'):
            self._filter_timer = QTimer()
            self._filter_timer.setSingleShot(True)
            self._filter_timer.timeout.connect(self.refresh_list)
        
        # Отменяем предыдущий таймер и запускаем новый
        self._filter_timer.stop()
        self._filter_timer.start(100)  # 100 мс задержка

    def select_all_filters(self):
        """Выбирает все фильтры"""
        # Временно отключаем сигналы чтобы избежать множественных обновлений
        self.filter_no_annotations.blockSignals(True)
        self.filter_incomplete_annotations.blockSignals(True)
        self.filter_complete_annotations.blockSignals(True)
        self.filter_train_dataset.blockSignals(True)
        self.filter_val_dataset.blockSignals(True)
        self.filter_test_dataset.blockSignals(True)
        self.filter_none_dataset.blockSignals(True)
        
        self.filter_no_annotations.setChecked(True)
        self.filter_incomplete_annotations.setChecked(True)
        self.filter_complete_annotations.setChecked(True)
        self.filter_train_dataset.setChecked(True)
        self.filter_val_dataset.setChecked(True)
        self.filter_test_dataset.setChecked(True)
        self.filter_none_dataset.setChecked(True)
        
        # Включаем сигналы обратно
        self.filter_no_annotations.blockSignals(False)
        self.filter_incomplete_annotations.blockSignals(False)
        self.filter_complete_annotations.blockSignals(False)
        self.filter_train_dataset.blockSignals(False)
        self.filter_val_dataset.blockSignals(False)
        self.filter_test_dataset.blockSignals(False)
        self.filter_none_dataset.blockSignals(False)
        
        # Обновляем список один раз
        self.refresh_list()

    def deselect_all_filters(self):
        """Снимает все фильтры"""
        # Временно отключаем сигналы чтобы избежать множественных обновлений
        self.filter_no_annotations.blockSignals(True)
        self.filter_incomplete_annotations.blockSignals(True)
        self.filter_complete_annotations.blockSignals(True)
        self.filter_train_dataset.blockSignals(True)
        self.filter_val_dataset.blockSignals(True)
        self.filter_test_dataset.blockSignals(True)
        self.filter_none_dataset.blockSignals(True)
        
        self.filter_no_annotations.setChecked(False)
        self.filter_incomplete_annotations.setChecked(False)
        self.filter_complete_annotations.setChecked(False)
        self.filter_train_dataset.setChecked(False)
        self.filter_val_dataset.setChecked(False)
        self.filter_test_dataset.setChecked(False)
        self.filter_none_dataset.setChecked(False)
        
        # Включаем сигналы обратно
        self.filter_no_annotations.blockSignals(False)
        self.filter_incomplete_annotations.blockSignals(False)
        self.filter_complete_annotations.blockSignals(False)
        self.filter_train_dataset.blockSignals(False)
        self.filter_val_dataset.blockSignals(False)
        self.filter_test_dataset.blockSignals(False)
        self.filter_none_dataset.blockSignals(False)
        
        # Обновляем список один раз
        self.refresh_list()

    def item_passes_filter(self, item, annotation_status):
        """Проверяет, проходит ли элемент фильтрацию"""
        # Для видео нет фильтрации
        if item.media_type == "video":
            return True
        
        # Проверяем фильтр по статусу аннотаций
        annotation_filter_passed = False
        if annotation_status == "none" and self.filter_no_annotations.isChecked():
            annotation_filter_passed = True
        elif annotation_status == "incomplete" and self.filter_incomplete_annotations.isChecked():
            annotation_filter_passed = True
        elif annotation_status == "complete" and self.filter_complete_annotations.isChecked():
            annotation_filter_passed = True
        
        if not annotation_filter_passed:
            return False
        
        # Проверяем фильтр по типу выборки
        dataset_filter_passed = False
        if item.dataset_type == "train" and self.filter_train_dataset.isChecked():
            dataset_filter_passed = True
        elif item.dataset_type == "val" and self.filter_val_dataset.isChecked():
            dataset_filter_passed = True
        elif item.dataset_type == "test" and self.filter_test_dataset.isChecked():
            dataset_filter_passed = True
        elif item.dataset_type == "none" and self.filter_none_dataset.isChecked():
            dataset_filter_passed = True
        
        return dataset_filter_passed

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    widget = MediaImporterWidget()
    widget.setWindowTitle("Импорт изображений и видео")
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())