import os
import hashlib
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QFileDialog, QMessageBox, QMenu, QAction
)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QBrush, QColor, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, QSize, pyqtSignal

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

def generate_image_thumbnail(file_path):
    # Загружаем изображение через QPixmap и принудительно масштабируем до THUMB_SIZE×THUMB_SIZE
    pix = QPixmap(file_path)
    if pix.isNull():
        pix = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pix.fill(Qt.gray)
    else:
        # Чтобы получить квадратную миниатюру без искажений, используем режим IgnoreAspectRatio
        pix = pix.scaled(THUMB_SIZE, THUMB_SIZE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
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

    def __init__(self, parent=None):
        super().__init__(parent)
        # Разрешаем Drag & Drop
        self.setAcceptDrops(True)
        # Режим по умолчанию – изображения
        self.mode = "image"
        self.imported_items = {"image": [], "video": []}
        self.copied_annotation = None
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
        mainLayout.addLayout(modeLayout)

        # Панель кнопок импорта
        btnLayout = QHBoxLayout()
        self.btnImportDir = QPushButton("Импортировать из директории")
        self.btnImportDir.clicked.connect(self.import_directory)
        btnLayout.addWidget(self.btnImportDir)
        self.btnImportFiles = QPushButton("Импортировать файл(ы)")
        self.btnImportFiles.clicked.connect(self.import_files)
        btnLayout.addWidget(self.btnImportFiles)
        mainLayout.addLayout(btnLayout)

        # Виджет для отображения миниатюр (в виде плитки)
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
        mainLayout.addWidget(self.listWidget)

        self.setLayout(mainLayout)

    def switch_to_images(self):
        self.mode = "image"
        self.btnImages.setChecked(True)
        self.btnVideos.setChecked(False)
        self.refresh_list()

    def switch_to_videos(self):
        self.mode = "video"
        self.btnVideos.setChecked(True)
        self.btnImages.setChecked(False)
        self.refresh_list()

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

    def refresh_list(self):
        self.listWidget.clear()
        for item in self.imported_items[self.mode]:
            list_item = QListWidgetItem()
            if item.media_type == "image":
                thumb = generate_image_thumbnail(item.file_path)
            else:
                thumb = generate_video_thumbnail(item.file_path)
            list_item.setIcon(QIcon(thumb))
            list_item.setText(os.path.basename(item.file_path))
            list_item.setData(Qt.UserRole, item)
            self.listWidget.addItem(list_item)

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
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.delete_item(item))
        menu.addAction(delete_action)
        copy_action = QAction("Копировать разметку", self)
        copy_action.triggered.connect(lambda: self.copy_annotation(item))
        menu.addAction(copy_action)
        if self.copied_annotation is not None:
            paste_action = QAction("Вставить разметку", self)
            paste_action.triggered.connect(lambda: self.paste_annotation(item))
            menu.addAction(paste_action)
        menu.exec_(self.listWidget.mapToGlobal(pos))

    def delete_selected_items(self):
        # Создаем копию списка выбранных элементов
        selected_items = list(self.listWidget.selectedItems())
        print(selected_items)
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
        if media_item.annotation is None:
            QMessageBox.information(self, "Информация", "У выбранного файла нет разметки для копирования")
            return
        self.copied_annotation = media_item.annotation
        QMessageBox.information(self, "Копирование", "Разметка скопирована")

    def paste_annotation(self, item: QListWidgetItem):
        if self.copied_annotation is None:
            return
        media_item = item.data(Qt.UserRole)
        media_item.annotation = self.copied_annotation
        QMessageBox.information(self, "Вставка", "Разметка вставлена")
        self.refresh_list()

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    widget = MediaImporterWidget()
    widget.setWindowTitle("Импорт изображений и видео")
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())
