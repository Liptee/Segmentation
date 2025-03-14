import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QGroupBox, QRadioButton, QSlider, QSpinBox, 
    QListWidget, QListWidgetItem, QFrame, QSplitter, QProgressDialog,
    QComboBox, QWidget, QCheckBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QIcon, QDragEnterEvent, QDropEvent

from logger import logger


class EffectWidget(QWidget):
    """
    Базовый класс для виджета эффекта с параметрами
    """
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.params = {}
        self.mode = "processing"  # "processing" или "augmentation"
        
        # Создание UI
        layout = QVBoxLayout(self)
        
        # Заголовок с именем эффекта
        title_layout = QHBoxLayout()
        self.title_label = QLabel(name)
        title_layout.addWidget(self.title_label)
        
        # Режим эффекта
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Обработка", "Аугментация"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        title_layout.addWidget(self.mode_combo)
        
        layout.addLayout(title_layout)
        
        # Контейнер для параметров эффекта
        self.params_container = QWidget()
        self.params_layout = QVBoxLayout(self.params_container)
        layout.addWidget(self.params_container)
        
        # Контейнер для вероятности (только для аугментации)
        self.probability_container = QWidget()
        self.probability_container.setVisible(False)
        prob_layout = QHBoxLayout(self.probability_container)
        prob_layout.addWidget(QLabel("Вероятность:"))
        self.probability_slider = QSlider(Qt.Horizontal)
        self.probability_slider.setRange(0, 100)
        self.probability_slider.setValue(50)
        self.probability_slider.setTickPosition(QSlider.TicksBelow)
        self.probability_slider.setTickInterval(10)
        prob_layout.addWidget(self.probability_slider)
        self.probability_label = QLabel("50%")
        prob_layout.addWidget(self.probability_label)
        self.probability_slider.valueChanged.connect(self.on_probability_changed)
        
        layout.addWidget(self.probability_container)
    
    def on_mode_changed(self, index):
        self.mode = "augmentation" if index == 1 else "processing"
        self.probability_container.setVisible(self.mode == "augmentation")
        self.params["mode"] = self.mode
    
    def on_probability_changed(self, value):
        self.probability_label.setText(f"{value}%")
        self.params["probability"] = value
    
    def get_effect_data(self):
        """
        Возвращает данные об эффекте для экспорта
        """
        return {
            "name": self.name,
            "mode": self.mode,
            "probability": self.params.get("probability", 50) if self.mode == "augmentation" else None,
            "params": self.params
        }


class FlipEffect(EffectWidget):
    """
    Эффект зеркального отражения изображения
    """
    def __init__(self, parent=None):
        super().__init__("Отражение", parent)
        
        # Добавляем параметры
        flip_layout = QHBoxLayout()
        
        self.horizontal_check = QCheckBox("Горизонтальное")
        self.horizontal_check.setChecked(True)
        self.horizontal_check.stateChanged.connect(self.update_params)
        
        self.vertical_check = QCheckBox("Вертикальное")
        self.vertical_check.stateChanged.connect(self.update_params)
        
        flip_layout.addWidget(self.horizontal_check)
        flip_layout.addWidget(self.vertical_check)
        
        self.params_layout.addLayout(flip_layout)
        
        # Инициализируем параметры
        self.params = {
            "horizontal": True,
            "vertical": False,
            "mode": self.mode
        }
    
    def update_params(self):
        self.params["horizontal"] = self.horizontal_check.isChecked()
        self.params["vertical"] = self.vertical_check.isChecked()


class RotationEffect(EffectWidget):
    """
    Эффект поворота изображения
    """
    def __init__(self, parent=None):
        super().__init__("Поворот", parent)
        
        # Добавляем параметры
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Угол:"))
        
        self.angle_slider = QSlider(Qt.Horizontal)
        self.angle_slider.setRange(0, 359)
        self.angle_slider.setValue(90)
        self.angle_slider.setTickPosition(QSlider.TicksBelow)
        self.angle_slider.setTickInterval(45)
        self.angle_slider.valueChanged.connect(self.update_params)
        
        self.angle_label = QLabel("90°")
        
        angle_layout.addWidget(self.angle_slider)
        angle_layout.addWidget(self.angle_label)
        
        self.params_layout.addLayout(angle_layout)
        
        # Инициализируем параметры
        self.params = {
            "angle": 90,
            "mode": self.mode
        }
    
    def update_params(self, value=None):
        if value is not None:
            self.angle_label.setText(f"{value}°")
            self.params["angle"] = value


class BrightnessEffect(EffectWidget):
    """
    Эффект изменения яркости изображения
    """
    def __init__(self, parent=None):
        super().__init__("Яркость", parent)
        
        # Добавляем параметры
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(QLabel("Значение:"))
        
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setTickPosition(QSlider.TicksBelow)
        self.brightness_slider.setTickInterval(25)
        self.brightness_slider.valueChanged.connect(self.update_params)
        
        self.brightness_label = QLabel("0")
        
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        
        self.params_layout.addLayout(brightness_layout)
        
        # Инициализируем параметры
        self.params = {
            "brightness": 0,
            "mode": self.mode
        }
    
    def update_params(self, value=None):
        if value is not None:
            self.brightness_label.setText(str(value))
            self.params["brightness"] = value


class EffectListWidget(QListWidget):
    """
    Виджет для отображения и управления списком эффектов
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)
        
    def add_effect(self, effect_widget):
        """
        Добавляет эффект в список
        """
        item = QListWidgetItem()
        item.setSizeHint(effect_widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, effect_widget)
    
    def get_effects(self):
        """
        Возвращает список данных всех эффектов
        """
        effects = []
        for i in range(self.count()):
            item = self.item(i)
            effect_widget = self.itemWidget(item)
            effects.append(effect_widget.get_effect_data())
        return effects


class AvailableEffectsWidget(QWidget):
    """
    Виджет с доступными эффектами для добавления в пайплайн
    """
    def __init__(self, pipeline_widget, parent=None):
        super().__init__(parent)
        self.pipeline_widget = pipeline_widget
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Доступные эффекты"))
        
        # Кнопки эффектов
        flip_btn = QPushButton("Добавить отражение")
        flip_btn.clicked.connect(lambda: self.add_effect_to_pipeline(FlipEffect))
        
        rotation_btn = QPushButton("Добавить поворот")
        rotation_btn.clicked.connect(lambda: self.add_effect_to_pipeline(RotationEffect))
        
        brightness_btn = QPushButton("Добавить яркость")
        brightness_btn.clicked.connect(lambda: self.add_effect_to_pipeline(BrightnessEffect))
        
        layout.addWidget(flip_btn)
        layout.addWidget(rotation_btn)
        layout.addWidget(brightness_btn)
        layout.addStretch()
    
    def add_effect_to_pipeline(self, effect_class):
        """
        Добавляет новый эффект в пайплайн
        """
        effect = effect_class()
        self.pipeline_widget.add_effect(effect)


class ExportAnnotationsDialog(QDialog):
    """
    Диалоговое окно для экспорта аннотаций
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Экспорт аннотаций")
        self.setMinimumSize(800, 600)
        
        self.init_ui()
    
    def init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        main_layout = QVBoxLayout(self)
        
        # Путь сохранения
        path_group = QGroupBox("Путь сохранения")
        path_layout = QHBoxLayout(path_group)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Выберите директорию для сохранения...")
        self.path_edit.setReadOnly(True)
        
        self.browse_btn = QPushButton("Обзор...")
        self.browse_btn.clicked.connect(self.browse_save_path)
        
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        
        main_layout.addWidget(path_group)
        
        # Режим экспорта
        mode_group = QGroupBox("Режим экспорта")
        mode_layout = QHBoxLayout(mode_group)
        
        self.segmentation_radio = QRadioButton("Сегментация (YOLO)")
        self.detection_radio = QRadioButton("Детекция (YOLO)")
        self.segmentation_radio.setChecked(True)
        
        mode_layout.addWidget(self.segmentation_radio)
        mode_layout.addWidget(self.detection_radio)
        
        main_layout.addWidget(mode_group)
        
        # Разбиение на выборки
        split_group = QGroupBox("Разбиение на выборки")
        split_layout = QVBoxLayout(split_group)
        
        train_layout = QHBoxLayout()
        train_layout.addWidget(QLabel("Train:"))
        self.train_slider = QSlider(Qt.Horizontal)
        self.train_slider.setRange(0, 100)
        self.train_slider.setValue(80)
        self.train_slider.valueChanged.connect(self.on_train_value_changed)
        train_layout.addWidget(self.train_slider)
        self.train_label = QLabel("80%")
        train_layout.addWidget(self.train_label)
        
        val_layout = QHBoxLayout()
        val_layout.addWidget(QLabel("Validation:"))
        self.val_slider = QSlider(Qt.Horizontal)
        self.val_slider.setRange(0, 100)
        self.val_slider.setValue(10)
        self.val_slider.valueChanged.connect(self.on_val_value_changed)
        val_layout.addWidget(self.val_slider)
        self.val_label = QLabel("10%")
        val_layout.addWidget(self.val_label)
        
        test_layout = QHBoxLayout()
        test_layout.addWidget(QLabel("Test:"))
        self.test_slider = QSlider(Qt.Horizontal)
        self.test_slider.setRange(0, 100)
        self.test_slider.setValue(10)
        self.test_slider.setEnabled(False)  # Авто-вычисление
        test_layout.addWidget(self.test_slider)
        self.test_label = QLabel("10%")
        test_layout.addWidget(self.test_label)
        
        split_layout.addLayout(train_layout)
        split_layout.addLayout(val_layout)
        split_layout.addLayout(test_layout)
        
        main_layout.addWidget(split_group)
        
        # Эффекты и аугментации
        effects_group = QGroupBox("Эффекты и аугментации")
        effects_layout = QHBoxLayout(effects_group)
        
        # Создаем разделитель
        effects_splitter = QSplitter(Qt.Horizontal)
        
        # Левая часть: пайплайн эффектов
        pipeline_container = QWidget()
        pipeline_layout = QVBoxLayout(pipeline_container)
        pipeline_layout.addWidget(QLabel("Пайплайн обработки"))
        
        self.pipeline_list = EffectListWidget()
        pipeline_layout.addWidget(self.pipeline_list)
        
        # Правая часть: доступные эффекты
        effects_container = QWidget()
        self.available_effects = AvailableEffectsWidget(self.pipeline_list, self)
        effects_container.setLayout(QVBoxLayout())
        effects_container.layout().addWidget(self.available_effects)
        
        # Добавляем контейнеры в разделитель
        effects_splitter.addWidget(pipeline_container)
        effects_splitter.addWidget(effects_container)
        effects_splitter.setSizes([400, 400])
        
        effects_layout.addWidget(effects_splitter)
        
        main_layout.addWidget(effects_group)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.export_btn = QPushButton("Экспорт")
        self.export_btn.clicked.connect(self.start_export)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(buttons_layout)
    
    def browse_save_path(self):
        """
        Открывает диалог выбора директории для сохранения
        """
        path = QFileDialog.getExistingDirectory(self, "Выберите директорию для сохранения")
        if path:
            self.path_edit.setText(path)
    
    def on_train_value_changed(self, value):
        """
        Обработчик изменения значения слайдера Train
        """
        self.train_label.setText(f"{value}%")
        # Авто-пересчет Test
        test_value = 100 - value - self.val_slider.value()
        if test_value < 0:
            # Корректируем Val, если Test становится отрицательным
            self.val_slider.setValue(100 - value)
            test_value = 0
        self.test_slider.setValue(test_value)
        self.test_label.setText(f"{test_value}%")
    
    def on_val_value_changed(self, value):
        """
        Обработчик изменения значения слайдера Validation
        """
        self.val_label.setText(f"{value}%")
        # Авто-пересчет Test
        test_value = 100 - self.train_slider.value() - value
        if test_value < 0:
            # Корректируем, если Test становится отрицательным
            self.val_slider.setValue(100 - self.train_slider.value())
            test_value = 0
        self.test_slider.setValue(test_value)
        self.test_label.setText(f"{test_value}%")
    
    def start_export(self):
        """
        Начинает процесс экспорта аннотаций
        """
        # Проверяем выбран ли путь для сохранения
        save_path = self.path_edit.text()
        if not save_path:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите путь для сохранения")
            return
        
        # Получаем настройки экспорта
        export_mode = "segmentation" if self.segmentation_radio.isChecked() else "detection"
        train_ratio = self.train_slider.value() / 100.0
        val_ratio = self.val_slider.value() / 100.0
        test_ratio = self.test_slider.value() / 100.0
        effects = self.pipeline_list.get_effects()
        
        # Создаем отдельный поток для экспорта
        self.export_thread = ExportThread(
            self.parent, 
            save_path, 
            export_mode, 
            train_ratio, 
            val_ratio, 
            test_ratio, 
            effects
        )
        
        # Создаем диалог прогресса
        self.progress_dialog = QProgressDialog("Экспорт аннотаций...", "Отмена", 0, 100, self)
        self.progress_dialog.setWindowTitle("Прогресс экспорта")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.canceled.connect(self.cancel_export)
        
        # Подключаем сигналы
        self.export_thread.progress_updated.connect(self.update_progress)
        self.export_thread.export_finished.connect(self.on_export_finished)
        
        # Запускаем экспорт
        self.export_thread.start()
        self.progress_dialog.exec_()
    
    def cancel_export(self):
        """
        Отменяет процесс экспорта
        """
        if hasattr(self, 'export_thread') and self.export_thread.isRunning():
            self.export_thread.terminate()
            self.export_thread.wait()
    
    def update_progress(self, value, message):
        """
        Обновляет прогресс экспорта
        """
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(value)
            self.progress_dialog.setLabelText(message)
    
    def on_export_finished(self, success, message):
        """
        Обработчик завершения экспорта
        """
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(100)
            self.progress_dialog.setLabelText("Экспорт завершен")
            
        QTimer.singleShot(500, self.progress_dialog.close)
        
        if success:
            QMessageBox.information(self, "Успех", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
        
        self.close()


class ExportThread(QThread):
    """
    Поток для выполнения экспорта аннотаций в фоновом режиме
    """
    progress_updated = pyqtSignal(int, str)
    export_finished = pyqtSignal(bool, str)
    
    def __init__(self, main_window, save_path, export_mode, train_ratio, val_ratio, test_ratio, effects):
        super().__init__()
        self.main_window = main_window
        self.save_path = save_path
        self.export_mode = export_mode
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.effects = effects
    
    def run(self):
        """
        Выполняет экспорт аннотаций
        """
        try:
            # Получаем ImageViewer для доступа к аннотациям
            if hasattr(self.main_window, 'image_viewer'):
                image_viewer = self.main_window.image_viewer
                annotation_manager = image_viewer.annotation_manager
                
                # Сохраняем текущие аннотации, если есть
                if image_viewer.current_image_path:
                    image_viewer.save_current_annotations()
                
                # Создаем директории для экспорта
                export_dir = os.path.join(self.save_path, f"dataset_{self.export_mode}")
                os.makedirs(export_dir, exist_ok=True)
                
                # Создаем директории для train/val/test
                train_dir = os.path.join(export_dir, "train")
                val_dir = os.path.join(export_dir, "val")
                test_dir = os.path.join(export_dir, "test")
                
                os.makedirs(os.path.join(train_dir, "images"), exist_ok=True)
                os.makedirs(os.path.join(train_dir, "labels"), exist_ok=True)
                os.makedirs(os.path.join(val_dir, "images"), exist_ok=True)
                os.makedirs(os.path.join(val_dir, "labels"), exist_ok=True)
                os.makedirs(os.path.join(test_dir, "images"), exist_ok=True)
                os.makedirs(os.path.join(test_dir, "labels"), exist_ok=True)
                
                # Получаем все аннотации
                all_annotations = annotation_manager.annotations_by_image
                
                # Общее количество изображений для расчета прогресса
                total_images = len(all_annotations)
                if total_images == 0:
                    self.export_finished.emit(False, "Нет аннотаций для экспорта")
                    return
                
                # Настройка сортировки для стабильного разделения на выборки
                image_paths = sorted(list(all_annotations.keys()))
                
                # Определяем количество изображений для каждой выборки
                train_count = int(total_images * self.train_ratio)
                val_count = int(total_images * self.val_ratio)
                test_count = total_images - train_count - val_count
                
                # Делим изображения на выборки
                train_images = image_paths[:train_count]
                val_images = image_paths[train_count:train_count + val_count]
                test_images = image_paths[train_count + val_count:]
                
                # Создаем файл data.yaml с конфигурацией для YOLO
                classes = {}
                for img_path, annotations in all_annotations.items():
                    for ann in annotations:
                        if 'class' in ann and 'name' in ann['class']:
                            class_name = ann['class']['name']
                            if class_name and class_name not in classes:
                                classes[class_name] = len(classes)
                
                if not classes:
                    self.export_finished.emit(False, "Нет классов в аннотациях")
                    return
                
                # Создаем data.yaml
                data_yaml = {
                    'path': export_dir,
                    'train': os.path.join('train', 'images'),
                    'val': os.path.join('val', 'images'),
                    'test': os.path.join('test', 'images'),
                    'nc': len(classes),
                    'names': list(classes.keys())
                }
                
                with open(os.path.join(export_dir, 'data.yaml'), 'w') as f:
                    f.write("path: " + export_dir + "\n")
                    f.write("train: train/images\n")
                    f.write("val: val/images\n")
                    f.write("test: test/images\n\n")
                    f.write(f"nc: {len(classes)}\n")
                    f.write("names: [" + ", ".join([f"'{name}'" for name in classes.keys()]) + "]\n")
                
                # Экспорт изображений и аннотаций
                processed_count = 0
                
                # Обрабатываем train выборку
                self.export_dataset_split("train", train_images, train_dir, classes, 
                                         all_annotations, processed_count, total_images)
                processed_count += len(train_images)
                
                # Обрабатываем val выборку
                self.export_dataset_split("val", val_images, val_dir, classes, 
                                         all_annotations, processed_count, total_images)
                processed_count += len(val_images)
                
                # Обрабатываем test выборку
                self.export_dataset_split("test", test_images, test_dir, classes, 
                                         all_annotations, processed_count, total_images)
                
                self.export_finished.emit(True, f"Экспорт успешно завершен. Данные сохранены в {export_dir}")
            else:
                self.export_finished.emit(False, "Не удалось получить доступ к аннотациям")
        except Exception as e:
            logger.error(f"Ошибка при экспорте: {str(e)}")
            self.export_finished.emit(False, f"Ошибка при экспорте: {str(e)}")
    
    def export_dataset_split(self, split_name, image_paths, output_dir, classes, all_annotations, 
                            processed_count, total_images):
        """
        Экспортирует часть датасета (train/val/test)
        """
        import shutil
        from PIL import Image
        import numpy as np
        
        images_dir = os.path.join(output_dir, "images")
        labels_dir = os.path.join(output_dir, "labels")
        
        for i, img_path in enumerate(image_paths):
            # Обновляем прогресс
            current_progress = int((processed_count + i) / total_images * 100)
            self.progress_updated.emit(current_progress, 
                                       f"Обработка {split_name} выборки: {i+1}/{len(image_paths)}")
            
            try:
                # Копируем изображение
                img_filename = os.path.basename(img_path)
                img_name, img_ext = os.path.splitext(img_filename)
                
                # Создаем новое имя файла для YOLO формата
                yolo_img_path = os.path.join(images_dir, f"{img_name}{img_ext}")
                
                # Копируем изображение
                shutil.copy2(img_path, yolo_img_path)
                
                # Получаем размеры изображения
                with Image.open(img_path) as img:
                    img_width, img_height = img.size
                
                # Создаем YOLO label файл
                annotations = all_annotations.get(img_path, [])
                
                # Имя файла с аннотациями
                label_filename = os.path.join(labels_dir, f"{img_name}.txt")
                
                with open(label_filename, 'w') as f:
                    for ann in annotations:
                        if 'class' in ann and 'name' in ann['class']:
                            class_name = ann['class']['name']
                            if class_name in classes:
                                class_id = classes[class_name]
                                
                                if self.export_mode == "segmentation" and ann['type'] == 'polygon':
                                    # Для сегментации в YOLO формате
                                    points_data = ann['points']
                                    # Нормализация координат для YOLO (относительно размеров изображения)
                                    normalized_points = []
                                    for p in points_data:
                                        x_norm = p['x']
                                        y_norm = p['y']
                                        normalized_points.append(f"{x_norm:.6f} {y_norm:.6f}")
                                    
                                    # Запись в формате: class_id x1 y1 x2 y2 ... xn yn
                                    f.write(f"{class_id} {' '.join(normalized_points)}\n")
                                    
                                elif self.export_mode == "detection" or (self.export_mode == "segmentation" and ann['type'] == 'rect'):
                                    # Для детекции используем bounding box
                                    if ann['type'] == 'rect':
                                        # Прямоугольник
                                        coords = ann['coords']
                                        # Для YOLO нам нужен центр и размеры
                                        x_center = coords['x'] + coords['width'] / 2
                                        y_center = coords['y'] + coords['height'] / 2
                                        width = coords['width']
                                        height = coords['height']
                                        
                                        # Запись в формате: class_id x_center y_center width height
                                        f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                                    elif ann['type'] == 'polygon':
                                        # Для полигона создаем ограничивающий прямоугольник
                                        points_data = ann['points']
                                        x_coords = [p['x'] for p in points_data]
                                        y_coords = [p['y'] for p in points_data]
                                        
                                        # Находим границы
                                        min_x = min(x_coords)
                                        max_x = max(x_coords)
                                        min_y = min(y_coords)
                                        max_y = max(y_coords)
                                        
                                        # Вычисляем центр и размеры для YOLO формата
                                        x_center = (min_x + max_x) / 2
                                        y_center = (min_y + max_y) / 2
                                        width = max_x - min_x
                                        height = max_y - min_y
                                        
                                        # Запись в формате: class_id x_center y_center width height
                                        f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            except Exception as e:
                logger.error(f"Ошибка при обработке {img_path}: {str(e)}")
                # Продолжаем с другими изображениями 