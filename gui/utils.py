import numpy as np
from PyQt5.QtGui import QImage


def convert_qimage_to_np(qimage):
    if qimage is None:
        return None
    # Приводим изображение к формату RGB888 (без альфа)
    image = qimage.convertToFormat(QImage.Format_RGB888)
    width = image.width()
    height = image.height()
    ptr = image.bits()
    ptr.setsize(height * width * 3)
    arr = np.array(ptr).reshape(height, width, 3)
    return arr


def convert_np_to_qimage(np_array):
    if np_array is None:
        return None
    height, width, channels = np_array.shape
    assert channels == 3, "Ожидается массив с 3 каналами (RGB)"
    bytes_per_line = width * 3
    image = QImage(np_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
    return image.copy()
