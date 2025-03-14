from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QFileDialog, QLabel, QStyle, QSizePolicy,
    QMenu, QAction, QMessageBox, QShortcut
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QVideoProbe, QAbstractVideoBuffer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QPainter, QImage, QIcon, QKeySequence
import numpy as np
import os
import tempfile
import uuid
import cv2
from logger import logger

from gui.utils import ms_to_str, convert_qimage_to_np

class ClickableVideoWidget(QVideoWidget):
    clicked = pyqtSignal()
    rightClicked = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlay_icon = None
        self.overlay_visible = False
        self.overlay_timer = QTimer(self)
        self.overlay_timer.setSingleShot(True)
        self.overlay_timer.timeout.connect(self.hideOverlay)
        # Разрешаем контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.rightClicked.emit(event.pos())
        super().mousePressEvent(event)

    def showOverlayIcon(self, state):
        style = self.style()
        if state == QMediaPlayer.PlayingState:
            self.overlay_icon = style.standardIcon(QStyle.SP_MediaPause).pixmap(64, 64)
        else:
            self.overlay_icon = style.standardIcon(QStyle.SP_MediaPlay).pixmap(64, 64)
        self.overlay_visible = True
        self.overlay_timer.start(1000)  # показываем иконку 1 секунду
        self.update()

    def hideOverlay(self):
        self.overlay_visible = False
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.overlay_visible and self.overlay_icon:
            painter = QPainter(self)
            widget_size = self.size()
            icon_size = self.overlay_icon.size()
            x = (widget_size.width() - icon_size.width()) // 2
            y = (widget_size.height() - icon_size.height()) // 2
            painter.drawPixmap(x, y, self.overlay_icon)

class VideoPlayer(QWidget):
    # Сигнал для уведомления о сохранении кадра
    frameSaved = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = ClickableVideoWidget()
        self.videoWidget.clicked.connect(self.toggle_play)
        self.videoWidget.rightClicked.connect(self.show_context_menu)
        self.videoWidget.customContextMenuRequested.connect(self.show_context_menu)

        # Кнопки управления
        self.saveFrameButton = QPushButton("Сохранить кадр")
        self.saveFrameButton.clicked.connect(self.save_current_frame)
        self.playButton = QPushButton("Play")
        self.playButton.clicked.connect(self.toggle_play)
        # Слайдер и метка времени
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.labelDuration = QLabel("00:00 / 00:00")

        # Создаем отдельный виджет для панели управления и задаем ему минимальную высоту
        controlWidget = QWidget()
        controlLayout = QHBoxLayout(controlWidget)
        controlLayout.setContentsMargins(5, 2, 5, 2)  # уменьшенные отступы
        controlLayout.setSpacing(5)
        controlLayout.addWidget(self.saveFrameButton)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.slider)
        controlLayout.addWidget(self.labelDuration)
        # Устанавливаем политику размера для контроля высоты панели
        controlWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controlWidget.setMaximumHeight(40)  # фиксированная максимальная высота панели управления

        # Основное расположение
        layout = QVBoxLayout()
        layout.addWidget(self.videoWidget)
        layout.addWidget(controlWidget)
        self.setLayout(layout)

        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.positionChanged.connect(self.position_changed)
        self.mediaPlayer.durationChanged.connect(self.duration_changed)
        self.mediaPlayer.error.connect(self.handle_error)

        self.videoProbe = QVideoProbe(self)
        self.current_frame = None

        self.currentIndex = -1  
        self.frame_duration = 40  # 40 мс, ~25 fps
        self.current_video_path = None  # Добавляем переменную для отслеживания текущего пути к видео
        
        # Настраиваем горячие клавиши
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Настраивает горячие клавиши"""
        # Клавиша S для сохранения кадра
        save_shortcut = QShortcut(QKeySequence("S"), self)
        save_shortcut.activated.connect(self.save_current_frame)
        
        # Клавиша O для открытия видео
        open_shortcut = QShortcut(QKeySequence("O"), self)
        open_shortcut.activated.connect(self.open_video)
        
        # Клавиша пробел для воспроизведения/паузы
        play_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        play_shortcut.activated.connect(self.toggle_play)
        
        # Стрелки влево/вправо для перемотки
        forward_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        forward_shortcut.activated.connect(lambda: self.seek_relative(5000))  # +5 секунд
        
        backward_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        backward_shortcut.activated.connect(lambda: self.seek_relative(-5000))  # -5 секунд
    
    def seek_relative(self, ms):
        """Перематывает видео относительно текущей позиции"""
        current_pos = self.mediaPlayer.position()
        new_pos = max(0, current_pos + ms)
        self.mediaPlayer.setPosition(new_pos)

    def save_current_frame(self):
        """Сохраняет текущий кадр видео во временную папку и экспортирует его в MediaImporter"""
        # Проверяем, загружено ли видео
        if self.mediaPlayer.media().isNull():
            QMessageBox.warning(self, "Ошибка", "Нет загруженного видео.")
            return
            
        # Пробуем разные методы получения кадра
        frame_image = None
        
        # Метод 1: Использовать уже проанализированный кадр через QVideoProbe
        if self.current_frame is not None:
            frame_image = self.current_frame
        
        # Метод 2: Делаем скриншот с видеовиджета
        if frame_image is None:
            frame_image = self.videoWidget.grab().toImage()
            # Проверим, не пустой ли это кадр (все черное)
            if self.is_empty_frame(frame_image):
                frame_image = None
        
        # Метод 3: Используем OpenCV для получения кадра из видеофайла
        if frame_image is None and self.current_video_path:
            try:
                cap = cv2.VideoCapture(self.current_video_path)
                if cap.isOpened():
                    # Если видео воспроизводится, устанавливаем положение кадра
                    position_ms = self.mediaPlayer.position()
                    frame_position = int((position_ms / 1000.0) * cap.get(cv2.CAP_PROP_FPS))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
                    ret, cv_frame = cap.read()
                    if ret:
                        # Преобразуем BGR в RGB
                        cv_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
                        height, width, channel = cv_frame.shape
                        bytes_per_line = 3 * width
                        frame_image = QImage(cv_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
                    cap.release()
            except Exception as e:
                logger.info(f"VideoPlayer: Ошибка OpenCV: {e}")
        
        if frame_image is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить кадр из видео.")
            return
        
        # Создаем временную директорию, если она еще не существует
        temp_dir = os.path.join(tempfile.gettempdir(), "video_frames")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Генерируем уникальное имя файла
        frame_path = os.path.join(temp_dir, f"frame_{uuid.uuid4()}.png")
        
        # Сохраняем кадр
        if frame_image.save(frame_path, "PNG"):
            # Сообщаем MediaImporter о новом кадре
            self.frameSaved.emit(frame_path)
            logger.info(f"VideoPlayer: Кадр сохранен: {frame_path}")
            
            # Показываем уведомление о сохранении
            self.show_save_notification()
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось сохранить кадр.")
            
    def is_empty_frame(self, qimage):
        """Проверяет, является ли кадр полностью черным (или почти черным)"""
        if qimage is None:
            return True
            
        # Преобразуем QImage в NumPy массив для анализа
        np_array = convert_qimage_to_np(qimage)
        if np_array is None:
            return True
            
        # Проверяем средние значения пикселей (если очень низкие, то кадр почти черный)
        mean = np.mean(np_array)
        return mean < 10  # Если средняя яркость меньше 10, считаем кадр пустым
    
    def show_save_notification(self):
        """Показывает кратковременное уведомление о сохранении кадра"""
        # Создаем временный текст поверх видео
        save_label = QLabel("✓ Кадр сохранен", self.videoWidget)
        save_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 150);
            color: white;
            border-radius: 5px;
            padding: 10px;
            font-size: 14px;
        """)
        save_label.setAlignment(Qt.AlignCenter)
        
        # Размещаем в центре видео
        save_label.adjustSize()
        w = save_label.width()
        h = save_label.height()
        x = (self.videoWidget.width() - w) // 2
        y = (self.videoWidget.height() - h) // 2
        save_label.move(x, y)
        
        # Показываем
        save_label.show()
        
        # Удаляем через 2 секунды
        QTimer.singleShot(2000, save_label.deleteLater)

    def open_video(self):
        fileNames, _ = QFileDialog.getOpenFileNames(
            self, "Открыть видео файлы", "",
            "Видео файлы (*.mp4 *.avi *.mov *.mkv);;Все файлы (*)"
        )
        if fileNames:
            self.playlist = fileNames
            self.currentIndex = 0
            self.load_video(self.playlist[self.currentIndex])
            
            # Пробуем предзагрузить первый кадр для проверки и отображения
            self.preload_first_frame()
    
    def preload_first_frame(self):
        """Предзагружает первый кадр видео для отображения и проверки"""
        if not self.current_video_path:
            return
            
        try:
            # Открываем видео через OpenCV
            cap = cv2.VideoCapture(self.current_video_path)
            if cap.isOpened():
                ret, cv_frame = cap.read()
                if ret:
                    # Преобразуем BGR в RGB
                    cv_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
                    height, width, channel = cv_frame.shape
                    bytes_per_line = 3 * width
                    # Сохраняем первый кадр
                    self.current_frame = QImage(cv_frame.data, width, height, bytes_per_line, QImage.Format_RGB888).copy()
                    logger.info("VideoPlayer: Первый кадр успешно загружен")
                cap.release()
        except Exception as e:
            logger.info(f"VideoPlayer: Ошибка при предзагрузке кадра: {e}")

    def load_video(self, video_path):
        self.current_video_path = video_path  # Сохраняем путь к видео
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
        self.playButton.setText("Play")
        self.slider.setValue(0)
        self.mediaPlayer.pause()

    def toggle_play(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            self.playButton.setText("Play")
        else:
            self.mediaPlayer.play()
            self.playButton.setText("Pause")
        self.videoWidget.showOverlayIcon(self.mediaPlayer.state())

    def set_position(self, position):
        self.mediaPlayer.setPosition(position)

    def position_changed(self, position):
        self.slider.setValue(position)
        duration = self.mediaPlayer.duration()
        self.update_duration_label(position, duration)

    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.update_duration_label(self.mediaPlayer.position(), duration)

    def update_duration_label(self, position, duration):
        self.labelDuration.setText(f"{ms_to_str(position)} / {ms_to_str(duration)}")

    def handle_error(self):
        error_string = self.mediaPlayer.errorString()
        logger.info(f"VideoPlayer: Ошибка: {error_string}")

    def show_context_menu(self, pos):
        """Показывает контекстное меню с опциями для видеоплеера"""
        context_menu = QMenu(self)
        
        # Добавляем действия в меню
        open_action = QAction("Открыть видео...", self)
        open_action.triggered.connect(self.open_video)
        context_menu.addAction(open_action)
        
        save_frame_action = QAction("Сохранить текущий кадр", self)
        save_frame_action.triggered.connect(self.save_current_frame)
        context_menu.addAction(save_frame_action)
        
        # Показываем меню
        context_menu.exec_(self.videoWidget.mapToGlobal(pos))

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.setWindowTitle("Тестовый VideoPlayer")
    player.resize(800, 600)
    player.show()
    sys.exit(app.exec_())
