import cv2
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSlider, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPinchGesture,
    QToolBar, QAction, QSizePolicy, QGraphicsRectItem
)
from PyQt5.QtGui import (
    QPixmap, QImage, QWheelEvent, QPainter, QCursor, 
    QIcon, QPen, QKeyEvent, QColor
)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF, QSize, QSizeF
import numpy as np

from gui.utils import convert_qimage_to_np, convert_np_to_qimage


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
    
    def __init__(self, x, y, w, h, parent=None):
        super().__init__(x, y, w, h, parent)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)
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
        
    def paint(self, painter, option, widget):
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
    
    def handle_at_position(self, pos):
        """Определяет, находится ли позиция над одним из маркеров изменения размера"""
        rect = self.rect()
        handle_size = self.resize_handle_size
        
        # Проверяем каждый маркер
        handle_rects = [
            # Верхний левый угол
            QRectF(rect.left() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size),
            # Центр верхней стороны
            QRectF(rect.center().x() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size),
            # Верхний правый угол
            QRectF(rect.right() - handle_size/2, rect.top() - handle_size/2, handle_size, handle_size),
            # Центр левой стороны
            QRectF(rect.left() - handle_size/2, rect.center().y() - handle_size/2, handle_size, handle_size),
            # Центр правой стороны
            QRectF(rect.right() - handle_size/2, rect.center().y() - handle_size/2, handle_size, handle_size),
            # Нижний левый угол
            QRectF(rect.left() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size),
            # Центр нижней стороны
            QRectF(rect.center().x() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size),
            # Нижний правый угол
            QRectF(rect.right() - handle_size/2, rect.bottom() - handle_size/2, handle_size, handle_size)
        ]
        
        for i, handle_rect in enumerate(handle_rects):
            if handle_rect.contains(pos):
                return i
        
        return None
    
    def mousePressEvent(self, event):
        """Обработка нажатия кнопки мыши на прямоугольнике"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            # Проверяем, нажат ли один из маркеров изменения размера
            handle = self.handle_at_position(pos)
            if handle is not None and self.isSelected():
                self.current_resize_handle = handle
                self.mouse_press_pos = pos
                self.mouse_press_rect = self.rect()
                event.accept()
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши при нажатой кнопке"""
        if self.current_resize_handle is not None:
            # Изменяем размер прямоугольника в зависимости от выбранного маркера
            pos = event.pos()
            rect = QRectF(self.mouse_press_rect)
            
            dx = pos.x() - self.mouse_press_pos.x()
            dy = pos.y() - self.mouse_press_pos.y()
            
            # Обрабатываем изменение размера в зависимости от маркера
            if self.current_resize_handle == self.HANDLE_TOP_LEFT:
                rect.setTopLeft(rect.topLeft() + QPointF(dx, dy))
            elif self.current_resize_handle == self.HANDLE_TOP_MIDDLE:
                rect.setTop(rect.top() + dy)
            elif self.current_resize_handle == self.HANDLE_TOP_RIGHT:
                rect.setTopRight(rect.topRight() + QPointF(dx, dy))
            elif self.current_resize_handle == self.HANDLE_MIDDLE_LEFT:
                rect.setLeft(rect.left() + dx)
            elif self.current_resize_handle == self.HANDLE_MIDDLE_RIGHT:
                rect.setRight(rect.right() + dx)
            elif self.current_resize_handle == self.HANDLE_BOTTOM_LEFT:
                rect.setBottomLeft(rect.bottomLeft() + QPointF(dx, dy))
            elif self.current_resize_handle == self.HANDLE_BOTTOM_MIDDLE:
                rect.setBottom(rect.bottom() + dy)
            elif self.current_resize_handle == self.HANDLE_BOTTOM_RIGHT:
                rect.setBottomRight(rect.bottomRight() + QPointF(dx, dy))
            
            # Проверяем, что прямоугольник не стал "вывернутым наизнанку"
            if rect.width() >= 5 and rect.height() >= 5:
                self.setRect(rect)
                self.update()
            
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None  # Исходное QImage (RGB)
        self.current_adjusted_image = None
        self.original_np = None  # NumPy-массив исходного изображения в формате RGB (float32)
        self.zoom_factor = 1.0
        self.annotations = []  # Здесь будем хранить данные о созданных фигурах
        
        # Переменные для режима выделения прямоугольника
        self.current_mode = self.MODE_VIEW
        self.start_point = None
        self.current_rect = None
        self.selected_item = None
        
        self._init_ui()
        self._init_adjustments()

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
        
        self.action_edit = QAction("Править", self)
        self.action_edit.setCheckable(True)
        self.action_edit.triggered.connect(lambda: self.set_tool_mode(self.MODE_EDIT))
        
        # Добавляем действия на панель инструментов
        self.toolbar.addAction(self.action_rect_select)
        self.toolbar.addAction(self.action_edit)
        
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
        
        self.annotations.clear()
        self.zoom_factor = 1.0
        self.view.resetTransform()

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
        self.action_edit.setChecked(False)
        
        # Устанавливаем соответствующий курсор и режим перетаскивания
        if mode == self.MODE_VIEW:
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
            self.view.viewport().setCursor(Qt.OpenHandCursor)
            self.scene.setShowCrosshair(False)
            # Отключаем интерактивность для всех прямоугольников
            for item in self.annotations:
                if isinstance(item, SelectableRectItem):
                    item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
                    item.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        elif mode == self.MODE_RECT_SELECT:
            self.action_rect_select.setChecked(True)
            self.view.setDragMode(QGraphicsView.NoDrag)
            # Устанавливаем курсор-перекрестие
            self.view.viewport().setCursor(Qt.CrossCursor)
            self.scene.setShowCrosshair(True)
            # Отключаем интерактивность для всех прямоугольников
            for item in self.annotations:
                if isinstance(item, SelectableRectItem):
                    item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
                    item.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        elif mode == self.MODE_EDIT:
            self.action_edit.setChecked(True)
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.view.viewport().setCursor(Qt.ArrowCursor)
            self.scene.setShowCrosshair(False)
            # Включаем интерактивность для всех прямоугольников
            for item in self.annotations:
                if isinstance(item, SelectableRectItem):
                    item.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
                    item.setFlag(QGraphicsRectItem.ItemIsMovable, True)
            
        # Сбрасываем текущее выделение
        if self.current_rect:
            self.scene.removeItem(self.current_rect)
            self.current_rect = None
        self.start_point = None
        
    def eventFilter(self, obj, event):
        """Фильтр событий для обработки событий мыши в viewport"""
        if obj == self.view.viewport():
            # Обновляем позицию перекрестия при движении мыши
            if event.type() == event.MouseMove and self.pixmap_item:
                scene_pos = self.view.mapToScene(event.pos())
                self.scene.setCrosshairPos(scene_pos)
            
            # В режиме редактирования позволяем событиям проходить к элементам сцены
            if self.current_mode == self.MODE_EDIT:
                # Проверяем, что это событие мыши, прежде чем вызывать pos()
                if event.type() in [event.MouseButtonPress, event.MouseButtonRelease, event.MouseMove]:
                    scene_pos = self.view.mapToScene(event.pos())
                    items = self.scene.items(scene_pos)
                    
                    # Проверяем, есть ли под курсором выделяемый прямоугольник
                    for item in items:
                        if isinstance(item, SelectableRectItem):
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
        # Обрабатываем только в режиме выделения прямоугольника
        if self.current_mode == self.MODE_RECT_SELECT:
            # Получаем координаты в сцене
            scene_pos = self.view.mapToScene(event.pos())
            
            # Проверяем, что точка находится в пределах изображения
            if self.pixmap_item and self.pixmap_item.contains(scene_pos):
                self.start_point = scene_pos
                
                # Создаем новый прямоугольник
                self.current_rect = QGraphicsRectItem(QRectF(scene_pos, QSizeF(0, 0)))
                self.current_rect.setPen(QPen(QColor(255, 0, 0), 2, Qt.DashLine))
                self.current_rect.setBrush(QColor(255, 0, 0, 50))
                self.scene.addItem(self.current_rect)
                
                return True
        
        return False
        
    def handle_mouse_move(self, event):
        """Обработка движения мыши"""
        # Обрабатываем только в режиме выделения прямоугольника
        if self.current_mode == self.MODE_RECT_SELECT and self.start_point and self.current_rect:
            # Получаем текущие координаты в сцене
            current_pos = self.view.mapToScene(event.pos())
            
            # Ограничиваем координаты границами изображения
            if self.pixmap_item:
                pixmap_rect = self.pixmap_item.boundingRect()
                current_pos.setX(max(pixmap_rect.left(), min(current_pos.x(), pixmap_rect.right())))
                current_pos.setY(max(pixmap_rect.top(), min(current_pos.y(), pixmap_rect.bottom())))
            
            # Обновляем прямоугольник
            rect = QRectF(
                min(self.start_point.x(), current_pos.x()),
                min(self.start_point.y(), current_pos.y()),
                abs(current_pos.x() - self.start_point.x()),
                abs(current_pos.y() - self.start_point.y())
            )
            self.current_rect.setRect(rect)
            
            return True
            
        return False
        
    def handle_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        if self.current_mode == self.MODE_RECT_SELECT and self.start_point and self.current_rect:
            # Получаем конечные координаты в сцене
            end_point = self.view.mapToScene(event.pos())
            
            # Ограничиваем координаты границами изображения
            if self.pixmap_item:
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
                rect_item = SelectableRectItem(rect.x(), rect.y(), rect.width(), rect.height())
                # В режиме выделения прямоугольники не должны быть интерактивными
                rect_item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
                rect_item.setFlag(QGraphicsRectItem.ItemIsMovable, False)
                self.scene.addItem(rect_item)
                self.annotations.append(rect_item)
            
            self.current_rect = None
            self.start_point = None
            
            return True
            
        return False
        
    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатий клавиш"""
        # Удаление выбранных прямоугольников при нажатии Delete или Backspace
        if self.current_mode == self.MODE_EDIT and (event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace):
            for item in self.scene.selectedItems():
                if isinstance(item, SelectableRectItem):
                    self.scene.removeItem(item)
                    if item in self.annotations:
                        self.annotations.remove(item)
            return
            
        super().keyPressEvent(event)


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
