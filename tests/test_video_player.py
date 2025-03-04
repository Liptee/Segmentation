import unittest
import sys
import numpy as np

from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtMultimedia import QMediaPlayer, QVideoProbe
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtCore import Qt

# Monkey-patch для QVideoProbe, чтобы setSource всегда возвращал True (для тестовой среды)
original_setSource = QVideoProbe.setSource
def dummy_setSource(self, source):
    return True
QVideoProbe.setSource = dummy_setSource

# Импортируем тестируемый класс
from gui.video_player import VideoPlayer
from gui.utils import convert_qimage_to_np, convert_np_to_qimage

# Создаём экземпляр QApplication, если его ещё нет
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


# Фейковый медиаплеер для имитации поведения QMediaPlayer
class FakeMediaPlayer:
    def __init__(self):
        self._state = QMediaPlayer.StoppedState
        self._position = 0
        self._duration = 10000  # 10 секунд (в мс)
        self._media = None

    def setMedia(self, media):
        self._media = media

    def media(self):
        return self._media

    def play(self):
        self._state = QMediaPlayer.PlayingState

    def pause(self):
        self._state = QMediaPlayer.PausedState

    def stop(self):
        self._state = QMediaPlayer.StoppedState

    def state(self):
        return self._state

    def setPosition(self, pos):
        self._position = pos

    def position(self):
        return self._position

    def duration(self):
        return self._duration

    def errorString(self):
        return "Test error"


class TestVideoPlayer(unittest.TestCase):
    def setUp(self):
        self.player = VideoPlayer()
        # Подменяем реальный медиаплеер на фейковый
        self.fake_player = FakeMediaPlayer()
        self.player.mediaPlayer = self.fake_player
        # Переопределяем videoWidget.showOverlayIcon, чтобы отслеживать его вызовы
        self.overlay_state = None
        def fake_showOverlayIcon(state):
            self.overlay_state = state
        self.player.videoWidget.showOverlayIcon = fake_showOverlayIcon

    def test_initial_state(self):
        self.assertEqual(self.player.currentIndex, -1)
        self.assertEqual(self.player.playlist, [])
        self.assertEqual(self.player.slider.value(), 0)
        self.assertEqual(self.player.labelDuration.text(), "00:00 / 00:00")

    def test_load_video(self):
        test_path = "/fake/path/video.mp4"
        self.player.load_video(test_path)
        self.assertIsNotNone(self.fake_player.media())
        self.assertEqual(self.player.playButton.text(), "Play")
        self.assertEqual(self.player.slider.value(), 0)
        self.assertEqual(self.fake_player.state(), QMediaPlayer.PausedState)

    def test_toggle_play(self):
        self.fake_player._state = QMediaPlayer.PausedState
        self.player.toggle_play()
        self.assertEqual(self.fake_player.state(), QMediaPlayer.PlayingState)
        self.assertEqual(self.player.playButton.text(), "Pause")
        self.assertEqual(self.overlay_state, QMediaPlayer.PlayingState)
        self.player.toggle_play()
        self.assertEqual(self.fake_player.state(), QMediaPlayer.PausedState)
        self.assertEqual(self.player.playButton.text(), "Play")
        self.assertEqual(self.overlay_state, QMediaPlayer.PausedState)

    def test_step_frame_forward(self):
        self.fake_player._position = 1000
        self.fake_player._duration = 5000
        initial_pos = self.fake_player._position
        self.player.step_frame_forward()
        self.assertEqual(self.fake_player._position, initial_pos + self.player.frame_duration)
        self.fake_player._position = 4990
        self.player.step_frame_forward()
        self.assertLessEqual(self.fake_player._position, self.fake_player._duration)

    def test_step_frame_backward(self):
        self.fake_player._position = 1000
        initial_pos = self.fake_player._position
        self.player.step_frame_backward()
        self.assertEqual(self.fake_player._position, initial_pos - self.player.frame_duration)
        self.fake_player._position = 20
        self.player.step_frame_backward()
        self.assertEqual(self.fake_player._position, 0)

    def test_set_position(self):
        self.player.set_position(2000)
        self.assertEqual(self.fake_player._position, 2000)

    def test_convert_qimage_to_np(self):
        # Проверяем функцию convert_qimage_to_np
        # Создаем QImage в формате RGB888 и заливаем его красным цветом
        test_img = QImage(100, 50, QImage.Format_RGB888)
        test_img.fill(QColor(Qt.red))
        arr = convert_qimage_to_np(test_img)
        self.assertIsNotNone(arr)
        self.assertEqual(arr.shape, (50, 100, 3))
        # Ожидаем, что первый пиксель будет [255, 0, 0]
        expected = np.array([255, 0, 0])
        self.assertTrue((arr[0, 0] == expected).all(), f"Expected {expected} but got {arr[0, 0]}")

    def test_convert_np_to_qimage(self):
        # Создаем тестовый массив RGB
        np_arr = np.full((50, 100, 3), fill_value=0, dtype=np.uint8)
        np_arr[..., 0] = 255  # красный канал
        qimg = convert_np_to_qimage(np_arr)
        self.assertIsInstance(qimg, QImage)
        self.assertEqual(qimg.width(), 100)
        self.assertEqual(qimg.height(), 50)
        # Преобразуем обратно, чтобы проверить цвет первого пикселя
        arr2 = convert_qimage_to_np(qimg)
        expected = np.array([255, 0, 0])
        self.assertTrue((arr2[0, 0] == expected).all(), f"Expected {expected} but got {arr2[0, 0]}")

    def test_get_current_frame_qimage(self):
        # Если current_frame = None, функция должна вернуть None
        self.player.current_frame = None
        qimg = self.player.get_current_frame_qimage()
        self.assertIsNone(qimg)
        # Создаем тестовое QImage
        test_img = QImage(100, 50, QImage.Format_RGB888)
        test_img.fill(QColor(Qt.red))
        self.player.current_frame = test_img
        qimg = self.player.get_current_frame_qimage()
        self.assertIsNotNone(qimg)
        self.assertEqual(qimg.width(), 100)
        self.assertEqual(qimg.height(), 50)

    def test_process_frame_valid(self):
        # Тестируем корректную обработку валидного кадра
        try:
            from PyQt5.QtMultimedia import QVideoFrame
            img = QImage(100, 50, QImage.Format_RGB888)
            img.fill(QColor(Qt.red))
            frame = QVideoFrame(img)
        except Exception:
            # Если конструктор QVideoFrame недоступен, создаем фиктивный объект
            class FakeVideoFrame:
                def __init__(self, image):
                    self._image = image
                def isValid(self):
                    return True
                def map(self, mode):
                    pass
                def unmap(self):
                    pass
                def bits(self):
                    return self._image.bits()
                def width(self):
                    return self._image.width()
                def height(self):
                    return self._image.height()
                def bytesPerLine(self):
                    return self._image.bytesPerLine()
                def pixelFormat(self):
                    from PyQt5.QtMultimedia import QVideoFrame
                    return QVideoFrame.Format_RGB888
            frame = FakeVideoFrame(img)

        self.player.current_frame = None
        self.player.process_frame(frame)
        self.assertIsNotNone(self.player.current_frame)
        self.assertEqual(self.player.current_frame.width(), 100)
        self.assertEqual(self.player.current_frame.height(), 50)
        arr = convert_qimage_to_np(self.player.current_frame)
        self.assertIsNotNone(arr)
        self.assertEqual(arr.shape, (50, 100, 3))
        expected = np.array([255, 0, 0])
        self.assertTrue((arr[0, 0] == expected).all(), f"Expected {expected} but got {arr[0, 0]}")

    def test_process_frame_invalid(self):
        # Тестируем обработку невалидного кадра
        class FakeInvalidFrame:
            def isValid(self):
                return False
            def map(self, mode):
                pass
            def unmap(self):
                pass
        invalid_frame = FakeInvalidFrame()
        self.player.current_frame = None
        self.player.process_frame(invalid_frame)
        self.assertIsNone(self.player.current_frame)

    def test_open_video_unexpected(self):
        # Имитируем ситуацию, когда пользователь отменяет выбор видео
        original_getOpenFileNames = QFileDialog.getOpenFileNames
        QFileDialog.getOpenFileNames = lambda *args, **kwargs: ([], "")
        self.player.open_video()
        self.assertEqual(self.player.playlist, [])
        self.assertEqual(self.player.currentIndex, -1)
        QFileDialog.getOpenFileNames = original_getOpenFileNames
