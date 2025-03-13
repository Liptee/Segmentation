from PyQt5.QtGui import QColor, QPen, QPolygonF
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsItem, QGraphicsPixmapItem
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtCore import pyqtSignal, QObject

from logger import logger


class ClassAnnotatableMixin:
    """
    Mixin для установки класса сегментации и обновления внешнего вида.
    (Mixin for setting segmentation class and updating appearance.)
    """

    def get_default_color(self) -> QColor:
        """Возвращает цвет по умолчанию.
        (Returns the default color.)"""
        return QColor(255, 0, 0)  # Красный по умолчанию

    def get_default_color_str(self) -> str:
        """Возвращает строковое представление цвета по умолчанию.
        (Returns the default color as a string.)"""
        return "#FF0000"

    def get_default_alpha(self) -> int:
        """Возвращает уровень прозрачности для заливки.
        (Returns the fill opacity.)"""
        return 50

    def set_class(self, class_data):
        """
        Устанавливает класс сегментации для объекта и обновляет внешний вид.
        (Sets the segmentation class for the object and updates its appearance.)
        """
        if class_data is None:
            self.class_id = None
            self.class_name = None
            self.class_color = self.get_default_color()
            logger.info(f"AnnotationTool: Устанавливаю None класс для {self.__class__.__name__}")
        else:
            self.class_id = class_data.get('id')
            self.class_name = class_data.get('name')
            color_str = class_data.get('color', self.get_default_color_str())
            logger.info(f"AnnotationTool: Устанавливаю класс для {self.__class__.__name__}: {self.class_name}, ID={self.class_id}, цвет={color_str}")
            self.class_color = QColor(color_str)
            if not self.class_color.isValid():
                logger.info(f"AnnotationTool: Ошибка: Невалидный цвет {color_str}, использую {self.get_default_color_str()}")
                self.class_color = self.get_default_color()

        self.update_appearance()

    def update_appearance(self):
        """
        Обновляет внешний вид объекта согласно выбранному классу.
        (Updates the object's appearance based on the chosen class.)
        """
        if self.class_color:
            fill_color = QColor(self.class_color)
            fill_color.setAlpha(self.get_default_alpha())
            self.setPen(QPen(self.class_color, 2, Qt.SolidLine))
            self.setBrush(fill_color)
            logger.info(f"AnnotationTool: Обновляю внешний вид {self.__class__.__name__}: ID класса={self.class_id}, цвет={self.class_color.name()}")
        else:
            default = self.get_default_color()
            self.setPen(QPen(default, 2, Qt.SolidLine))
            fill_color = QColor(default)
            fill_color.setAlpha(self.get_default_alpha())
            self.setBrush(fill_color)
            logger.info(f"AnnotationTool: Устанавливаю стандартный цвет {default.name()} для {self.__class__.__name__}")


class ImageRectMixin:
    """Миксин для получения прямоугольника изображения"""
    def get_image_rect(self):
        # Проверяем, есть ли у нас прямой доступ к pixmap_item через self.scene
        if hasattr(self, 'scene'):
            # Если self.scene - это ImageViewerWidget
            if hasattr(self.scene, 'pixmap_item') and self.scene.pixmap_item:
                return self.scene.pixmap_item.boundingRect()
            
            # Если self.scene - это QGraphicsScene
            if hasattr(self.scene, 'parent') and self.scene.parent and hasattr(self.scene.parent, 'pixmap_item'):
                return self.scene.parent.pixmap_item.boundingRect()
        
        # Пытаемся получить сцену через QGraphicsItem.scene()
        try:
            scene = super().scene()  # Используем метод scene() из QGraphicsItem
            if scene:
                # Проверяем, есть ли у сцены родитель с pixmap_item
                if hasattr(scene, 'parent') and scene.parent and hasattr(scene.parent, 'pixmap_item'):
                    return scene.parent.pixmap_item.boundingRect()
                
                # Проверяем, есть ли у сцены pixmap_item напрямую
                for item in scene.items():
                    if isinstance(item, QGraphicsPixmapItem):
                        return item.boundingRect()
        except Exception as e:
            logger.warning(f"Ошибка при получении сцены: {e}")
        
        # Если ничего не нашли, возвращаем None
        return None


class SelectableRectItem(ClassAnnotatableMixin, ImageRectMixin, QGraphicsRectItem):
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
        if change == QGraphicsItem.ItemPositionChange:
            try:
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
            except Exception as e:
                logger.warning(f"Ошибка при ограничении позиции прямоугольника: {e}")
                return value
        
        # Когда позиция прямоугольника изменилась, уведомляем об этом
        elif change == QGraphicsItem.ItemPositionHasChanged:
            try:
                # Уведомляем об изменении положения прямоугольника
                logger.info(f"SelectableRectItem: Позиция изменилась на {self.pos()}")
                if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
                    logger.info(f"SelectableRectItem: Вызываем on_annotation_changed")
                    self.scene.on_annotation_changed()
                else:
                    logger.warning(f"SelectableRectItem: Не удалось вызвать on_annotation_changed: scene={hasattr(self, 'scene')}, has_method={hasattr(self.scene, 'on_annotation_changed') if hasattr(self, 'scene') else False}")
            except Exception as e:
                logger.warning(f"Ошибка при обработке изменения позиции прямоугольника: {e}")
        
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
            # Вместо сигнала используем метод scene для уведомления об изменениях
            if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
                logger.info(f"SelectableRectItem.mouseReleaseEvent: Вызываем on_annotation_changed")
                self.scene.on_annotation_changed()
            event.accept()
            return
        
        # Если перемещали весь прямоугольник, тоже уведомляем об изменениях
        if event.button() == Qt.LeftButton and self.isSelected():
            # Вместо сигнала используем метод scene для уведомления об изменениях
            if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
                logger.info(f"SelectableRectItem.mouseReleaseEvent: Вызываем on_annotation_changed после перемещения")
                self.scene.on_annotation_changed()
        
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


class SelectablePolygonItem(ClassAnnotatableMixin, ImageRectMixin, QGraphicsPolygonItem):
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
        self.scene_obj = None  # Ссылка на объект QGraphicsScene
        self.hover_edge_index = None  # Индекс ребра, над которым находится курсор
        
        # Свойства для класса сегментации
        self.class_id = None
        self.class_name = None
        self.class_color = None
        
        # Установка обработки наведения мыши
        self.setAcceptHoverEvents(True)
    
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
            try:
                self.update()
                # Уведомляем об изменении положения полигона
                logger.info(f"SelectablePolygonItem: Позиция изменилась на {self.pos()}")
                if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
                    logger.info(f"SelectablePolygonItem: Вызываем on_annotation_changed")
                    self.scene.on_annotation_changed()
                else:
                    logger.warning(f"SelectablePolygonItem: Не удалось вызвать on_annotation_changed: scene={hasattr(self, 'scene')}, has_method={hasattr(self.scene, 'on_annotation_changed') if hasattr(self, 'scene') else False}")
            except Exception as e:
                logger.warning(f"Ошибка при обработке изменения позиции полигона: {e}")
        
        # Когда меняется позиция полигона, проверяем, не выходит ли он за границы изображения
        elif change == QGraphicsItem.ItemPositionChange:
            try:
                new_pos = value
                image_rect = self.get_image_rect()
                
                if image_rect:
                    # Получаем границы полигона
                    polygon_rect = self.boundingRect()
                    
                    # Проверяем, не выходит ли полигон за границы изображения
                    # Ограничиваем перемещение по X
                    if new_pos.x() + polygon_rect.left() < image_rect.left():
                        new_pos.setX(image_rect.left() - polygon_rect.left())
                    elif new_pos.x() + polygon_rect.right() > image_rect.right():
                        new_pos.setX(image_rect.right() - polygon_rect.right())
                    
                    # Ограничиваем перемещение по Y
                    if new_pos.y() + polygon_rect.top() < image_rect.top():
                        new_pos.setY(image_rect.top() - polygon_rect.top())
                    elif new_pos.y() + polygon_rect.bottom() > image_rect.bottom():
                        new_pos.setY(image_rect.bottom() - polygon_rect.bottom())
                    
                    return new_pos
            except Exception as e:
                logger.warning(f"Ошибка при ограничении позиции полигона: {e}")
                return value
        
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
            
            # Если курсор находится над ребром, отрисовываем точку возможного добавления
            if self.hover_edge_index is not None:
                painter.setPen(QPen(QColor(255, 165, 0), 1))  # Оранжевый цвет
                painter.setBrush(QColor(255, 165, 0, 200))
                
                # Получаем координаты середины ребра
                i1 = self.hover_edge_index
                i2 = (i1 + 1) % polygon.count()
                p1 = polygon.at(i1)
                p2 = polygon.at(i2)
                mid_point = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                
                # Рисуем маркер в середине ребра
                handle_rect = QRectF(
                    mid_point.x() - self.handle_size/2,
                    mid_point.y() - self.handle_size/2,
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
    
    def edge_at_position(self, pos):
        """Определяет, находится ли указанная позиция над одним из ребер полигона
        
        Args:
            pos: Позиция проверки (QPointF)
            
        Returns:
            int: Индекс начальной точки ребра или None, если ребро не найдено
        """
        polygon = self.polygon()
        if polygon.count() < 2:
            return None
            
        # Проверяем каждое ребро полигона
        for i in range(polygon.count()):
            p1 = polygon.at(i)
            p2 = polygon.at((i + 1) % polygon.count())
            
            # Вычисляем середину ребра
            mid_point = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
            
            # Проверяем, находится ли курсор рядом с серединой ребра
            handle_rect = QRectF(
                mid_point.x() - self.handle_size/2,
                mid_point.y() - self.handle_size/2,
                self.handle_size,
                self.handle_size
            )
            
            if handle_rect.contains(pos):
                return i
                
        return None
    
    def add_point_at_edge(self, edge_index):
        """Добавляет новую точку в середину указанного ребра
        
        Args:
            edge_index: Индекс начальной точки ребра
        """
        polygon = self.polygon()
        if polygon.count() < 2 or edge_index is None:
            return
            
        # Получаем координаты точек ребра
        i1 = edge_index
        i2 = (edge_index + 1) % polygon.count()
        p1 = polygon.at(i1)
        p2 = polygon.at(i2)
        
        # Вычисляем середину ребра
        mid_point = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
        
        # Создаем новый полигон с добавленной точкой
        new_polygon = QPolygonF()
        for i in range(polygon.count()):
            new_polygon.append(polygon.at(i))
            if i == edge_index:
                # Вставляем новую точку после текущей
                new_polygon.append(mid_point)
        
        # Обновляем полигон
        self.setPolygon(new_polygon)
        
        # Уведомляем об изменении
        if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
            self.scene.on_annotation_changed()
    
    def remove_point(self, point_index):
        """Удаляет точку из полигона
        
        Args:
            point_index: Индекс точки для удаления
        """
        polygon = self.polygon()
        if polygon.count() <= 3 or point_index is None:
            # Не удаляем точку, если полигон станет слишком маленьким
            return
            
        # Создаем новый полигон без указанной точки
        new_polygon = QPolygonF()
        for i in range(polygon.count()):
            if i != point_index:
                new_polygon.append(polygon.at(i))
        
        # Обновляем полигон
        self.setPolygon(new_polygon)
        
        # Уведомляем об изменении
        if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
            self.scene.on_annotation_changed()
    
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
                
            # Проверяем, нажата ли середина ребра для добавления новой точки
            edge_index = self.edge_at_position(pos)
            if edge_index is not None and self.isSelected():
                self.add_point_at_edge(edge_index)
                event.accept()
                return
        elif event.button() == Qt.RightButton:
            pos = event.pos()
            # Проверяем, нажата ли одна из точек полигона для удаления
            point_index = self.point_at_position(pos)
            if point_index is not None and self.isSelected():
                self.remove_point(point_index)
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
            # Вместо сигнала используем метод scene для уведомления об изменениях
            if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
                logger.info(f"SelectablePolygonItem.mouseReleaseEvent: Вызываем on_annotation_changed")
                self.scene.on_annotation_changed()
        
        # Если перемещали весь полигон, тоже уведомляем об изменениях
        if event.button() == Qt.LeftButton and self.isSelected():
            # Вместо сигнала используем метод scene для уведомления об изменениях
            if hasattr(self, 'scene') and self.scene and hasattr(self.scene, 'on_annotation_changed'):
                logger.info(f"SelectablePolygonItem.mouseReleaseEvent: Вызываем on_annotation_changed после перемещения")
                self.scene.on_annotation_changed()
        
        super().mouseReleaseEvent(event)
        
    def hoverMoveEvent(self, event):
        """Обработка перемещения мыши над полигоном"""
        if self.isSelected():
            pos = event.pos()
            
            # Проверяем, находится ли курсор над точкой полигона
            point_index = self.point_at_position(pos)
            if point_index is not None:
                self.setCursor(Qt.PointingHandCursor)
                self.hover_edge_index = None
                self.update()  # Перерисовываем для обновления отображения
                return
                
            # Проверяем, находится ли курсор над ребром полигона
            edge_index = self.edge_at_position(pos)
            if edge_index is not None:
                self.setCursor(Qt.CrossCursor)  # Курсор для добавления точки
                self.hover_edge_index = edge_index
                self.update()  # Перерисовываем для обновления отображения
                return
                
            # Если курсор не над точкой и не над ребром
            self.setCursor(Qt.ArrowCursor)
            self.hover_edge_index = None
            self.update()  # Перерисовываем для обновления отображения
        else:
            self.setCursor(Qt.ArrowCursor)
            self.hover_edge_index = None
        
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Обработка выхода мыши за пределы полигона"""
        self.setCursor(Qt.ArrowCursor)
        self.hover_edge_index = None
        self.update()  # Перерисовываем для обновления отображения
        super().hoverLeaveEvent(event)
