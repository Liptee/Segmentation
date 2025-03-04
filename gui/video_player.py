# gui/video_player.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QFileDialog, QLabel, QStyle, QSizePolicy
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QVideoProbe, QAbstractVideoBuffer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QImage, QIcon
import numpy as np

class ClickableVideoWidget(QVideoWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlay_icon = None
        self.overlay_visible = False
        self.overlay_timer = QTimer(self)
        self.overlay_timer.setSingleShot(True)
        self.overlay_timer.timeout.connect(self.hideOverlay)

    def mousePressEvent(self, event):
        self.clicked.emit()
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = ClickableVideoWidget()
        self.videoWidget.clicked.connect(self.toggle_play)

        # Кнопки управления
        self.openButton = QPushButton("Открыть")
        self.openButton.clicked.connect(self.open_video)
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
        controlLayout.addWidget(self.openButton)
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
        if self.videoProbe.setSource(self.mediaPlayer):
            self.videoProbe.videoFrameProbed.connect(self.process_frame)
        else:
            print("Ошибка: не удалось установить QVideoProbe")
        self.current_frame = None

        self.playlist = []      
        self.currentIndex = -1  
        self.frame_duration = 40  # 40 мс, ~25 fps

    def open_video(self):
        fileNames, _ = QFileDialog.getOpenFileNames(
            self, "Открыть видео файлы", "",
            "Видео файлы (*.mp4 *.avi *.mov *.mkv);;Все файлы (*)"
        )
        if fileNames:
            self.playlist.extend(fileNames)
            if self.currentIndex == -1:
                self.currentIndex = 0
                self.load_video(self.playlist[self.currentIndex])

    def load_video(self, video_path):
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
        def ms_to_str(ms):
            seconds = ms // 1000
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        self.labelDuration.setText(f"{ms_to_str(position)} / {ms_to_str(duration)}")

    def handle_error(self):
        error_string = self.mediaPlayer.errorString()
        print("Ошибка:", error_string)

    def process_frame(self, frame):
        if frame.isValid():
            frame.map(QAbstractVideoBuffer.ReadOnly)
            image_format = QVideoFrame.imageFormatFromPixelFormat(frame.pixelFormat())
            if image_format != QImage.Format_Invalid:
                img = QImage(frame.bits(), frame.width(), frame.height(), frame.bytesPerLine(), image_format)
                self.current_frame = img.copy()
            frame.unmap()

    def get_current_frame_qimage(self):
        return self.current_frame

    @staticmethod
    def convert_qimage_to_np(qimage):
        if qimage is None:
            return None
        image = qimage.convertToFormat(QImage.Format_RGB888)
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 3)
        arr = np.array(ptr).reshape(height, width, 3)
        return arr

    @staticmethod
    def convert_np_to_qimage(np_array):
        if np_array is None:
            return None
        height, width, channels = np_array.shape
        assert channels == 3, "Ожидается массив с 3 каналами (RGB)"
        bytes_per_line = width * 3
        image = QImage(np_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
        return image.copy()

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.setWindowTitle("Тестовый VideoPlayer")
    player.resize(800, 600)
    player.show()
    sys.exit(app.exec_())
