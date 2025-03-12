from PyQt5.QtCore import QRectF, QPointF

class GeometryUtils:
    @staticmethod
    def normalize_rect(rect: QRectF, image_rect: QRectF) -> QRectF:
        """
        Преобразует абсолютный прямоугольник в нормализованный (координаты от 0 до 1)
        (Converts an absolute rectangle to normalized coordinates (0 to 1)). 
        """
        norm_x = (rect.x() - image_rect.x()) / image_rect.width()
        norm_y = (rect.y() - image_rect.y()) / image_rect.height()
        norm_width = rect.width() / image_rect.width()
        norm_height = rect.height() / image_rect.height()
        return QRectF(norm_x, norm_y, norm_width, norm_height)

    @staticmethod
    def denormalize_rect(norm_rect: QRectF, image_rect: QRectF) -> QRectF:
        """
        Преобразует нормализованный прямоугольник (от 0 до 1) в абсолютный
        (Converts a normalized rectangle (0 to 1) to absolute coordinates).
        """
        x = norm_rect.x() * image_rect.width() + image_rect.x()
        y = norm_rect.y() * image_rect.height() + image_rect.y()
        width = norm_rect.width() * image_rect.width()
        height = norm_rect.height() * image_rect.height()
        return QRectF(x, y, width, height)

    @staticmethod
    def normalize_points(points: list, image_rect: QRectF) -> list:
        """
        Преобразует список точек в нормализованные координаты (от 0 до 1)
        (Converts a list of points to normalized coordinates).
        """
        return [
            QPointF((p.x() - image_rect.x()) / image_rect.width(),
                    (p.y() - image_rect.y()) / image_rect.height())
            for p in points
        ]

    @staticmethod
    def denormalize_points(norm_points: list, image_rect: QRectF) -> list:
        """
        Преобразует список нормализованных точек (от 0 до 1) в абсолютные координаты
        (Converts a list of normalized points (0 to 1) to absolute coordinates).
        """
        return [
            QPointF(p.x() * image_rect.width() + image_rect.x(),
                    p.y() * image_rect.height() + image_rect.y())
            for p in norm_points
        ]