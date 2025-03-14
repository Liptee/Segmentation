import numpy as np
from PyQt5.QtGui import QImage


def convert_qimage_to_np(qimage):
    if qimage is None:
        return None
    qimage = qimage.convertToFormat(QImage.Format_RGB888)
    width = qimage.width()
    height = qimage.height()
    bpl = qimage.bytesPerLine()
    ptr = qimage.bits()
    ptr.setsize(bpl * height)
    arr = np.array(ptr).reshape(height, bpl, 1)  
    # получаем массив байт для каждой строки
    # Обрезаем до нужной ширины пикселей (width * 3), т.к. формат RGB
    # это связано с тем, что в QImage ширина и высота должны быть четными
    arr = arr[:, :width * 3].reshape(height, width, 3)
    return arr

def convert_np_to_qimage(np_array):
    if np_array is None:
        return None
    height, width, channels = np_array.shape
    assert channels == 3, "Ожидается массив с 3 каналами (RGB)"
    bytes_per_line = width * 3
    image = QImage(np_array.tobytes(), width, height, bytes_per_line, QImage.Format_RGB888)
    return image.copy()

def ms_to_str(ms):
    """Convert milliseconds to a time string (MM:SS)"""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
