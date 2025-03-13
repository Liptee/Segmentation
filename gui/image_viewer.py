import json
import os
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
from gui.geometry_utils import GeometryUtils
from core.annotation_manager import AnnotationManager
from gui.annotation_items import SelectableRectItem, SelectablePolygonItem
from logger import logger



"""
Данная константа MAX_PIXELS определяет максимальное количество пикселей в изображении,
которое будет отображаться в окне просмотра.
Если изображение превышает это значение, оно будет масштабировано.
Данное решение необходимо, чтобы не загружать в память большие изображения,
которые также сильно нагружают систему при изменениях параметров яркости:
"""
MAX_PIXELS = 2000000 # 2 мегапикселя


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

class CrosshairGraphicsScene(QGraphicsScene):
    """Сцена с отображением перекрестия при выборе инструмента выделения"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_crosshair = False
        self.crosshair_pos = QPointF(0, 0)
        self.image_rect = QRectF()
        self.parent = parent
        
    def setShowCrosshair(self, show):
        self.show_crosshair = show
        self.update()
        
    def setCrosshairPos(self, pos):
        self.crosshair_pos = pos
        self.update()
        
    def setImageRect(self, rect):
        self.image_rect = rect
        
    def on_annotation_changed(self):
        """Обработчик изменения аннотаций"""
        # Перенаправляем вызов к родительскому виджету
        if self.parent and hasattr(self.parent, 'on_annotation_changed'):
            self.parent.on_annotation_changed()
        
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
        self.annotation_manager = AnnotationManager()
        
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
        if self.current_image_path and self.annotations:
            logger.info(f"ImageViewer: Сохраняю {len(self.annotations)} аннотаций для {self.current_image_path}")
            self.save_current_annotations()
            
        qimg = QImage(file_path).convertToFormat(QImage.Format_RGB888)
        logger.info(f"ImageViewer: Размер изображения оригинального QImage: {qimg.size()}")
        if qimg.isNull():
            return False
        
        w = qimg.width()
        h = qimg.height()
        self.image = qimg
        self.original_np = convert_qimage_to_np(self.image)
        logger.info(f"ImageViewer: Размер изображения оригинального NumPy-массива: {self.original_np.shape}")
        # Если изображение слишком большое, уменьшаем его
        if w * h > MAX_PIXELS:
            scale = np.sqrt(MAX_PIXELS / (w * h))
            new_w = int(w * scale)
            new_h = int(h * scale)
            logger.info(f"ImageViewer: Уменьшаю изображение до {new_w}x{new_h}")
            self.original_np = cv2.resize(self.original_np, (new_w, new_h), interpolation=cv2.INTER_AREA)
            self.image = convert_np_to_qimage(self.original_np)

        self.current_adjusted_image = convert_np_to_qimage(self.original_np)
        self.scene.clear()

        self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(self.current_adjusted_image))
        self.scene.addItem(self.pixmap_item)
        self.update_image_adjustments()

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

        logger.info(f"ImageViewer: Загружено изображение: {file_path}, восстановлено аннотаций: {len(self.annotations)}")
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
                    # Устанавливаем ссылку на сцену для каждого элемента
                    item.scene = self
                    # Устанавливаем флаг для обработки изменений геометрии
                    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
            
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
                # Устанавливаем флаг для обработки изменений геометрии
                rect_item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
                # В режиме выделения прямоугольники не должны быть интерактивными
                rect_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                rect_item.setFlag(QGraphicsItem.ItemIsMovable, False)
                self.scene.addItem(rect_item)
                self.annotations.append(rect_item)
                
                # Показываем диалог выбора класса для нового прямоугольника
                if self.class_manager:
                    self.show_object_labeler(rect_item)
                    
                # Сохраняем аннотации после создания прямоугольника
                self.save_current_annotations()
            
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
        
        # Устанавливаем флаг для обработки изменений геометрии
        polygon_item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
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
        
        # Сохраняем аннотации после создания полигона
        self.save_current_annotations()
        
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
            # Сохраняем изменения после удаления аннотаций
            self.save_current_annotations()
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
                
            # Сохраняем изменения после назначения класса
            self.save_current_annotations()
            logger.info(f"ImageViewer: Класс назначен и аннотации сохранены для {self.current_image_path}")
    
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
            logger.info("ImageViewer: Не могу показать диалог назначения класса: нет менеджера классов или объекта")
            return
            
        logger.info(f"ImageViewer: Показываю диалог назначения класса для объекта типа {type(annotation_object).__name__}")
            
        # Создаем ObjectLabelerWidget, если его еще нет
        if not self.object_labeler:
            self.object_labeler = ObjectLabelerWidget(self, self.class_manager)
            self.object_labeler.classAssigned.connect(self.on_class_assigned)
            self.object_labeler.newClassRequested.connect(self.request_new_class)
        
        # Устанавливаем текущий объект и показываем диалог
        self.object_labeler.set_current_object(annotation_object)
        result = self.object_labeler.exec_()
        
        logger.info(f"ImageViewer: Диалог закрылся с результатом: {result} (1=принят, 0=отклонен)")

    def normalize_rect_coords(self, rect):
        if not self.pixmap_item:
            return rect
            
        img_rect = self.pixmap_item.boundingRect()
        return GeometryUtils.normalize_rect(rect, img_rect)
    
    def denormalize_rect_coords(self, norm_rect):
        if not self.pixmap_item:
            return norm_rect
            
        img_rect = self.pixmap_item.boundingRect()
        return GeometryUtils.denormalize_rect(norm_rect, img_rect)
    
    def normalize_polygon_points(self, points):
        if not self.pixmap_item or not points:
            return points
            
        img_rect = self.pixmap_item.boundingRect()
        return GeometryUtils.normalize_points(points, img_rect)
    
    def denormalize_polygon_points(self, norm_points):
        if not self.pixmap_item or not norm_points:
            return norm_points
            
        img_rect = self.pixmap_item.boundingRect()
        return GeometryUtils.denormalize_points(norm_points, img_rect)
    
    def save_current_annotations(self):
        """
        Сохраняет текущие аннотации для текущего изображения
        """
        if not self.current_image_path:
            logger.warning("ImageViewer.save_current_annotations: Нет текущего пути к изображению")
            return
        
        logger.info(f"ImageViewer.save_current_annotations: Сохраняю {len(self.annotations)} аннотаций для {self.current_image_path}")
        
        # Выводим информацию о каждой аннотации перед сохранением
        for i, annotation in enumerate(self.annotations):
            if isinstance(annotation, SelectableRectItem):
                logger.info(f"  Сохраняю аннотацию {i}: Прямоугольник, позиция: {annotation.pos()}, размер: {annotation.rect().size()}")
            elif isinstance(annotation, SelectablePolygonItem):
                logger.info(f"  Сохраняю аннотацию {i}: Полигон, позиция: {annotation.pos()}, точек: {annotation.polygon().count()}")
        
        self.annotation_manager.save_annotations(
            self.current_image_path, 
            self.annotations, 
            self.normalize_rect_coords, 
            self.normalize_polygon_points)
        
        logger.info(f"ImageViewer.save_current_annotations: Аннотации сохранены")

    def load_annotations_for_image(self, image_path):
        """
        Загружает и отображает аннотации для указанного изображения
        """
        logger.info(f"ImageViewer.load_annotations_for_image: Загружаю аннотации для {image_path}")
        
        # Очищаем текущие аннотации
        for annotation in self.annotations:
            self.scene.removeItem(annotation)
        self.annotations.clear()
        
        # Если нет сохраненных аннотаций для этого изображения, выходим
        if image_path not in self.annotation_manager.annotations_by_image:
            logger.info(f"ImageViewer.load_annotations_for_image: Нет сохраненных аннотаций для {image_path}")
            return
            
        loaded_items = self.annotation_manager.load_annotations(
            image_path, 
            self.denormalize_rect_coords, 
            self.denormalize_polygon_points)
        
        logger.info(f"ImageViewer.load_annotations_for_image: Загружено {len(loaded_items)} аннотаций")
        
        for i, item in enumerate(loaded_items):
            if isinstance(item, SelectableRectItem):
                logger.info(f"  Загружена аннотация {i}: Прямоугольник, позиция: {item.pos()}, размер: {item.rect().size()}")
            elif isinstance(item, SelectablePolygonItem):
                logger.info(f"  Загружена аннотация {i}: Полигон, позиция: {item.pos()}, точек: {item.polygon().count()}")
            
            # Устанавливаем ссылку на сцену для каждого элемента
            item.scene = self
            # Устанавливаем флаг для обработки изменений геометрии
            item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
            
            self.scene.addItem(item)
            self.annotations.append(item)

    def export_annotations_to_json(self, output_file):
        """
        Экспортирует все аннотации в JSON-файл
        """
        self.save_current_annotations()
        self.annotation_manager.export_to_json(output_file)
    
    def import_annotations_from_json(self, input_file):
        """
        Импортирует аннотации из JSON-файла
        """
        if self.annotation_manager.import_from_json(input_file):
            if self.current_image_path in self.annotation_manager.annotations_by_image:
                self.load_annotations_for_image(self.current_image_path)
            return True
        return False

    def on_annotation_changed(self):
        """Обработчик изменения аннотаций в режиме редактирования"""
        # Сохраняем текущие аннотации при их изменении
        logger.info(f"ImageViewer.on_annotation_changed: Сохраняю аннотации для {self.current_image_path}")
        logger.info(f"ImageViewer.on_annotation_changed: Количество аннотаций: {len(self.annotations)}")
        
        # Выводим информацию о каждой аннотации
        for i, annotation in enumerate(self.annotations):
            if isinstance(annotation, SelectableRectItem):
                logger.info(f"  Аннотация {i}: Прямоугольник, позиция: {annotation.pos()}, размер: {annotation.rect().size()}")
            elif isinstance(annotation, SelectablePolygonItem):
                logger.info(f"  Аннотация {i}: Полигон, позиция: {annotation.pos()}, точек: {annotation.polygon().count()}")
        
        self.save_current_annotations()
        logger.info(f"ImageViewer: Аннотации изменены и сохранены для {self.current_image_path}")

    def closeEvent(self, event):
        """Обработчик закрытия виджета"""
        # Сохраняем текущие аннотации перед закрытием
        if self.current_image_path and self.annotations:
            logger.info(f"ImageViewer: Сохраняю {len(self.annotations)} аннотаций перед закрытием для {self.current_image_path}")
            self.save_current_annotations()
        super().closeEvent(event)
