from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, 
    QLabel, QDialog, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from logger import logger


class ObjectLabelerWidget(QDialog):
    """
    Виджет для назначения классов сегментации объектам аннотации (прямоугольников и полигонов).
    Отображается как всплывающее окно при создании или выборе объекта в ImageViewerWidget.
    """
    classAssigned = pyqtSignal(object, object)  # (объект аннотации, выбранный класс)
    newClassRequested = pyqtSignal()  # Сигнал для запроса создания нового класса
    
    def __init__(self, parent=None, class_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Назначение класса")
        self.setMinimumWidth(300)
        
        # Сохраняем ссылку на менеджер классов
        self.class_manager = class_manager
        
        # Текущий объект аннотации (прямоугольник или полигон)
        self.current_object = None
        
        self.init_ui()
        
    def init_ui(self):
        # Основной макет
        main_layout = QVBoxLayout(self)
        
        # Заголовок
        title_label = QLabel("Выберите класс для объекта:")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Область с прокруткой для классов
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        scroll_content = QWidget()
        self.classes_layout = QVBoxLayout(scroll_content)
        self.classes_layout.setAlignment(Qt.AlignTop)
        self.classes_layout.setSpacing(5)
        
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # Выпадающий список для выбора класса
        class_layout = QHBoxLayout()
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(200)
        class_layout.addWidget(QLabel("Класс:"))
        class_layout.addWidget(self.class_combo)
        main_layout.addLayout(class_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.new_class_button = QPushButton("Создать новый класс")
        self.new_class_button.clicked.connect(self.request_new_class)
        
        self.apply_button = QPushButton("Применить")
        self.apply_button.clicked.connect(self.apply_class)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.new_class_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.apply_button)
        buttons_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Устанавливаем макет
        self.setLayout(main_layout)
    
    def set_current_object(self, annotation_object):
        """Устанавливает текущий объект аннотации и обновляет список классов"""
        self.current_object = annotation_object
        self.update_class_list()
    
    def update_class_list(self):
        """Обновляет выпадающий список классов из менеджера классов"""
        if not self.class_manager:
            return
            
        # Очищаем комбо-бокс
        self.class_combo.clear()
        
        # Добавляем пустой элемент (без класса)
        self.class_combo.addItem("Нет класса", None)
        
        # Получаем все классы из менеджера
        classes = self.class_manager.get_all_classes()
        
        # Добавляем классы в выпадающий список
        current_class_id = getattr(self.current_object, 'class_id', None)
        current_index = 0
        
        for i, cls in enumerate(classes):
            # Используем цвет класса как иконку или текстовый маркер
            color_str = cls.get('color', '#FFFFFF')
            name = cls.get('name', 'Неизвестный класс')
            
            # Добавляем класс в выпадающий список
            self.class_combo.addItem(name)
            
            # Создаем цвет для фона элемента списка
            bg_color = QColor(color_str)
            bg_color.setAlpha(100)  # Делаем полупрозрачным для лучшей видимости текста
            self.class_combo.setItemData(i + 1, bg_color, Qt.BackgroundRole)
            
            # Устанавливаем текст черным или белым в зависимости от яркости фона
            if bg_color.lightness() < 128:
                # Для темных фонов используем светлый текст
                self.class_combo.setItemData(i + 1, QColor(255, 255, 255), Qt.ForegroundRole)
            
            # Если это текущий класс объекта - запоминаем индекс
            if cls.get('id') == current_class_id:
                current_index = i + 1
        
        # Устанавливаем текущий выбранный класс
        self.class_combo.setCurrentIndex(current_index)
    
    def apply_class(self):
        """Применяет выбранный класс к объекту"""
        if not self.current_object:
            self.reject()
            return
            
        # Получаем выбранный класс
        index = self.class_combo.currentIndex()
        if index <= 0:  # "Нет класса"
            selected_class = None
        else:
            # Получаем выбранный класс из менеджера
            classes = self.class_manager.get_all_classes()
            if index - 1 < len(classes):
                selected_class = classes[index - 1]
                
                # Проверяем, что класс содержит все необходимые данные
                if not selected_class.get('id') or not selected_class.get('color'):
                    logger.info(f"ObjectLabeler: Предупреждение: класс не содержит id или color: {selected_class}")
                    
                # Добавим отладочную информацию
                logger.info(f"ObjectLabeler: Выбран класс: {selected_class.get('name')}, ID: {selected_class.get('id')}, Цвет: {selected_class.get('color')}")
            else:
                selected_class = None
                logger.info(f"ObjectLabeler: Ошибка: выбран индекс {index-1}, но всего классов {len(classes)}")
        
        # Излучаем сигнал с выбранным классом
        self.classAssigned.emit(self.current_object, selected_class)
        self.accept()
    
    def request_new_class(self):
        """Запрашивает создание нового класса через менеджер классов"""
        self.newClassRequested.emit()
        # После создания нового класса нужно обновить список
        self.update_class_list() 