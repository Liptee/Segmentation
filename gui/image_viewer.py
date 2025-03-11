import cv2
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSlider, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPinchGesture,
    QToolBar, QAction, QSizePolicy, QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsItem
)
from PyQt5.QtGui import (
    QPixmap, QImage, QWheelEvent, QPainter, QCursor, 
    QIcon, QPen, QKeyEvent, QColor, QPolygonF
)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF, QSize, QSizeF
import numpy as np

from gui.utils import convert_qimage_to_np, convert_np_to_qimage
from gui.object_labeler import ObjectLabelerWidget


class PinchableGraphicsView(QGraphicsView):
    """Подкласс QGraphicsView, который захватывает жесты пинча для масштабирования."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grabGesture(Qt.PinchGesture)
        self._current_scale = 1.0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def event(self, event):
        if event.type() == event.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def gestureEvent(self, event):
        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
            changeFlags = pinch.changeFlags()
            if changeFlags & QPinchGesture.ScaleFactorChanged:
                factor = pinch.scaleFactor()
                self._current_scale *= factor
                self.scale(factor, factor)
            return True
        return False


class SelectableRectItem(QGraphicsRectItem):
    """Класс для создания выделяемых и редактируемых прямоугольников"""
    
    # Константы для идентификации маркеров изменения размера
    HANDLE_TOP_LEFT = 0
    HANDLE_TOP_MIDDLE = 1
    HANDLE_TOP_RIGHT = 2
    HANDLE_MIDDLE_LEFT = 3
    HANDLE_MIDDLE_RIGHT = 4
    HANDLE_BOTTOM_LEFT = 5
    HANDLE_BOTTOM_MIDDLE = 6
    HANDLE_BOTTOM_RIGHT = 7
    
    def __init__(self, x, y, w, h, parent=None, scene=None):
        super().__init__(x, y, w, h, parent)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        # Добавляем флаг для обработки событий мыши
        self.setAcceptHoverEvents(True)
        
        # Настройка внешнего вида
        self.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
        self.setBrush(QColor(255, 0, 0, 50))
        
        # Состояние редактирования
        self.is_selected = False
        self.resize_handle_size = 8
        self.resize_handles = []
        self.current_resize_handle = None
        self.mouse_press_pos = None
        self.mouse_press_rect = None
        self.hover_handle = None
        self.scene = scene
        
        # Свойства для класса сегментации
        self.class_id = None
        self.class_name = None
        self.class_color = None
    
    def set_class(self, class_data):
        """Устанавливает класс сегментации для объекта"""
        if class_data is None:
            self.class_id = None
            self.class_name = None
            self.class_color = QColor(255, 0, 0)  # Красный по умолчанию
            print("Устанавливаю None класс для прямоугольника")
        else:
            self.class_id = class_data.get('id')
            self.class_name = class_data.get('name')
            
            # Получаем цвет из строки вида "#RRGGBB"
            color_str = class_data.get('color', '#FF0000')
            print(f"Устанавливаю класс для прямоугольника: {self.class_name}, ID={self.class_id}, цвет={color_str}")
            self.class_color = QColor(color_str)
            
            # Проверка правильности преобразования цвета
            if not self.class_color.isValid():
                print(f"Ошибка: Невалидный цвет {color_str}, использую красный")
                self.class_color = QColor(255, 0, 0)
        
        # Обновляем внешний вид
        self.update_appearance()
    
    def update_appearance(self):
        """Обновляет внешний вид объекта согласно выбранному классу"""
        if self.class_color:
            # Создаем полупрозрачный цвет для заливки
            fill_color = QColor(self.class_color)
            fill_color.setAlpha(50)  # 20% непрозрачность
            
            # Устанавливаем цвет контура и заливки
            self.setPen(QPen(self.class_color, 2, Qt.SolidLine))
            self.setBrush(fill_color)
            
            # Отладочная информация
            print(f"Обновляю внешний вид прямоугольника: ID класса={self.class_id}, цвет={self.class_color.name()}")
        else:
            # Стандартный красный цвет, если класс не выбран
            self.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
            self.setBrush(QColor(255, 0, 0, 50))
            print("Устанавливаю стандартный красный цвет для прямоугольника")
    
    def get_image_rect(self):
        """Получить прямоугольник изображения"""
        # Проверяем если self.scene это экземпляр ImageViewerWidget
        if self.scene and hasattr(self.scene, 'pixmap_item') and self.scene.pixmap_item:
            return self.scene.pixmap_item.boundingRect()
        
        # Проверяем если self.scene._scene это QGraphicsScene с pixmap_item
        if self.scene and hasattr(self.scene, 'scene') and self.scene.scene:
            scene = self.scene.scene
            if hasattr(scene, 'pixmap_item') and scene.pixmap_item:
                return scene.pixmap_item.boundingRect()
        
        # Если не удалось получить через scene, пробуем через сцену, к которой прикреплен элемент
        scene = self.scene()
        if scene:
            # Проверяем, есть ли pixmap_item непосредственно в сцене
            if hasattr(scene, 'pixmap_item') and scene.pixmap_item:
                return scene.pixmap_item.boundingRect()
            
            # Проверяем, есть ли родительский объект с pixmap_item
            if hasattr(scene, 'parent') and scene.parent():
                parent = scene.parent()
                if hasattr(parent, 'pixmap_item') and parent.pixmap_item:
                    return parent.pixmap_item.boundingRect()
        
        # Последняя проверка, если self.scene это что-то другое с pixmap_item как атрибутом
        if hasattr(self.scene, 'pixmap_item') and self.scene.pixmap_item:
            return self.scene.pixmap_item.boundingRect()
            
        return None
    
    def constrain_rect_to_image(self, rect):
        """Ограничивает прямоугольник границами изображения"""
        image_rect = self.get_image_rect()
        if image_rect:
            # Получаем текущую позицию элемента
            item_pos = self.pos()
            
            # Рассчитываем абсолютное положение углов прямоугольника в сцене
            abs_left = item_pos.x() + rect.left()
            abs_right = item_pos.x() + rect.right()
            abs_top = item_pos.y() + rect.top()
            abs_bottom = item_pos.y() + rect.bottom()
            
            # Ограничиваем абсолютные координаты
            new_left = max(image_rect.left(), abs_left)
            new_right = min(image_rect.right(), abs_right)
            new_top = max(image_rect.top(), abs_top)
            new_bottom = min(image_rect.bottom(), abs_bottom)
            
            # Преобразуем обратно в локальные координаты
            new_rect = QRectF(
                new_left - item_pos.x(),
                new_top - item_pos.y(),
                new_right - new_left,
                new_bottom - new_top
            )
            return new_rect
        return rect
    
    def itemChange(self, change, value):
        """Обработка изменений элемента"""
        # Когда меняется позиция прямоугольника, проверяем, не выходит ли он за границы изображения
        if change == QGraphicsItem.ItemPositionChange and self.scene:
            new_pos = value
            image_rect = self.get_image_rect()
            
            if image_rect:
                # Получаем границы прямоугольника
                rect = self.rect()
                
                # Проверяем, не выходит ли прямоугольник за границы изображения
                if new_pos.x() + rect.left() < image_rect.left():
                    new_pos.setX(image_rect.left() - rect.left())
                elif new_pos.x() + rect.right() > image_rect.right():
                    new_pos.setX(image_rect.right() - rect.right())
                
                if new_pos.y() + rect.top() < image_rect.top():
                    new_pos.setY(image_rect.top() - rect.top())
                elif new_pos.y() + rect.bottom() > image_rect.bottom():
                    new_pos.setY(image_rect.bottom() - rect.bottom())
                
                return new_pos
        
        return super().itemChange(change, value)
    
    def handle_at_position(self, pos):
        """Определяет, находится ли указанная позиция над одним из маркеров изменения размера"""
        rect = self.rect()
        handle_size = self.resize_handle_size
        # Верхняя левая точка
        handle_rect = QRectF(rect.left() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_TOP_LEFT
        # Верхняя средняя точка
        handle_rect = QRectF(rect.left() + rect.width()/2 - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_TOP_MIDDLE
        # Верхняя правая точка
        handle_rect = QRectF(rect.right() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_TOP_RIGHT
        # Средняя левая точка
        handle_rect = QRectF(rect.left() - handle_size/2, rect.top() + rect.height()/2 - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_MIDDLE_LEFT
        # Средняя правая точка
        handle_rect = QRectF(rect.right() - handle_size/2, rect.top() + rect.height()/2 - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_MIDDLE_RIGHT
        # Нижняя левая точка
        handle_rect = QRectF(rect.left() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_BOTTOM_LEFT
        # Нижняя средняя точка
        handle_rect = QRectF(rect.left() + rect.width()/2 - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_BOTTOM_MIDDLE
        # Нижняя правая точка
        handle_rect = QRectF(rect.right() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(pos):
            return self.HANDLE_BOTTOM_RIGHT
        # Если не над маркером, возвращаем None
        return None
        
    def mousePressEvent(self, event):
        """Обработка нажатия мыши на прямоугольнике"""
        if event.button() == Qt.LeftButton:
            handle = self.handle_at_position(event.pos())
            if handle is not None and self.isSelected():
                self.current_resize_handle = handle
                self.mouse_press_pos = event.pos()
                self.mouse_press_rect = self.rect()
                event.accept()
                return
                
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """Обработка перемещения мыши с нажатой кнопкой"""
        if self.current_resize_handle is not None:
            # Изменяем размер прямоугольника
            rect = self.rect()
            delta = event.pos() - self.mouse_press_pos
            
            # Создаем копию прямоугольника для изменения
            new_rect = QRectF(rect)
            
            # Обновляем прямоугольник в зависимости от того, какой маркер выбран
            if self.current_resize_handle == self.HANDLE_TOP_LEFT:
                new_rect.setTopLeft(self.mouse_press_rect.topLeft() + delta)
            elif self.current_resize_handle == self.HANDLE_TOP_MIDDLE:
                new_rect.setTop(self.mouse_press_rect.top() + delta.y())
            elif self.current_resize_handle == self.HANDLE_TOP_RIGHT:
                new_rect.setTopRight(self.mouse_press_rect.topRight() + delta)
            elif self.current_resize_handle == self.HANDLE_MIDDLE_LEFT:
                new_rect.setLeft(self.mouse_press_rect.left() + delta.x())
            elif self.current_resize_handle == self.HANDLE_MIDDLE_RIGHT:
                new_rect.setRight(self.mouse_press_rect.right() + delta.x())
            elif self.current_resize_handle == self.HANDLE_BOTTOM_LEFT:
                new_rect.setBottomLeft(self.mouse_press_rect.bottomLeft() + delta)
            elif self.current_resize_handle == self.HANDLE_BOTTOM_MIDDLE:
                new_rect.setBottom(self.mouse_press_rect.bottom() + delta.y())
            elif self.current_resize_handle == self.HANDLE_BOTTOM_RIGHT:
                new_rect.setBottomRight(self.mouse_press_rect.bottomRight() + delta)
                
            # Ограничиваем прямоугольник границами изображения
            constrained_rect = self.constrain_rect_to_image(new_rect)
            
            # Устанавливаем новый прямоугольник
            self.setRect(constrained_rect)
            event.accept()
            return
            
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания кнопки мыши"""
        if event.button() == Qt.LeftButton and self.current_resize_handle is not None:
            self.current_resize_handle = None
            self.mouse_press_pos = None
            self.mouse_press_rect = None
            event.accept()
            return
        
        super().mouseReleaseEvent(event)
    
    def cursor_for_handle(self, handle):
        """Возвращает соответствующий курсор для маркера изменения размера"""
        if handle == self.HANDLE_TOP_LEFT or handle == self.HANDLE_BOTTOM_RIGHT:
            return Qt.SizeFDiagCursor
        elif handle == self.HANDLE_TOP_RIGHT or handle == self.HANDLE_BOTTOM_LEFT:
            return Qt.SizeBDiagCursor
        elif handle == self.HANDLE_TOP_MIDDLE or handle == self.HANDLE_BOTTOM_MIDDLE:
            return Qt.SizeVerCursor
        elif handle == self.HANDLE_MIDDLE_LEFT or handle == self.HANDLE_MIDDLE_RIGHT:
            return Qt.SizeHorCursor
        else:
            return Qt.ArrowCursor

    def hoverMoveEvent(self, event):
        """Обработка движения мыши над прямоугольником без нажатия кнопки"""
        if self.isSelected():
            handle = self.handle_at_position(event.pos())
            if handle != self.hover_handle:
                self.hover_handle = handle
                if handle is not None:
                    self.setCursor(self.cursor_for_handle(handle))
                else:
                    self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Обработка выхода курсора за пределы прямоугольника"""
        self.hover_handle = None
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget):
        """Отрисовка прямоугольника и маркеров изменения размера"""
        # Отрисовка основного прямоугольника
        super().paint(painter, option, widget)
        
        # Если прямоугольник выбран, рисуем маркеры изменения размера
        if self.isSelected():
            rect = self.rect()
            handle_size = self.resize_handle_size
            
            # Рисуем маркеры в углах и по центрам сторон
            painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
            painter.setBrush(QColor(255, 255, 255))
            
            # Верхний левый угол
            painter.drawRect(QRectF(rect.left() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size))
            # Верхний правый угол
            painter.drawRect(QRectF(rect.right() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size))
            # Нижний левый угол
            painter.drawRect(QRectF(rect.left() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size))
            # Нижний правый угол
            painter.drawRect(QRectF(rect.right() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size))
            
            # Центр верхней стороны
            painter.drawRect(QRectF(rect.center().x() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size))
            # Центр нижней стороны
            painter.drawRect(QRectF(rect.center().x() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size))
            # Центр левой стороны
            painter.drawRect(QRectF(rect.left() - handle_size/2, rect.center().y() - handle_size/2, handle_size, handle_size))
            # Центр правой стороны
            painter.drawRect(QRectF(rect.right() - handle_size/2, rect.center().y() - handle_size/2, handle_size, handle_size))


class SelectablePolygonItem(QGraphicsPolygonItem):
    """Класс для создания выделяемых и редактируемых полигонов"""
    
    def __init__(self, points=None, parent=None, scene=None):
        """Инициализация полигона
        
        Args:
            points: Список точек полигона (QPointF)
            parent: Родительский элемент
            scene: Сцена, к которой привязан полигон (для получения границ изображения)
        """
        # Создаем полигон из списка точек
        polygon = QPolygonF(points if points else [])
        super().__init__(polygon, parent)
        
        # Установка внешнего вида
        self.setPen(QPen(QColor(0, 255, 0), 2))
        self.setBrush(QColor(0, 255, 0, 50))
        
        # Установка флагов для интерактивности
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        
        # Переменные для отслеживания состояния
        # Сохраняем копию точек, чтобы не потерять оригинальные данные
        self.points = points.copy() if points else []
        self.handle_size = 8
        self.current_point_index = None
        self.mouse_press_pos = None
        self.scene = scene
        
        # Свойства для класса сегментации
        self.class_id = None
        self.class_name = None
        self.class_color = None
        
        # Установка обработки наведения мыши
        self.setAcceptHoverEvents(True)
    
    def set_class(self, class_data):
        """Устанавливает класс сегментации для объекта"""
        if class_data is None:
            self.class_id = None
            self.class_name = None
            self.class_color = QColor(0, 255, 0)  # Зеленый по умолчанию для полигонов
            print("Устанавливаю None класс для полигона")
        else:
            self.class_id = class_data.get('id')
            self.class_name = class_data.get('name')
            
            # Получаем цвет из строки вида "#RRGGBB"
            color_str = class_data.get('color', '#00FF00')
            print(f"Устанавливаю класс для полигона: {self.class_name}, ID={self.class_id}, цвет={color_str}")
            self.class_color = QColor(color_str)
            
            # Проверка правильности преобразования цвета
            if not self.class_color.isValid():
                print(f"Ошибка: Невалидный цвет {color_str}, использую зеленый")
                self.class_color = QColor(0, 255, 0)
        
        # Обновляем внешний вид
        self.update_appearance()
    
    def update_appearance(self):
        """Обновляет внешний вид объекта согласно выбранному классу"""
        if self.class_color:
            # Создаем полупрозрачный цвет для заливки
            fill_color = QColor(self.class_color)
            fill_color.setAlpha(50)  # 20% непрозрачность
            
            # Устанавливаем цвет контура и заливки
            self.setPen(QPen(self.class_color, 2, Qt.SolidLine))
            self.setBrush(fill_color)
            
            # Отладочная информация
            print(f"Обновляю внешний вид полигона: ID класса={self.class_id}, цвет={self.class_color.name()}")
        else:
            # Стандартный зеленый цвет, если класс не выбран
            self.setPen(QPen(QColor(0, 255, 0), 2, Qt.SolidLine))
            self.setBrush(QColor(0, 255, 0, 50))
            print("Устанавливаю стандартный зеленый цвет для полигона")
    
    def get_image_rect(self):
        """Получить прямоугольник изображения"""
        # Проверяем если self.scene это экземпляр ImageViewerWidget
        if self.scene and hasattr(self.scene, 'pixmap_item') and self.scene.pixmap_item:
            return self.scene.pixmap_item.boundingRect()
        
        # Проверяем если self.scene._scene это QGraphicsScene с pixmap_item
        if self.scene and hasattr(self.scene, 'scene') and self.scene.scene:
            scene = self.scene.scene
            if hasattr(scene, 'pixmap_item') and scene.pixmap_item:
                return scene.pixmap_item.boundingRect()
        
        # Если не удалось получить через scene, пробуем через сцену, к которой прикреплен элемент
        scene = self.scene()
        if scene:
            # Проверяем, есть ли pixmap_item непосредственно в сцене
            if hasattr(scene, 'pixmap_item') and scene.pixmap_item:
                return scene.pixmap_item.boundingRect()
            
            # Проверяем, есть ли родительский объект с pixmap_item
            if hasattr(scene, 'parent') and scene.parent():
                parent = scene.parent()
                if hasattr(parent, 'pixmap_item') and parent.pixmap_item:
                    return parent.pixmap_item.boundingRect()
        
        # Последняя проверка, если self.scene это что-то другое с pixmap_item как атрибутом
        if hasattr(self.scene, 'pixmap_item') and self.scene.pixmap_item:
            return self.scene.pixmap_item.boundingRect()
            
        return None
    
    def constrain_point_to_image(self, point):
        """Ограничивает точку границами изображения"""
        image_rect = self.get_image_rect()
        if image_rect:
            # Получаем текущую позицию элемента
            item_pos = self.pos()
            
            # Рассчитываем абсолютное положение точки в сцене
            abs_x = item_pos.x() + point.x()
            abs_y = item_pos.y() + point.y()
            
            # Ограничиваем абсолютные координаты
            new_x = max(image_rect.left(), min(abs_x, image_rect.right()))
            new_y = max(image_rect.top(), min(abs_y, image_rect.bottom()))
            
            # Преобразуем обратно в локальные координаты
            return QPointF(new_x - item_pos.x(), new_y - item_pos.y())
        return point
    
    def itemChange(self, change, value):
        """Обработка изменений элемента"""
        # Когда полигон перемещается, нам нужно обновить отображение,
        # чтобы маркеры точек были отрисованы в правильных позициях
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.update()
        
        # Когда меняется позиция полигона, проверяем, не выходит ли он за границы изображения
        elif change == QGraphicsItem.ItemPositionChange and self.scene:
            new_pos = value
            image_rect = self.get_image_rect()
            
            if image_rect:
                # Получаем границы полигона
                polygon_rect = self.boundingRect()
                
                # Проверяем, не выходит ли полигон за границы изображения
                if new_pos.x() + polygon_rect.left() < image_rect.left():
                    new_pos.setX(image_rect.left() - polygon_rect.left())
                elif new_pos.x() + polygon_rect.right() > image_rect.right():
                    new_pos.setX(image_rect.right() - polygon_rect.right())
                
                if new_pos.y() + polygon_rect.top() < image_rect.top():
                    new_pos.setY(image_rect.top() - polygon_rect.top())
                elif new_pos.y() + polygon_rect.bottom() > image_rect.bottom():
                    new_pos.setY(image_rect.bottom() - polygon_rect.bottom())
                
                return new_pos
        
        return super().itemChange(change, value)
    
    def paint(self, painter, option, widget):
        """Отрисовка полигона и маркеров точек"""
        # Отрисовка основного полигона
        super().paint(painter, option, widget)
        
        # Отрисовка маркеров изменения размера, если элемент выбран
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 0, 255), 1))
            painter.setBrush(QColor(0, 0, 255, 200))
            
            # Отрисовка маркера для каждой точки полигона
            # Используем координаты из полигона, а не из self.points
            polygon = self.polygon()
            for i in range(polygon.count()):
                point = polygon.at(i)
                handle_rect = QRectF(
                    point.x() - self.handle_size/2,
                    point.y() - self.handle_size/2,
                    self.handle_size,
                    self.handle_size
                )
                painter.drawRect(handle_rect)
    
    def point_at_position(self, pos):
        """Определяет, находится ли указанная позиция над одной из точек полигона
        
        Args:
            pos: Позиция проверки (QPointF)
            
        Returns:
            int: Индекс точки или None, если точка не найдена
        """
        polygon = self.polygon()
        for i in range(polygon.count()):
            point = polygon.at(i)
            handle_rect = QRectF(
                point.x() - self.handle_size/2,
                point.y() - self.handle_size/2,
                self.handle_size,
                self.handle_size
            )
            if handle_rect.contains(pos):
                return i
        return None
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши на полигоне"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            # Проверяем, нажата ли одна из точек полигона
            point_index = self.point_at_position(pos)
            if point_index is not None and self.isSelected():
                self.current_point_index = point_index
                self.mouse_press_pos = pos
                event.accept()
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Обработка перемещения мыши с нажатой кнопкой"""
        if self.current_point_index is not None:
            # Перемещаем выбранную точку
            new_pos = event.pos()
            
            # Ограничиваем позицию границами изображения
            constrained_pos = self.constrain_point_to_image(new_pos)
            
            # Получаем текущий полигон и обновляем точку
            polygon = self.polygon()
            polygon.replace(self.current_point_index, constrained_pos)
            
            # Обновляем полигон
            self.setPolygon(polygon)
            event.accept()
            return
        
        # Для перемещения всего полигона используем стандартную обработку
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания кнопки мыши"""
        if self.current_point_index is not None:
            self.current_point_index = None
            self.mouse_press_pos = None
        
        super().mouseReleaseEvent(event)
        
    def hoverMoveEvent(self, event):
        """Обработка перемещения мыши над полигоном"""
        # Изменяем курсор, если мышь находится над точкой полигона
        if self.isSelected() and self.point_at_position(event.pos()) is not None:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Обработка выхода мыши за пределы полигона"""
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)


class CrosshairGraphicsScene(QGraphicsScene):
    """Сцена с отображением перекрестия при выборе инструмента выделения"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_crosshair = False
        self.crosshair_pos = QPointF(0, 0)
        self.image_rect = QRectF()
        
    def setShowCrosshair(self, show):
        self.show_crosshair = show
        self.update()
        
    def setCrosshairPos(self, pos):
        self.crosshair_pos = pos
        self.update()
        
    def setImageRect(self, rect):
        self.image_rect = rect
        
    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        
        if self.show_crosshair and not self.image_rect.isNull() and self.image_rect.contains(self.crosshair_pos):
            # Настраиваем перо для пунктирной линии
            pen = QPen(Qt.red, 1, Qt.DashLine)
            painter.setPen(pen)
            
            # Рисуем горизонтальную линию через всё изображение
            painter.drawLine(
                QPointF(self.image_rect.left(), self.crosshair_pos.y()),
                QPointF(self.image_rect.right(), self.crosshair_pos.y())
            )
            
            # Рисуем вертикальную линию через всё изображение
            painter.drawLine(
                QPointF(self.crosshair_pos.x(), self.image_rect.top()),
                QPointF(self.crosshair_pos.x(), self.image_rect.bottom())
            )


class ImageViewerWidget(QWidget):
    # Сигнал для передачи выбранного изображения (например, для открытия в другом модуле)
    imageSelected = pyqtSignal(str)

    # Режимы работы
    MODE_VIEW = 0
    MODE_RECT_SELECT = 1
    MODE_EDIT = 2
    MODE_POLYGON_SELECT = 3

    def __init__(self, parent=None, class_manager=None):
        super().__init__(parent)
        self.image = None  # Исходное QImage (RGB)
        self.current_adjusted_image = None
        self.original_np = None  # NumPy-массив исходного изображения в формате RGB (float32)
        self.zoom_factor = 1.0
        self.annotations = []  # Текущие активные аннотации для отображаемого изображения
        
        # Словарь для хранения аннотаций для каждого изображения
        # Ключ - путь к изображению, значение - список нормализованных аннотаций
        self.annotations_by_image = {}
        
        # Текущий путь к изображению
        self.current_image_path = None
        
        # Класс-менеджер для связи с классами сегментации
        self.class_manager = class_manager
        
        # Создаем виджет для назначения классов объектам
        self.object_labeler = None
        
        # Переменные для режима выделения прямоугольника
        self.current_mode = self.MODE_VIEW
        self.start_point = None
        self.current_rect = None
        self.selected_item = None
        
        # Переменные для режима выделения полигона
        self.current_polygon = None
        self.polygon_points = []
        self.temp_line = None
        
        self._init_ui()
        self._init_adjustments()
        
    def set_class_manager(self, class_manager):
        """Устанавливает менеджер классов сегментации"""
        self.class_manager = class_manager
        
        # Создаем или обновляем ObjectLabelerWidget
        if self.object_labeler is None:
            self.object_labeler = ObjectLabelerWidget(self, self.class_manager)
            self.object_labeler.classAssigned.connect(self.on_class_assigned)
            self.object_labeler.newClassRequested.connect(self.request_new_class)
        else:
            self.object_labeler.class_manager = class_manager

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Добавляем панель инструментов слева
        self.toolbar = QToolBar("Инструменты")
        self.toolbar.setOrientation(Qt.Vertical)
        self.toolbar.setIconSize(QSize(32, 32))
        
        # Создаем действия для инструментов
        self.action_rect_select = QAction("Выделение", self)
        self.action_rect_select.setCheckable(True)
        self.action_rect_select.triggered.connect(lambda: self.set_tool_mode(self.MODE_RECT_SELECT))
        
        self.action_polygon_select = QAction("Полигоны", self)
        self.action_polygon_select.setCheckable(True)
        self.action_polygon_select.triggered.connect(lambda: self.set_tool_mode(self.MODE_POLYGON_SELECT))
        
        self.action_edit = QAction("Править", self)
        self.action_edit.setCheckable(True)
        self.action_edit.triggered.connect(lambda: self.set_tool_mode(self.MODE_EDIT))
        
        # Добавляем действия на панель инструментов
        self.toolbar.addAction(self.action_rect_select)
        self.toolbar.addAction(self.action_polygon_select)
        self.toolbar.addAction(self.action_edit)
        
        # Добавляем разделитель
        self.toolbar.addSeparator()
        
        # Добавляем действия для экспорта/импорта аннотаций
        self.action_export_annotations = QAction("Экспорт аннотаций", self)
        self.action_export_annotations.triggered.connect(self.show_export_annotations_dialog)
        self.toolbar.addAction(self.action_export_annotations)
        
        self.action_import_annotations = QAction("Импорт аннотаций", self)
        self.action_import_annotations.triggered.connect(self.show_import_annotations_dialog)
        self.toolbar.addAction(self.action_import_annotations)
        
        # Устанавливаем политику размера для панели инструментов
        self.toolbar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
        main_layout.addWidget(self.toolbar)
        
        # Для основного просмотра создаём вертикальное расположение:
        viewer_layout = QVBoxLayout()
        self.scene = CrosshairGraphicsScene(self)
        self.view = PinchableGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        
        # Подключаем обработчики событий мыши для сцены
        self.view.setMouseTracking(True)
        self.view.viewport().installEventFilter(self)
        
        # Настройка для правильной работы с элементами сцены
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        viewer_layout.addWidget(self.view)
        
        # Панель регулировки яркости, контраста, гаммы
        adjust_layout = QHBoxLayout()
        self.slider_brightness = QSlider(Qt.Horizontal)
        self.slider_brightness.setRange(50, 150)
        self.slider_brightness.setValue(100)
        self.slider_contrast = QSlider(Qt.Horizontal)
        self.slider_contrast.setRange(50, 150)
        self.slider_contrast.setValue(100)
        self.slider_gamma = QSlider(Qt.Horizontal)
        self.slider_gamma.setRange(50, 150)
        self.slider_gamma.setValue(100)
        adjust_layout.addWidget(QLabel("Яркость"))
        adjust_layout.addWidget(self.slider_brightness)
        adjust_layout.addWidget(QLabel("Контраст"))
        adjust_layout.addWidget(self.slider_contrast)
        adjust_layout.addWidget(QLabel("Гамма"))
        adjust_layout.addWidget(self.slider_gamma)
        viewer_layout.addLayout(adjust_layout)
        main_layout.addLayout(viewer_layout)
        self.setLayout(main_layout)
        
        # Связываем слайдеры с обработчиком
        self.slider_brightness.valueChanged.connect(self.update_image_adjustments)
        self.slider_contrast.valueChanged.connect(self.update_image_adjustments)
        self.slider_gamma.valueChanged.connect(self.update_image_adjustments)
        
        # Устанавливаем режим просмотра по умолчанию
        self.set_tool_mode(self.MODE_VIEW)
        
        # Устанавливаем фокус на view для обработки клавиатурных событий
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setFocus()

    def _init_adjustments(self):
        self.brightness = 1.0
        self.contrast = 1.0
        self.gamma = 1.0

    def load_image(self, file_path):
        # Сохраняем текущие аннотации перед загрузкой нового изображения
        if self.current_image_path and self.annotations:
            print(f"Сохраняю {len(self.annotations)} аннотаций для {self.current_image_path}")
            self.save_current_annotations()
            
        qimg = QImage(file_path).convertToFormat(QImage.Format_RGB888)
        if qimg.isNull():
            return False
            
        # Если изображение слишком большое, уменьшаем его
        MAX_PIXELS = 2000000
        w = qimg.width()
        h = qimg.height()
        self.image = qimg
        self.original_np = convert_qimage_to_np(self.image)
        if w * h > MAX_PIXELS:
            scale = np.sqrt(MAX_PIXELS / (w * h))
            new_w = int(w * scale)
            new_h = int(h * scale)
            self.original_np = cv2.resize(self.original_np, (new_w, new_h), interpolation=cv2.INTER_AREA)
            self.image = convert_np_to_qimage(self.original_np)

        self.current_adjusted_image = convert_np_to_qimage(self.original_np)
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(self.current_adjusted_image))
        self.scene.addItem(self.pixmap_item)
        
        # Устанавливаем границы изображения для отображения перекрестия
        self.scene.setImageRect(self.pixmap_item.boundingRect())
        
        # Очищаем текущие аннотации
        self.annotations.clear()
        
        # Устанавливаем текущий путь к изображению
        self.current_image_path = file_path
        
        # Загружаем ранее сохраненные аннотации для этого изображения
        self.load_annotations_for_image(file_path)
        
        self.zoom_factor = 1.0
        self.view.resetTransform()

        print(f"Загружено изображение: {file_path}, восстановлено аннотаций: {len(self.annotations)}")
        return True

    def update_image_adjustments(self):
        if self.original_np is None:
            return
        brightness = self.slider_brightness.value() / 100.0  # 1.0 - без изменений
        contrast = self.slider_contrast.value() / 100.0
        gamma = self.slider_gamma.value() / 100.0
        # Векторизированные операции для яркости и контраста:
        adjusted = self.original_np * brightness
        mean = np.mean(adjusted, axis=(0, 1), keepdims=True)
        adjusted = (adjusted - mean) * contrast + mean
        adjusted = np.clip(adjusted, 0, 255)
        # Применяем гамму
        invGamma = 1.0 / gamma
        adjusted = 255.0 * np.power(adjusted / 255.0, invGamma)
        adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)

        self.current_adjusted_image = convert_np_to_qimage(adjusted)
        if self.pixmap_item:
            self.pixmap_item.setPixmap(QPixmap.fromImage(self.current_adjusted_image))

    # Переопределяем wheelEvent только для случаев, когда жесты пинча не срабатывают (например, с мышью)
    def wheelEvent(self, event: QWheelEvent):
        angle = event.angleDelta().y()
        factor = 1.25 if angle > 0 else 0.8
        self.zoom_factor *= factor
        self.view.scale(factor, factor)

    # Методы для преобразования между QImage и NumPy-массивом (RGB)
    def get_current_frame_qimage(self):
        return self.current_adjusted_image
        
    def set_tool_mode(self, mode):
        """Устанавливает текущий режим работы инструмента"""
        self.current_mode = mode
        
        # Сбрасываем состояние всех кнопок
        self.action_rect_select.setChecked(False)
        self.action_polygon_select.setChecked(False)
        self.action_edit.setChecked(False)
        
        # Устанавливаем соответствующий курсор и режим перетаскивания
        if mode == self.MODE_VIEW:
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
            self.view.viewport().setCursor(Qt.OpenHandCursor)
            self.scene.setShowCrosshair(False)
            # Отключаем интерактивность для всех фигур
            for item in self.annotations:
                if isinstance(item, (SelectableRectItem, SelectablePolygonItem)):
                    item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                    item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == self.MODE_RECT_SELECT:
            self.action_rect_select.setChecked(True)
            self.view.setDragMode(QGraphicsView.NoDrag)
            # Устанавливаем курсор-перекрестие
            self.view.viewport().setCursor(Qt.CrossCursor)
            self.scene.setShowCrosshair(True)
            # Отключаем интерактивность для всех фигур
            for item in self.annotations:
                if isinstance(item, (SelectableRectItem, SelectablePolygonItem)):
                    item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                    item.setFlag(QGraphicsItem.ItemIsMovable, False)
        elif mode == self.MODE_POLYGON_SELECT:
            self.action_polygon_select.setChecked(True)
            self.view.setDragMode(QGraphicsView.NoDrag)
            # Устанавливаем курсор-перекрестие
            self.view.viewport().setCursor(Qt.CrossCursor)
            self.scene.setShowCrosshair(True)
            # Отключаем интерактивность для всех фигур
            for item in self.annotations:
                if isinstance(item, (SelectableRectItem, SelectablePolygonItem)):
                    item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                    item.setFlag(QGraphicsItem.ItemIsMovable, False)
            # Сбрасываем точки полигона
            self.polygon_points = []
            if self.temp_line:
                self.scene.removeItem(self.temp_line)
                self.temp_line = None
        elif mode == self.MODE_EDIT:
            self.action_edit.setChecked(True)
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.view.viewport().setCursor(Qt.ArrowCursor)
            self.scene.setShowCrosshair(False)
            # Включаем интерактивность для всех фигур
            for item in self.annotations:
                if isinstance(item, (SelectableRectItem, SelectablePolygonItem)):
                    item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    item.setFlag(QGraphicsItem.ItemIsMovable, True)
            
        # Сбрасываем текущее выделение
        if self.current_rect:
            self.scene.removeItem(self.current_rect)
            self.current_rect = None
        if self.current_polygon:
            self.scene.removeItem(self.current_polygon)
            self.current_polygon = None
        if self.temp_line:
            self.scene.removeItem(self.temp_line)
            self.temp_line = None
        self.start_point = None
        self.polygon_points = []

    def eventFilter(self, obj, event):
        """Обработчик всех событий для виджета просмотра"""
        if obj == self.view.viewport():
            # Обновляем позицию перекрестия при движении мыши
            if event.type() == event.MouseMove and hasattr(self, 'pixmap_item') and self.pixmap_item:
                scene_pos = self.view.mapToScene(event.pos())
                self.scene.setCrosshairPos(scene_pos)
            
            # В режиме редактирования позволяем событиям проходить к элементам сцены
            if self.current_mode == self.MODE_EDIT:
                # Проверяем, что это событие мыши, прежде чем вызывать pos()
                if event.type() in [event.MouseButtonPress, event.MouseButtonRelease, event.MouseMove, event.MouseButtonDblClick]:
                    scene_pos = self.view.mapToScene(event.pos())
                    items = self.scene.items(scene_pos)
                    
                    # Проверяем, есть ли под курсором выделяемый объект
                    for item in items:
                        if isinstance(item, (SelectableRectItem, SelectablePolygonItem)):
                            # Если это двойной клик, показываем диалог выбора класса
                            if event.type() == event.MouseButtonDblClick and event.button() == Qt.LeftButton:
                                # Выбираем объект перед открытием диалога
                                item.setSelected(True)
                                self.selected_item = item
                                
                                # Вызываем диалог выбора класса
                                self.show_object_labeler(item)
                                return True
                            # Если это нажатие кнопки мыши, запоминаем выбранный объект
                            elif event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                                self.selected_item = item
                            
                            # Позволяем событию пройти дальше для обработки элементом
                            return False
            
            # Обрабатываем события для режимов просмотра и выделения
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                return self.handle_mouse_press(event)
            elif event.type() == event.MouseMove:
                return self.handle_mouse_move(event)
            elif event.type() == event.MouseButtonRelease and event.button() == Qt.LeftButton:
                return self.handle_mouse_release(event)
                
        return super().eventFilter(obj, event)
        
    def handle_mouse_press(self, event):
        """Обработка нажатия кнопки мыши"""
        # Получаем координаты в сцене
        scene_pos = self.view.mapToScene(event.pos())
        
        # Проверяем, что точка находится в пределах изображения
        if not hasattr(self, 'pixmap_item') or not self.pixmap_item or not self.pixmap_item.contains(scene_pos):
            return False
            
        # Обрабатываем в режиме выделения прямоугольника
        if self.current_mode == self.MODE_RECT_SELECT:
            self.start_point = scene_pos
            
            # Создаем новый прямоугольник
            self.current_rect = QGraphicsRectItem(QRectF(scene_pos, QSizeF(0, 0)))
            self.current_rect.setPen(QPen(QColor(255, 0, 0), 2, Qt.DashLine))
            self.current_rect.setBrush(QColor(255, 0, 0, 50))
            self.scene.addItem(self.current_rect)
            
            return True
        
        # Обрабатываем в режиме выделения полигона
        elif self.current_mode == self.MODE_POLYGON_SELECT:
            if not self.current_polygon:
                # Начинаем новый полигон
                self.polygon_points = [scene_pos]
                self.current_polygon = QGraphicsPolygonItem(QPolygonF([QPointF(scene_pos.x(), scene_pos.y())]))
                self.current_polygon.setPen(QPen(Qt.red, 2))
                self.scene.addItem(self.current_polygon)
            else:
                # Добавляем новую точку к полигону
                self.polygon_points.append(scene_pos)
                poly = QPolygonF([QPointF(p.x(), p.y()) for p in self.polygon_points])
                self.current_polygon.setPolygon(poly)
            return True
            
        return False
        
    def handle_mouse_move(self, event):
        """Обработка движения мыши"""
        # Получаем текущие координаты в сцене
        current_pos = self.view.mapToScene(event.pos())
        
        # Ограничиваем координаты границами изображения
        if hasattr(self, 'pixmap_item') and self.pixmap_item:
            pixmap_rect = self.pixmap_item.boundingRect()
            current_pos.setX(max(pixmap_rect.left(), min(current_pos.x(), pixmap_rect.right())))
            current_pos.setY(max(pixmap_rect.top(), min(current_pos.y(), pixmap_rect.bottom())))
        
        # Обрабатываем в режиме выделения прямоугольника
        if self.current_mode == self.MODE_RECT_SELECT and self.start_point and hasattr(self, 'current_rect') and self.current_rect:
            # Обновляем прямоугольник
            rect = QRectF(
                min(self.start_point.x(), current_pos.x()),
                min(self.start_point.y(), current_pos.y()),
                abs(current_pos.x() - self.start_point.x()),
                abs(current_pos.y() - self.start_point.y())
            )
            self.current_rect.setRect(rect)
            
            return True
            
        # Обрабатываем в режиме выделения полигона
        elif self.current_mode == self.MODE_POLYGON_SELECT and len(self.polygon_points) > 0:
            # Обновляем временную линию от последней точки до текущей позиции мыши
            if self.temp_line:
                self.scene.removeItem(self.temp_line)
            
            last_point = self.polygon_points[-1]
            self.temp_line = self.scene.addLine(
                last_point.x(), last_point.y(), 
                current_pos.x(), current_pos.y(),
                QPen(QColor(0, 255, 0), 2, Qt.DashLine)
            )
            
            return True
            
        return False
        
    def handle_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        # Обрабатываем в режиме выделения прямоугольника
        if self.current_mode == self.MODE_RECT_SELECT and self.start_point and hasattr(self, 'current_rect') and self.current_rect:
            # Получаем конечные координаты в сцене
            end_point = self.view.mapToScene(event.pos())
            
            # Ограничиваем координаты границами изображения
            if hasattr(self, 'pixmap_item') and self.pixmap_item:
                pixmap_rect = self.pixmap_item.boundingRect()
                end_point.setX(max(pixmap_rect.left(), min(end_point.x(), pixmap_rect.right())))
                end_point.setY(max(pixmap_rect.top(), min(end_point.y(), pixmap_rect.bottom())))
            
            # Создаем финальный прямоугольник
            rect = QRectF(
                min(self.start_point.x(), end_point.x()),
                min(self.start_point.y(), end_point.y()),
                abs(end_point.x() - self.start_point.x()),
                abs(end_point.y() - self.start_point.y())
            )
            
            # Если прямоугольник слишком маленький, игнорируем его
            if rect.width() < 5 or rect.height() < 5:
                self.scene.removeItem(self.current_rect)
            else:
                # Удаляем временный прямоугольник
                self.scene.removeItem(self.current_rect)
                
                # Создаем постоянный прямоугольник
                rect_item = SelectableRectItem(rect.x(), rect.y(), rect.width(), rect.height(), None, self)
                # В режиме выделения прямоугольники не должны быть интерактивными
                rect_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                rect_item.setFlag(QGraphicsItem.ItemIsMovable, False)
                self.scene.addItem(rect_item)
                self.annotations.append(rect_item)
                
                # Показываем диалог выбора класса для нового прямоугольника
                if self.class_manager:
                    self.show_object_labeler(rect_item)
            
            self.current_rect = None
            self.start_point = None
            
            return True
            
        return False
    
    def complete_polygon(self):
        """Завершает создание полигона"""
        if len(self.polygon_points) < 3:
            # Полигон должен иметь хотя бы 3 точки
            return
            
        # Удаляем временный полигон и линию
        if self.current_polygon:
            self.scene.removeItem(self.current_polygon)
        if self.temp_line:
            self.scene.removeItem(self.temp_line)
            self.temp_line = None
            
        # Создаем постоянный полигон
        # Используем copy() для создания копии списка точек
        # Передаем непосредственно сцену для доступа к pixmap_item
        polygon_item = SelectablePolygonItem(self.polygon_points.copy(), None, self)
        
        # Установим еще одну ссылку на scene как объект типа QGraphicsScene
        polygon_item.scene_obj = self.scene
        
        # В режиме выделения полигоны не должны быть интерактивными
        polygon_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        polygon_item.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.scene.addItem(polygon_item)
        self.annotations.append(polygon_item)
        
        # Показываем диалог выбора класса для нового полигона
        if self.class_manager:
            self.show_object_labeler(polygon_item)
        
        # Сбрасываем переменные
        self.current_polygon = None
        self.polygon_points = []

    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатий клавиш"""
        # Удаление выбранных фигур при нажатии Delete или Backspace
        if self.current_mode == self.MODE_EDIT and (event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace):
            for item in self.scene.selectedItems():
                if isinstance(item, (SelectableRectItem, SelectablePolygonItem)):
                    self.scene.removeItem(item)
                    if item in self.annotations:
                        self.annotations.remove(item)
            return
        
        # Вызов диалога выбора класса при нажатии клавиши C
        if self.current_mode == self.MODE_EDIT and event.key() == Qt.Key_C:
            selected_items = self.scene.selectedItems()
            if selected_items and isinstance(selected_items[0], (SelectableRectItem, SelectablePolygonItem)):
                self.show_object_labeler(selected_items[0])
                return
        
        # Замыкание полигона при нажатии клавиши F
        if self.current_mode == self.MODE_POLYGON_SELECT and event.key() == Qt.Key_F:
            if len(self.polygon_points) >= 3:  # Полигон должен иметь хотя бы 3 точки
                self.complete_polygon()
                return
            
        super().keyPressEvent(event)

    def on_class_assigned(self, annotation_object, class_data):
        """Обработчик события назначения класса объекту"""
        if annotation_object and hasattr(annotation_object, 'set_class'):
            # Устанавливаем класс для объекта
            annotation_object.set_class(class_data)
            
            # Явно вызываем обновление сцены для перерисовки объекта
            if self.scene:
                self.scene.update()
    
    def request_new_class(self):
        """Запрашивает создание нового класса через менеджер классов"""
        if self.class_manager and hasattr(self.class_manager, 'openAddClassDialog'):
            # Если диалог выбора класса открыт, сначала закрываем его
            if self.object_labeler and self.object_labeler.isVisible():
                current_object = self.object_labeler.current_object
                self.object_labeler.close()
            else:
                current_object = None
                
            # Открываем диалог добавления класса
            self.class_manager.openAddClassDialog()
            
            # После создания нового класса
            if current_object:
                # Снова открываем диалог выбора класса для текущего объекта
                self.show_object_labeler(current_object)
                
                # Выбираем последний добавленный класс
                classes = self.class_manager.get_all_classes()
                if classes and self.object_labeler:
                    self.object_labeler.class_combo.setCurrentIndex(len(classes))
    
    def show_object_labeler(self, annotation_object):
        """Показывает диалог назначения класса для объекта"""
        if not self.class_manager or not annotation_object:
            print("Не могу показать диалог назначения класса: нет менеджера классов или объекта")
            return
            
        print(f"Показываю диалог назначения класса для объекта типа {type(annotation_object).__name__}")
            
        # Создаем ObjectLabelerWidget, если его еще нет
        if not self.object_labeler:
            self.object_labeler = ObjectLabelerWidget(self, self.class_manager)
            self.object_labeler.classAssigned.connect(self.on_class_assigned)
            self.object_labeler.newClassRequested.connect(self.request_new_class)
        
        # Устанавливаем текущий объект и показываем диалог
        self.object_labeler.set_current_object(annotation_object)
        result = self.object_labeler.exec_()
        
        print(f"Диалог закрылся с результатом: {result} (1=принят, 0=отклонен)")

    def normalize_rect_coords(self, rect):
        """
        Преобразует абсолютные координаты прямоугольника в нормализованные (от 0 до 1)
        """
        if not self.pixmap_item:
            return rect
            
        img_rect = self.pixmap_item.boundingRect()
        img_width = img_rect.width()
        img_height = img_rect.height()
        
        # Нормализуем координаты относительно размеров изображения
        norm_x = (rect.x() - img_rect.x()) / img_width
        norm_y = (rect.y() - img_rect.y()) / img_height
        norm_width = rect.width() / img_width
        norm_height = rect.height() / img_height
        
        return QRectF(norm_x, norm_y, norm_width, norm_height)
    
    def denormalize_rect_coords(self, norm_rect):
        """
        Преобразует нормализованные координаты прямоугольника (от 0 до 1) в абсолютные
        """
        if not self.pixmap_item:
            return norm_rect
            
        img_rect = self.pixmap_item.boundingRect()
        img_width = img_rect.width()
        img_height = img_rect.height()
        
        # Денормализуем координаты относительно размеров изображения
        x = norm_rect.x() * img_width + img_rect.x()
        y = norm_rect.y() * img_height + img_rect.y()
        width = norm_rect.width() * img_width
        height = norm_rect.height() * img_height
        
        return QRectF(x, y, width, height)
    
    def normalize_polygon_points(self, points):
        """
        Преобразует абсолютные координаты точек полигона в нормализованные (от 0 до 1)
        """
        if not self.pixmap_item or not points:
            return points
            
        img_rect = self.pixmap_item.boundingRect()
        img_width = img_rect.width()
        img_height = img_rect.height()
        
        # Нормализуем координаты относительно размеров изображения
        norm_points = []
        for point in points:
            norm_x = (point.x() - img_rect.x()) / img_width
            norm_y = (point.y() - img_rect.y()) / img_height
            norm_points.append(QPointF(norm_x, norm_y))
            
        return norm_points
    
    def denormalize_polygon_points(self, norm_points):
        """
        Преобразует нормализованные координаты точек полигона (от 0 до 1) в абсолютные
        """
        if not self.pixmap_item or not norm_points:
            return norm_points
            
        img_rect = self.pixmap_item.boundingRect()
        img_width = img_rect.width()
        img_height = img_rect.height()
        
        # Денормализуем координаты относительно размеров изображения
        points = []
        for norm_point in norm_points:
            x = norm_point.x() * img_width + img_rect.x()
            y = norm_point.y() * img_height + img_rect.y()
            points.append(QPointF(x, y))
            
        return points
    
    def save_current_annotations(self):
        """
        Сохраняет текущие аннотации для текущего изображения
        """
        if not self.current_image_path:
            return
        
        # Список для хранения нормализованных данных
        normalized_annotations = []
        
        # Обходим все аннотации
        for annotation in self.annotations:
            if isinstance(annotation, SelectableRectItem):
                # Для прямоугольников сохраняем нормализованные координаты и класс
                rect = annotation.rect()
                norm_rect = self.normalize_rect_coords(rect)
                class_data = {
                    'id': annotation.class_id,
                    'name': annotation.class_name,
                    'color': annotation.class_color.name() if annotation.class_color else None
                }
                
                normalized_annotations.append({
                    'type': 'rect',
                    'coords': {
                        'x': norm_rect.x(),
                        'y': norm_rect.y(),
                        'width': norm_rect.width(),
                        'height': norm_rect.height()
                    },
                    'class': class_data
                })
            
            elif isinstance(annotation, SelectablePolygonItem):
                # Для полигонов сохраняем нормализованные точки и класс
                points = []
                for i in range(annotation.polygon().count()):
                    points.append(annotation.polygon().at(i))
                
                norm_points = self.normalize_polygon_points(points)
                norm_points_data = []
                
                for point in norm_points:
                    norm_points_data.append({'x': point.x(), 'y': point.y()})
                
                class_data = {
                    'id': annotation.class_id,
                    'name': annotation.class_name,
                    'color': annotation.class_color.name() if annotation.class_color else None
                }
                
                normalized_annotations.append({
                    'type': 'polygon',
                    'points': norm_points_data,
                    'class': class_data
                })
        
        # Сохраняем нормализованные аннотации для текущего изображения
        self.annotations_by_image[self.current_image_path] = normalized_annotations
    
    def load_annotations_for_image(self, image_path):
        """
        Загружает и отображает аннотации для указанного изображения
        """
        # Очищаем текущие аннотации
        for annotation in self.annotations:
            self.scene.removeItem(annotation)
        self.annotations.clear()
        
        # Если нет сохраненных аннотаций для этого изображения, выходим
        if image_path not in self.annotations_by_image:
            return
            
        normalized_annotations = self.annotations_by_image[image_path]
        
        # Восстанавливаем аннотации из нормализованных данных
        for annotation_data in normalized_annotations:
            if annotation_data['type'] == 'rect':
                # Восстанавливаем прямоугольник
                coords = annotation_data['coords']
                norm_rect = QRectF(coords['x'], coords['y'], coords['width'], coords['height'])
                rect = self.denormalize_rect_coords(norm_rect)
                
                # Создаем прямоугольник
                rect_item = SelectableRectItem(rect.x(), rect.y(), rect.width(), rect.height(), None, self)
                rect_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                rect_item.setFlag(QGraphicsItem.ItemIsMovable, False)
                
                # Устанавливаем класс, если он есть
                if 'class' in annotation_data and annotation_data['class']:
                    rect_item.set_class(annotation_data['class'])
                
                self.scene.addItem(rect_item)
                self.annotations.append(rect_item)
                
            elif annotation_data['type'] == 'polygon':
                # Восстанавливаем полигон
                norm_points_data = annotation_data['points']
                norm_points = []
                
                for point_data in norm_points_data:
                    norm_points.append(QPointF(point_data['x'], point_data['y']))
                
                points = self.denormalize_polygon_points(norm_points)
                
                # Создаем полигон
                polygon_item = SelectablePolygonItem(points, None, self)
                polygon_item.scene_obj = self.scene
                polygon_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                polygon_item.setFlag(QGraphicsItem.ItemIsMovable, False)
                
                # Устанавливаем класс, если он есть
                if 'class' in annotation_data and annotation_data['class']:
                    polygon_item.set_class(annotation_data['class'])
                
                self.scene.addItem(polygon_item)
                self.annotations.append(polygon_item)

    def export_annotations_to_json(self, output_file):
        """
        Экспортирует все аннотации в JSON-файл
        """
        # Сохраняем текущие аннотации перед экспортом
        if self.current_image_path and self.annotations:
            self.save_current_annotations()
            
        import json
        import os
        
        # Создаем словарь для JSON-файла
        data = {
            'version': '1.0',
            'images': {}
        }
        
        # Преобразуем пути к относительным, если возможно
        base_dir = os.path.dirname(output_file)
        
        for img_path, annotations in self.annotations_by_image.items():
            # Пытаемся создать относительный путь
            try:
                rel_path = os.path.relpath(img_path, base_dir)
            except:
                rel_path = img_path
                
            data['images'][rel_path] = annotations
        
        # Записываем в JSON-файл с отступами для читаемости
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"Экспортированы аннотации для {len(self.annotations_by_image)} изображений в {output_file}")
        return True
    
    def import_annotations_from_json(self, input_file):
        """
        Импортирует аннотации из JSON-файла
        """
        import json
        import os
        
        # Очищаем текущие сохраненные аннотации
        self.annotations_by_image.clear()
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Проверяем версию формата
            if 'version' not in data or data['version'] != '1.0':
                print(f"Предупреждение: неизвестная версия формата аннотаций: {data.get('version', 'неизвестна')}")
                
            # Если есть данные для изображений
            if 'images' in data and isinstance(data['images'], dict):
                base_dir = os.path.dirname(input_file)
                
                # Загружаем аннотации для каждого изображения
                for rel_path, annotations in data['images'].items():
                    # Преобразуем относительный путь в абсолютный
                    if not os.path.isabs(rel_path):
                        abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
                    else:
                        abs_path = rel_path
                        
                    # Сохраняем аннотации для этого изображения
                    self.annotations_by_image[abs_path] = annotations
                    
                print(f"Импортированы аннотации для {len(self.annotations_by_image)} изображений из {input_file}")
                
                # Если текущее изображение есть среди импортированных, загружаем его аннотации
                if self.current_image_path in self.annotations_by_image:
                    self.load_annotations_for_image(self.current_image_path)
                    
                return True
        except Exception as e:
            print(f"Ошибка при импорте аннотаций: {str(e)}")
            
        return False


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    viewer = ImageViewerWidget()
    viewer.setWindowTitle("Просмотр и обработка изображений")
    viewer.resize(1000, 700)
    viewer.load_image("/Users/mac/Pictures/IMG_5257.jpeg")
    viewer.show()
    sys.exit(app.exec_())
