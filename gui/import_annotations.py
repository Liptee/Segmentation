import sys
import os
import json
import yaml
import random
import shutil
import platform  # Для определения ОС
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QGroupBox, QProgressDialog, QMessageBox, QCheckBox,
    QWidget, QListWidget, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QColor

from logger import logger

# Определяем, работаем ли мы на macOS
IS_MACOS = platform.system() == 'Darwin'

class ImportAnnotationsDialog(QDialog):
    """
    Диалоговое окно для импорта аннотаций из набора данных YOLO
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Импорт аннотаций")
        self.setMinimumSize(600, 400)
        
        self.dataset_path = ""
        self.yaml_path = ""
        self.json_path = ""
        
        self.init_ui()
    
    def init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        main_layout = QVBoxLayout(self)
        
        # Путь к набору данных
        dataset_group = QGroupBox("Набор данных YOLO")
        dataset_layout = QVBoxLayout(dataset_group)
        
        # Информация о структуре набора данных
        dataset_info = QLabel("Выберите директорию, содержащую набор данных YOLO со следующей структурой:\n"
                           "  - train/\n"
                           "    - images/\n"
                           "    - labels/\n"
                           "  - val/\n"
                           "    - images/\n"
                           "    - labels/\n"
                           "  - test/\n"
                           "    - images/\n"
                           "    - labels/\n"
                           "  - data.yaml")
        dataset_info.setWordWrap(True)
        dataset_layout.addWidget(dataset_info)
        
        # Выбор директории с набором данных
        path_layout = QHBoxLayout()
        
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("Путь к директории с набором данных YOLO...")
        self.dataset_path_edit.setReadOnly(True)
        
        self.browse_dataset_btn = QPushButton("Обзор...")
        self.browse_dataset_btn.clicked.connect(self.browse_dataset_path)
        
        path_layout.addWidget(self.dataset_path_edit)
        path_layout.addWidget(self.browse_dataset_btn)
        
        dataset_layout.addLayout(path_layout)
        
        # Статус проверки набора данных
        self.dataset_status_label = QLabel("Выберите директорию с набором данных")
        self.dataset_status_label.setStyleSheet("color: palette(text);")
        dataset_layout.addWidget(self.dataset_status_label)
        
        # Добавляем чекбоксы для выбора папок импорта
        folders_group = QGroupBox("Выберите папки для импорта")
        folders_layout = QVBoxLayout(folders_group)
        
        self.train_checkbox = QCheckBox("Импортировать из train")
        self.train_checkbox.setChecked(True)  # По умолчанию включено
        folders_layout.addWidget(self.train_checkbox)
        
        self.val_checkbox = QCheckBox("Импортировать из val")
        folders_layout.addWidget(self.val_checkbox)
        
        self.test_checkbox = QCheckBox("Импортировать из test")
        folders_layout.addWidget(self.test_checkbox)
        
        dataset_layout.addWidget(folders_group)
        
        main_layout.addWidget(dataset_group)
        
        # Импорт JSON с классами и цветами
        json_group = QGroupBox("Импорт классов из JSON")
        json_layout = QVBoxLayout(json_group)
        
        json_info = QLabel("Вы можете дополнительно импортировать классы и их цвета из JSON-файла с аннотациями. "
                         "В случае конфликтов имен классов, приоритет будет отдан классам из YAML-файла.")
        json_info.setWordWrap(True)
        json_layout.addWidget(json_info)
        
        # Опция импорта JSON
        self.import_json_check = QCheckBox("Импортировать классы из JSON-файла")
        self.import_json_check.setChecked(False)
        self.import_json_check.stateChanged.connect(self.on_import_json_changed)
        json_layout.addWidget(self.import_json_check)
        
        # Выбор JSON-файла
        json_path_layout = QHBoxLayout()
        
        self.json_path_edit = QLineEdit()
        self.json_path_edit.setPlaceholderText("Путь к JSON-файлу с классами...")
        self.json_path_edit.setReadOnly(True)
        self.json_path_edit.setEnabled(False)
        
        self.browse_json_btn = QPushButton("Обзор...")
        self.browse_json_btn.clicked.connect(self.browse_json_path)
        self.browse_json_btn.setEnabled(False)
        
        json_path_layout.addWidget(self.json_path_edit)
        json_path_layout.addWidget(self.browse_json_btn)
        
        json_layout.addLayout(json_path_layout)
        
        # Статус проверки JSON
        self.json_status_label = QLabel("Опция отключена")
        self.json_status_label.setStyleSheet("color: palette(mid);")
        json_layout.addWidget(self.json_status_label)
        
        main_layout.addWidget(json_group)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.import_btn = QPushButton("Импорт")
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.import_btn)
        
        main_layout.addLayout(buttons_layout)
    
    def browse_dataset_path(self):
        """
        Открывает диалог выбора директории с набором данных
        """
        path = QFileDialog.getExistingDirectory(self, "Выберите директорию с набором данных YOLO")
        if path:
            self.dataset_path = path
            self.dataset_path_edit.setText(path)
            self.validate_dataset()
    
    def validate_dataset(self):
        """
        Проверяет структуру набора данных и наличие YAML-файла
        """
        # Проверяем наличие необходимых директорий
        required_dirs = [
            os.path.join(self.dataset_path, "train", "images"),
            os.path.join(self.dataset_path, "train", "labels"),
            os.path.join(self.dataset_path, "val", "images"),
            os.path.join(self.dataset_path, "val", "labels"),
        ]
        
        # Также проверяем наличие директорий test, но они необязательны
        test_dirs = [
            os.path.join(self.dataset_path, "test", "images"),
            os.path.join(self.dataset_path, "test", "labels"),
        ]
        
        has_required_dirs = all(os.path.isdir(d) for d in required_dirs)
        has_test_dirs = all(os.path.isdir(d) for d in test_dirs)
        
        # Ищем YAML-файл
        yaml_files = [f for f in os.listdir(self.dataset_path) if f.endswith(".yaml") or f.endswith(".yml")]
        
        if not yaml_files:
            self.dataset_status_label.setText("Ошибка: Не найден YAML-файл в директории набора данных")
            self.dataset_status_label.setStyleSheet("color: red;")
            self.import_btn.setEnabled(False)
            return False
        
        # Проверяем YAML-файл (берем первый найденный)
        self.yaml_path = os.path.join(self.dataset_path, yaml_files[0])
        try:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            # Проверяем наличие классов в YAML
            if 'names' not in yaml_data or not yaml_data['names']:
                self.dataset_status_label.setText("Ошибка: В YAML-файле не найдены классы (ключ 'names')")
                self.dataset_status_label.setStyleSheet("color: red;")
                self.import_btn.setEnabled(False)
                return False
            
            # Проверяем наличие изображений в директориях
            train_images = os.listdir(os.path.join(self.dataset_path, "train", "images"))
            val_images = os.listdir(os.path.join(self.dataset_path, "val", "images"))
            
            if not train_images and not val_images:
                self.dataset_status_label.setText("Предупреждение: Не найдены изображения в train и val директориях")
                self.dataset_status_label.setStyleSheet("color: orange;")
            else:
                if has_required_dirs and has_test_dirs:
                    self.dataset_status_label.setText(f"Корректная структура набора данных. Классов: {len(yaml_data['names'])}")
                else:
                    self.dataset_status_label.setText(f"Базовая структура набора данных. Классов: {len(yaml_data['names'])}")
                self.dataset_status_label.setStyleSheet("color: green;")
                self.import_btn.setEnabled(True)
                return True
            
        except Exception as e:
            self.dataset_status_label.setText(f"Ошибка при чтении YAML-файла: {str(e)}")
            self.dataset_status_label.setStyleSheet("color: red;")
            self.import_btn.setEnabled(False)
            return False
    
    def on_import_json_changed(self, state):
        """
        Обработчик изменения состояния чекбокса импорта JSON
        """
        enabled = state == Qt.Checked
        self.json_path_edit.setEnabled(enabled)
        self.browse_json_btn.setEnabled(enabled)
        
        if enabled:
            self.json_status_label.setText("Выберите JSON-файл с классами")
            self.json_status_label.setStyleSheet("color: palette(text);")
        else:
            self.json_status_label.setText("Опция отключена")
            self.json_status_label.setStyleSheet("color: palette(mid);")
            self.json_path = ""
            self.json_path_edit.setText("")
    
    def browse_json_path(self):
        """
        Открывает диалог выбора JSON-файла с классами
        """
        path, _ = QFileDialog.getOpenFileName(self, "Выберите JSON-файл с классами", "", "JSON Files (*.json)")
        if path:
            self.json_path = path
            self.json_path_edit.setText(path)
            self.validate_json()
    
    def validate_json(self):
        """
        Проверяет структуру JSON-файла с классами
        Структура JSON-файла:
        [
            {
                "name": "class_name",
                "color": "color_hex"
                "description": "description_text"
            },
            {
                "name": "class_name",
                "color": "color_hex"
                "description": "description_text"
            },
            
        ]
        """
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            for item in json_data:
                if 'name' in item and 'color' in item and 'description' in item:
                    self.json_status_label.setText(f"JSON-файл валиден. Найдено классов: {len(json_data)}")
                    self.json_status_label.setStyleSheet("color: green;")
                    return True
            
            self.json_status_label.setText("Предупреждение: Не найдены классы в JSON-файле")

        
        except Exception as e:
            self.json_status_label.setText(f"Ошибка при чтении JSON-файла: {str(e)}")
            self.json_status_label.setStyleSheet("color: red;")
            return False
    
    def start_import(self):
        """
        Начинает процесс импорта аннотаций
        """
        if not self.dataset_path or not self.yaml_path:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите корректную директорию с набором данных")
            return
        
        if self.import_json_check.isChecked() and not self.json_path:
            QMessageBox.warning(self, "Предупреждение", "Включена опция импорта JSON, но файл не выбран")
            return
        
        # Проверяем, что хотя бы одна папка выбрана
        if not (self.train_checkbox.isChecked() or self.val_checkbox.isChecked() or self.test_checkbox.isChecked()):
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одну папку для импорта")
            return
        
        # Формируем список выбранных папок
        selected_folders = []
        if self.train_checkbox.isChecked():
            selected_folders.append("train")
        if self.val_checkbox.isChecked():
            selected_folders.append("val")
        if self.test_checkbox.isChecked():
            selected_folders.append("test")
        
        # Создаем диалог прогресса
        self.progress_dialog = QProgressDialog("Импорт аннотаций...", "Отмена", 0, 100, self)
        self.progress_dialog.setWindowTitle("Прогресс импорта")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        
        # На macOS выполняем импорт в основном потоке из-за ограничений Qt
        if IS_MACOS:
            self.progress_dialog.canceled.connect(self.close)
            self.progress_dialog.show()
            QApplication.processEvents()
            
            # Создаем импортер
            importer = ImportHelper(
                self.parent,
                self.dataset_path,
                self.yaml_path,
                self.json_path if self.import_json_check.isChecked() else "",
                selected_folders
            )
            
            # Обработчик прогресса
            def update_progress(value, message):
                self.progress_dialog.setValue(value)
                self.progress_dialog.setLabelText(message)
                QApplication.processEvents()
            
            # Выполняем импорт
            try:
                success, message, class_conflicts = importer.import_annotations(update_progress)
                # Закрываем диалог прогресса
                self.progress_dialog.setValue(100)
                self.progress_dialog.setLabelText("Импорт завершен")
                QApplication.processEvents()
                QTimer.singleShot(500, self.progress_dialog.close)
                
                # Показываем результат
                if success:
                    QMessageBox.information(self, "Успех", message)
                    
                    # Если были конфликты классов, показываем информационное сообщение
                    if class_conflicts and isinstance(class_conflicts, dict) and class_conflicts:
                        conflict_message = "При импорте были обнаружены конфликты имен классов:\n\n"
                        for yaml_name, json_name in class_conflicts.items():
                            conflict_message += f"• Класс из YAML: '{yaml_name}' заменил класс из JSON: '{json_name}'\n"
                        conflict_message += "\nЦвета классов из JSON были сохранены."
                        
                        QMessageBox.information(self, "Конфликты классов", conflict_message)
                    
                    self.accept()  # Закрываем диалог при успешном импорте
                else:
                    QMessageBox.critical(self, "Ошибка", message)
            except Exception as e:
                logger.error(f"Ошибка при импорте: {str(e)}")
                self.progress_dialog.close()
                QMessageBox.critical(self, "Ошибка", f"Ошибка при импорте: {str(e)}")
        else:
            # На других платформах используем потоки
            self.progress_dialog.canceled.connect(self.cancel_import)
            
            # Создаем отдельный поток для импорта
            self.import_thread = ImportThread(
                self.parent,
                self.dataset_path,
                self.yaml_path,
                self.json_path if self.import_json_check.isChecked() else "",
                selected_folders
            )
            
            # Подключаем сигналы
            self.import_thread.progress_updated.connect(self.update_progress)
            self.import_thread.import_finished.connect(self.on_import_finished)
            
            # Запускаем импорт
            self.import_thread.start()
            self.progress_dialog.exec_()
    
    def cancel_import(self):
        """
        Отменяет процесс импорта
        """
        if hasattr(self, 'import_thread') and self.import_thread.isRunning():
            self.import_thread.terminate()
            self.import_thread.wait()
    
    def update_progress(self, value, message):
        """
        Обновляет прогресс импорта
        """
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(value)
            self.progress_dialog.setLabelText(message)
    
    def on_import_finished(self, success, message, class_conflicts=None):
        """
        Обработчик завершения импорта
        """
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(100)
            self.progress_dialog.setLabelText("Импорт завершен")
        
        # Закрываем прогресс-диалог через небольшую задержку
        QTimer.singleShot(500, self.progress_dialog.close)
        
        if success:
            QMessageBox.information(self, "Успех", message)
            self.accept()  # Закрываем диалог при успешном импорте
        else:
            QMessageBox.critical(self, "Ошибка", message)
        
        # Если были конфликты классов, показываем информационное сообщение
        if class_conflicts and isinstance(class_conflicts, dict) and class_conflicts:
            conflict_message = "При импорте были обнаружены конфликты имен классов:\n\n"
            for yaml_name, json_name in class_conflicts.items():
                conflict_message += f"• Класс из YAML: '{yaml_name}' заменил класс из JSON: '{json_name}'\n"
            conflict_message += "\nЦвета классов из JSON были сохранены."
            
            QMessageBox.information(self, "Конфликты классов", conflict_message)


class ImportThread(QThread):
    """
    Поток для выполнения импорта аннотаций в фоновом режиме
    """
    progress_updated = pyqtSignal(int, str)
    import_finished = pyqtSignal(bool, str, object)
    
    def __init__(self, main_window, dataset_path, yaml_path, json_path="", selected_folders=None):
        super().__init__()
        self.main_window = main_window
        self.dataset_path = dataset_path
        self.yaml_path = yaml_path
        self.json_path = json_path
        self.selected_folders = selected_folders or ["train"]  # По умолчанию импортируем только из train
        self.class_conflicts = {}  # Словарь для хранения конфликтов классов
    
    def run(self):
        """
        Выполняет импорт аннотаций
        """
        try:
            # Загружаем классы из YAML
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            yaml_classes = yaml_data.get('names', [])
            if not yaml_classes:
                self.import_finished.emit(False, "В YAML-файле не найдены классы", None)
                return
            
            # Преобразуем классы из YAML в список, если это словарь
            if isinstance(yaml_classes, dict):
                yaml_classes = [yaml_classes[i] for i in sorted(yaml_classes.keys())]
            
            # Генерируем случайные цвета для классов из YAML
            class_colors = {}
            
            for class_name in yaml_classes:
                # Генерируем случайный цвет
                r, g, b = random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)
                class_colors[class_name] = QColor(r, g, b)
            
            # Если есть JSON, загружаем из него классы и цвета
            if self.json_path:
                self.progress_updated.emit(5, "Загрузка классов из JSON...")
                
                try:
                    with open(self.json_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    json_classes = {}
                    
                    # Собираем информацию о классах из аннотаций в JSON
                    for img_path, annotations in json_data.get('images', {}).items():
                        for ann in annotations:
                            if 'class' in ann and ann['class'].get('name'):
                                class_name = ann['class']['name']
                                color_str = ann['class'].get('color')
                                
                                if class_name and color_str and class_name not in json_classes:
                                    try:
                                        color = QColor(color_str)
                                        json_classes[class_name] = color
                                    except:
                                        # Если не удалось преобразовать строку в цвет, используем случайный
                                        r, g, b = random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)
                                        json_classes[class_name] = QColor(r, g, b)
                    
                    # Проверяем конфликты и приоритеты классов
                    for json_class_name, json_color in json_classes.items():
                        if json_class_name in yaml_classes:
                            # Конфликт имен - приоритет имеет YAML, но цвет берем из JSON
                            class_colors[json_class_name] = json_color
                            # Сохраняем информацию о конфликте
                            self.class_conflicts[json_class_name] = json_class_name
                        else:
                            # Уникальный класс из JSON - добавляем его и цвет
                            yaml_classes.append(json_class_name)
                            class_colors[json_class_name] = json_color
                    
                except Exception as e:
                    logger.error(f"Ошибка при чтении JSON-файла: {str(e)}")
                    # Продолжаем импорт, но без данных из JSON
            
            # Получаем список изображений для импорта из всех выбранных папок
            image_files = []
            for folder in self.selected_folders:
                import_images_dir = os.path.join(self.dataset_path, folder, "images")
                if os.path.exists(import_images_dir):
                    for root, _, files in os.walk(import_images_dir):
                        for file in files:
                            if file.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                                image_path = os.path.join(root, file)
                                image_files.append((image_path, folder))  # Сохраняем и путь, и папку источник
            
            if not image_files:
                self.import_finished.emit(False, "Не найдены изображения для импорта в выбранных папках", None)
                return
            
            # Импортируем изображения и аннотации
            self.progress_updated.emit(10, f"Импорт изображений и аннотаций (0/{len(image_files)})...")
            
            # Получаем ImageViewer для доступа к функциям импорта
            if hasattr(self.main_window, 'image_viewer'):
                image_viewer = self.main_window.image_viewer
                
                # Обновляем классы в менеджере классов
                if hasattr(self.main_window, 'class_manager'):
                    class_manager = self.main_window.class_manager
                    
                    # Очищаем существующие классы
                    class_manager.clear_classes()
                    
                    # Добавляем классы из YAML с цветами
                    for i, class_name in enumerate(yaml_classes):
                        color = class_colors.get(class_name, QColor(120, 120, 120))
                        class_manager.add_class(i, class_name, color)
                
                # Импортируем изображения и аннотации из YOLO
                imported_count = 0
                for i, (image_path, source_folder) in enumerate(image_files):
                    # Обновляем прогресс
                    progress = 10 + int(90 * i / len(image_files))
                    self.progress_updated.emit(progress, f"Импорт изображений и аннотаций ({i+1}/{len(image_files)})...")
                    
                    try:
                        # Получаем имя файла без расширения
                        image_dir = os.path.dirname(image_path)
                        image_name = os.path.splitext(os.path.basename(image_path))[0]
                        
                        # Ищем соответствующий файл меток
                        label_path = None
                        import_labels_dir = os.path.join(self.dataset_path, source_folder, "labels")
                        for label_dir in [import_labels_dir, os.path.join(image_dir, "../labels")]:
                            test_path = os.path.join(label_dir, f"{image_name}.txt")
                            if os.path.exists(test_path):
                                label_path = test_path
                                break
                        
                        if label_path and os.path.exists(label_path):
                            # Копируем изображение в папку данных приложения
                            target_image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "images")
                            os.makedirs(target_image_dir, exist_ok=True)
                            
                            target_image_path = os.path.join(target_image_dir, os.path.basename(image_path))
                            shutil.copy2(image_path, target_image_path)
                            
                            # Импортируем аннотацию
                            self.import_yolo_annotation(image_viewer, target_image_path, label_path, yaml_classes, class_colors)
                            
                            imported_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при импорте {image_path}: {str(e)}")
                        # Продолжаем с другими изображениями
                
                # Обновляем список медиа
                if hasattr(self.main_window, 'media_importer'):
                    media_importer = self.main_window.media_importer
                    
                    # Перед обновлением списка, добавляем все импортированные файлы
                    for i, (image_path, source_folder) in enumerate(image_files):
                        try:
                            # Получаем имя файла
                            image_name = os.path.basename(image_path)
                            # Путь назначения
                            target_image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "images")
                            target_image_path = os.path.join(target_image_dir, image_name)
                            
                            # Проверяем, существует ли файл после копирования
                            if os.path.exists(target_image_path):
                                # Импортируем файл в список media_importer
                                media_importer.import_file(target_image_path)
                                
                                # Устанавливаем тип выборки на основе папки источника
                                dataset_type_mapping = {"train": "train", "val": "val", "test": "test"}
                                dataset_type = dataset_type_mapping.get(source_folder, "none")
                                
                                # Находим импортированный элемент и устанавливаем ему тип выборки
                                for media_item in media_importer.imported_items["image"]:
                                    if media_item.file_path == target_image_path:
                                        media_item.dataset_type = dataset_type
                                        break
                                        
                        except Exception as e:
                            logger.error(f"Ошибка при добавлении {image_path} в media_importer: {str(e)}")
                    
                    # Обновляем список
                    media_importer.refresh_list()
                    
                    # Переключаемся на режим изображений, если текущий режим - видео
                    if media_importer.mode != "image":
                        media_importer.switch_to_images()
                
                self.import_finished.emit(True, f"Импорт успешно завершен. Импортировано {imported_count} изображений с аннотациями.", self.class_conflicts)
            else:
                self.import_finished.emit(False, "Не удалось получить доступ к функциям импорта", None)
        except Exception as e:
            logger.error(f"Ошибка при импорте: {str(e)}")
            self.import_finished.emit(False, f"Ошибка при импорте: {str(e)}", None)
    
    def import_yolo_annotation(self, image_viewer, image_path, label_path, classes, class_colors):
        """
        Импортирует аннотацию из файла меток YOLO
        
        :param image_viewer: Объект ImageViewer для добавления аннотаций
        :param image_path: Путь к изображению
        :param label_path: Путь к файлу меток YOLO
        :param classes: Список классов
        :param class_colors: Словарь с цветами для каждого класса
        """
        import cv2
        from PyQt5.QtCore import QPointF, QRectF
        from gui.annotation_items import SelectableRectItem, SelectablePolygonItem
        
        # Получаем размеры изображения
        img = cv2.imread(image_path)
        img_height, img_width = img.shape[:2]
        
        # Читаем файл меток
        with open(label_path, 'r') as f:
            label_lines = f.readlines()
        
        annotations = []
        
        for line in label_lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) < 5:  # Минимум: класс и 4 координаты для bbox
                continue
            
            class_id = int(parts[0])
            if class_id >= len(classes):
                continue  # Пропускаем, если индекс класса вне диапазона
            
            class_name = classes[class_id]
            
            # Определяем тип аннотации по количеству координат
            if len(parts) == 5:  # Bounding box (class_id, x_center, y_center, width, height)
                x_center, y_center, width, height = map(float, parts[1:5])
                
                # Преобразуем нормализованные координаты в абсолютные
                x = (x_center - width/2) * img_width
                y = (y_center - height/2) * img_height
                w = width * img_width
                h = height * img_height
                
                # Получаем цвет класса из словаря
                class_color = class_colors.get(class_name)
                class_color_str = class_color.name() if class_color else None
                
                # Создаем прямоугольник
                rect_item = {
                    'type': 'rect',
                    'coords': {
                        'x': x / img_width,  # Нормализованные координаты для AnnotationManager
                        'y': y / img_height,
                        'width': w / img_width,
                        'height': h / img_height
                    },
                    'position': {'x': 0, 'y': 0},
                    'class': {
                        'id': class_name,  # Используем имя класса как ID вместо числового индекса
                        'name': class_name,
                        'color': class_color_str  # Устанавливаем цвет класса
                    }
                }
                
                annotations.append(rect_item)
                
            elif len(parts) > 5 and len(parts) % 2 == 1:  # Полигон (class_id, x1, y1, x2, y2, ...)
                points = []
                for i in range(1, len(parts), 2):
                    if i+1 < len(parts):
                        x = float(parts[i])
                        y = float(parts[i+1])
                        points.append({'x': x, 'y': y})  # Уже нормализованные координаты
                
                # Получаем цвет класса из словаря
                class_color = class_colors.get(class_name)
                class_color_str = class_color.name() if class_color else None
                
                polygon_item = {
                    'type': 'polygon',
                    'points': points,
                    'position': {'x': 0, 'y': 0},
                    'class': {
                        'id': class_name,  # Используем имя класса как ID вместо числового индекса
                        'name': class_name,
                        'color': class_color_str  # Устанавливаем цвет класса
                    }
                }
                
                annotations.append(polygon_item)
        
        # Сохраняем аннотации в AnnotationManager
        if annotations and hasattr(image_viewer, 'annotation_manager'):
            image_viewer.annotation_manager.annotations_by_image[image_path] = annotations


# Класс-помощник для выполнения импорта без потоков
class ImportHelper:
    def __init__(self, main_window, dataset_path, yaml_path, json_path="", selected_folders=None):
        self.main_window = main_window
        self.dataset_path = dataset_path
        self.yaml_path = yaml_path
        self.json_path = json_path
        self.selected_folders = selected_folders or ["train"]
        self.class_conflicts = {}
    
    def import_annotations(self, progress_callback):
        """
        Выполняет импорт аннотаций и вызывает callback для обновления прогресса
        
        :param progress_callback: функция callback(value, message) для обновления прогресса
        :return: (success, message, class_conflicts)
        """
        try:
            # Загружаем классы из YAML
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            yaml_classes = yaml_data.get('names', [])
            if not yaml_classes:
                return False, "В YAML-файле не найдены классы", None
            
            # Преобразуем классы из YAML в список, если это словарь
            if isinstance(yaml_classes, dict):
                yaml_classes = [yaml_classes[i] for i in sorted(yaml_classes.keys())]
            
            # Генерируем случайные цвета для классов из YAML
            class_colors = {}
        
            
            # Если есть JSON, загружаем из него классы и цвета
            if self.json_path:
                print("Here")
                progress_callback(5, "Загрузка классов из JSON...")
                
                try:
                    with open(self.json_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    json_classes = {}
                    
                    # Собираем информацию о классах из аннотаций в JSON
                    for class_info in  json_data:
                        if class_info['name'] not in yaml_classes:
                            yaml_classes.append(class_info['name'])
                            class_colors[class_info['name']] = QColor(class_info['color'])
                        else:
                            class_colors[class_info['name']] = QColor(class_info['color'])
                    
                except Exception as e:
                    logger.error(f"Ошибка при чтении JSON-файла: {str(e)}")
                    # Продолжаем импорт, но без данных из JSON
            
            else:
                for class_name in yaml_classes:
                    # Генерируем случайный цвет
                    r, g, b = random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)
                    class_colors[class_name] = QColor(r, g, b)

            # Получаем список изображений для импорта из всех выбранных папок
            image_files = []
            for folder in self.selected_folders:
                import_images_dir = os.path.join(self.dataset_path, folder, "images")
                if os.path.exists(import_images_dir):
                    for root, _, files in os.walk(import_images_dir):
                        for file in files:
                            if file.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                                image_path = os.path.join(root, file)
                                image_files.append((image_path, folder))  # Сохраняем и путь, и папку источник
            
            if not image_files:
                return False, "Не найдены изображения для импорта в выбранных папках", None
            
            # Импортируем изображения и аннотации
            progress_callback(10, f"Импорт изображений и аннотаций (0/{len(image_files)})...")
            
            # Получаем ImageViewer для доступа к функциям импорта
            if hasattr(self.main_window, 'image_viewer'):
                image_viewer = self.main_window.image_viewer
                
                # Обновляем классы в менеджере классов
                if hasattr(self.main_window, 'class_manager'):
                    class_manager = self.main_window.class_manager
                    
                    # Очищаем существующие классы
                    class_manager.clear_classes()
                    
                    # Добавляем классы из YAML с цветами
                    for i, class_name in enumerate(yaml_classes):
                        color = class_colors.get(class_name, QColor(120, 120, 120))
                        class_manager.add_class(i, class_name, color)
                
                # Импортируем изображения и аннотации из YOLO
                imported_count = 0
                for i, (image_path, source_folder) in enumerate(image_files):
                    # Обновляем прогресс
                    progress = 10 + int(90 * i / len(image_files))
                    progress_callback(progress, f"Импорт изображений и аннотаций ({i+1}/{len(image_files)})...")
                    
                    try:
                        # Получаем имя файла без расширения
                        image_dir = os.path.dirname(image_path)
                        image_name = os.path.splitext(os.path.basename(image_path))[0]
                        
                        # Ищем соответствующий файл меток
                        label_path = None
                        import_labels_dir = os.path.join(self.dataset_path, source_folder, "labels")
                        for label_dir in [import_labels_dir, os.path.join(image_dir, "../labels")]:
                            test_path = os.path.join(label_dir, f"{image_name}.txt")
                            if os.path.exists(test_path):
                                label_path = test_path
                                break
                        
                        if label_path and os.path.exists(label_path):
                            # Копируем изображение в папку данных приложения
                            target_image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "images")
                            os.makedirs(target_image_dir, exist_ok=True)
                            
                            target_image_path = os.path.join(target_image_dir, os.path.basename(image_path))
                            shutil.copy2(image_path, target_image_path)
                            
                            # Импортируем аннотацию
                            self.import_yolo_annotation(image_viewer, target_image_path, label_path, yaml_classes, class_colors)
                            
                            imported_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при импорте {image_path}: {str(e)}")
                        # Продолжаем с другими изображениями
                
                # Обновляем список медиа
                if hasattr(self.main_window, 'media_importer'):
                    media_importer = self.main_window.media_importer
                    
                    # Перед обновлением списка, добавляем все импортированные файлы
                    for i, (image_path, source_folder) in enumerate(image_files):
                        try:
                            # Получаем имя файла
                            image_name = os.path.basename(image_path)
                            # Путь назначения
                            target_image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "images")
                            target_image_path = os.path.join(target_image_dir, image_name)
                            
                            # Проверяем, существует ли файл после копирования
                            if os.path.exists(target_image_path):
                                # Импортируем файл в список media_importer
                                media_importer.import_file(target_image_path)
                                
                                # Устанавливаем тип выборки на основе папки источника
                                dataset_type_mapping = {"train": "train", "val": "val", "test": "test"}
                                dataset_type = dataset_type_mapping.get(source_folder, "none")
                                
                                # Находим импортированный элемент и устанавливаем ему тип выборки
                                for media_item in media_importer.imported_items["image"]:
                                    if media_item.file_path == target_image_path:
                                        media_item.dataset_type = dataset_type
                                        break
                                        
                        except Exception as e:
                            logger.error(f"Ошибка при добавлении {image_path} в media_importer: {str(e)}")
                    
                    # Обновляем список
                    media_importer.refresh_list()
                    
                    # Переключаемся на режим изображений, если текущий режим - видео
                    if media_importer.mode != "image":
                        media_importer.switch_to_images()
                
                return True, f"Импорт успешно завершен. Импортировано {imported_count} изображений с аннотациями.", self.class_conflicts
            else:
                return False, "Не удалось получить доступ к функциям импорта", None
        except Exception as e:
            logger.error(f"Ошибка при импорте: {str(e)}")
            return False, f"Ошибка при импорте: {str(e)}", None
    
    def import_yolo_annotation(self, image_viewer, image_path, label_path, classes, class_colors):
        """
        Импортирует аннотацию из файла меток YOLO
        
        :param image_viewer: Объект ImageViewer для добавления аннотаций
        :param image_path: Путь к изображению
        :param label_path: Путь к файлу меток YOLO
        :param classes: Список классов
        :param class_colors: Словарь с цветами для каждого класса
        """
        import cv2
        from PyQt5.QtCore import QPointF, QRectF
        from gui.annotation_items import SelectableRectItem, SelectablePolygonItem
        
        # Получаем размеры изображения
        img = cv2.imread(image_path)
        img_height, img_width = img.shape[:2]
        
        # Читаем файл меток
        with open(label_path, 'r') as f:
            label_lines = f.readlines()
        
        annotations = []
        
        for line in label_lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) < 5:  # Минимум: класс и 4 координаты для bbox
                continue
            
            class_id = int(parts[0])
            if class_id >= len(classes):
                continue  # Пропускаем, если индекс класса вне диапазона
            
            class_name = classes[class_id]
            
            # Определяем тип аннотации по количеству координат
            if len(parts) == 5:  # Bounding box (class_id, x_center, y_center, width, height)
                x_center, y_center, width, height = map(float, parts[1:5])
                
                # Преобразуем нормализованные координаты в абсолютные
                x = (x_center - width/2) * img_width
                y = (y_center - height/2) * img_height
                w = width * img_width
                h = height * img_height
                
                # Получаем цвет класса из словаря
                class_color = class_colors.get(class_name)
                class_color_str = class_color.name() if class_color else None
                
                # Создаем прямоугольник
                rect_item = {
                    'type': 'rect',
                    'coords': {
                        'x': x / img_width,  # Нормализованные координаты для AnnotationManager
                        'y': y / img_height,
                        'width': w / img_width,
                        'height': h / img_height
                    },
                    'position': {'x': 0, 'y': 0},
                    'class': {
                        'id': class_name,  # Используем имя класса как ID вместо числового индекса
                        'name': class_name,
                        'color': class_color_str  # Устанавливаем цвет класса
                    }
                }
                
                annotations.append(rect_item)
                
            elif len(parts) > 5 and len(parts) % 2 == 1:  # Полигон (class_id, x1, y1, x2, y2, ...)
                points = []
                for i in range(1, len(parts), 2):
                    if i+1 < len(parts):
                        x = float(parts[i])
                        y = float(parts[i+1])
                        points.append({'x': x, 'y': y})  # Уже нормализованные координаты
                
                # Получаем цвет класса из словаря
                class_color = class_colors.get(class_name)
                class_color_str = class_color.name() if class_color else None
                
                polygon_item = {
                    'type': 'polygon',
                    'points': points,
                    'position': {'x': 0, 'y': 0},
                    'class': {
                        'id': class_name,  # Используем имя класса как ID вместо числового индекса
                        'name': class_name,
                        'color': class_color_str  # Устанавливаем цвет класса
                    }
                }
                
                annotations.append(polygon_item)
        
        # Сохраняем аннотации в AnnotationManager
        if annotations and hasattr(image_viewer, 'annotation_manager'):
            image_viewer.annotation_manager.annotations_by_image[image_path] = annotations 