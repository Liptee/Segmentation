import sys
import json
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QApplication, QMessageBox, QFileDialog, QInputDialog, QDialog, QColorDialog, QDialogButtonBox
)
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor, QIcon, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from core.class_manager import SegmentationClassManager
from logger import logger


class AddClassDialog(QDialog):
    """
    Диалог для создания нового класса.
    Позволяет ввести имя, выбрать цвет через системную палитру и ввести описание.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить новый класс")
        self.selected_color = None  # строка вида "#rrggbb"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.nameEdit = QLineEdit()
        self.nameEdit.setPlaceholderText("Введите название класса")
        layout.addWidget(QLabel("Название:"))
        layout.addWidget(self.nameEdit)

        colorLayout = QHBoxLayout()
        self.colorButton = QPushButton("Выбрать цвет")
        self.colorButton.clicked.connect(self.choose_color)
        self.colorPreview = QLabel()
        self.colorPreview.setFixedSize(30, 30)
        self.colorPreview.setStyleSheet("border: 1px solid gray; border-radius: 15px;")
        colorLayout.addWidget(self.colorButton)
        colorLayout.addWidget(self.colorPreview)
        layout.addLayout(colorLayout)

        self.descEdit = QTextEdit()
        self.descEdit.setPlaceholderText("Введите описание класса")
        layout.addWidget(QLabel("Описание:"))
        layout.addWidget(self.descEdit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.colorPreview.setStyleSheet(
                f"border: 1px solid gray; border-radius: 15px; background-color: {self.selected_color};"
            )

    def get_data(self):
        return (self.nameEdit.text().strip(), self.selected_color, self.descEdit.toPlainText().strip())


class EditClassDialog(QDialog):
    """
    Диалог для редактирования класса.
    Позволяет переименовать класс, выбрать новый цвет через палитру и изменить описание.
    """
    def __init__(self, initial_name, initial_color, initial_desc, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать класс")
        self.selected_color = initial_color
        self.init_ui(initial_name, initial_color, initial_desc)

    def init_ui(self, name, color, desc):
        layout = QVBoxLayout(self)

        self.nameEdit = QLineEdit(name)
        layout.addWidget(QLabel("Новое название:"))
        layout.addWidget(self.nameEdit)

        colorLayout = QHBoxLayout()
        self.colorButton = QPushButton("Выбрать цвет")
        self.colorButton.clicked.connect(self.choose_color)
        self.colorPreview = QLabel()
        self.colorPreview.setFixedSize(30, 30)
        self.colorPreview.setStyleSheet(
            f"border: 1px solid gray; border-radius: 15px; background-color: {color};"
        )
        colorLayout.addWidget(self.colorButton)
        colorLayout.addWidget(self.colorPreview)
        layout.addLayout(colorLayout)

        self.descEdit = QTextEdit(desc)
        layout.addWidget(QLabel("Новое описание:"))
        layout.addWidget(self.descEdit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.colorPreview.setStyleSheet(
                f"border: 1px solid gray; border-radius: 15px; background-color: {self.selected_color};"
            )

    def get_data(self):
        return (self.nameEdit.text().strip(), self.selected_color, self.descEdit.toPlainText().strip())


class MergeClassesDialog(QDialog):
    """
    Диалог для объединения (мерджа) классов.
    Позволяет задать имя целевого класса, выбрать его цвет через палитру и указать описание.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Объединение классов")
        self.selected_color = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.nameEdit = QLineEdit()
        self.nameEdit.setPlaceholderText("Введите имя целевого класса")
        layout.addWidget(QLabel("Имя целевого класса:"))
        layout.addWidget(self.nameEdit)

        colorLayout = QHBoxLayout()
        self.colorButton = QPushButton("Выбрать цвет")
        self.colorButton.clicked.connect(self.choose_color)
        self.colorPreview = QLabel()
        self.colorPreview.setFixedSize(30, 30)
        self.colorPreview.setStyleSheet("border: 1px solid gray; border-radius: 15px;")
        colorLayout.addWidget(self.colorButton)
        colorLayout.addWidget(self.colorPreview)
        layout.addLayout(colorLayout)

        self.descEdit = QTextEdit()
        self.descEdit.setPlaceholderText("Введите описание (опционально)")
        layout.addWidget(QLabel("Описание:"))
        layout.addWidget(self.descEdit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.colorPreview.setStyleSheet(
                f"border: 1px solid gray; border-radius: 15px; background-color: {self.selected_color};"
            )

    def get_data(self):
        return (self.nameEdit.text().strip(), self.selected_color, self.descEdit.toPlainText().strip())


class SegmentationClassManagerWidget(QWidget):
    """
    Графическая обёртка для менеджмента классов сегментации.
    Позволяет добавлять, удалять, объединять классы и экспортировать их в JSON.
    Редактирование класса осуществляется по двойному щелчку на элемент списка.
    """
    # Сигнал, который отправляется при изменении класса
    # (old_name, new_name, new_color)
    classUpdated = pyqtSignal(str, str, str)
    
    # Сигнал, который отправляется при удалении класса
    # (name)
    classRemoved = pyqtSignal(str)
    
    # Сигнал, который отправляется при объединении классов
    # (list_of_names, target_name, target_color)
    classesMerged = pyqtSignal(list, str, str)
    
    # Сигнал, информирующий об изменениях в классах (для обновления UI)
    classesChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = SegmentationClassManager()
        self.setAcceptDrops(True)  # Разрешаем Drag & Drop
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Добавим хинт о возможности перетаскивания JSON файла
        drag_hint = QLabel("Перетащите JSON-файл для импорта классов")
        drag_hint.setAlignment(Qt.AlignCenter)
        drag_hint.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(drag_hint)

        self.classListWidget = QListWidget()
        self.classListWidget.setSelectionMode(QListWidget.ExtendedSelection)
        main_layout.addWidget(QLabel("Список классов:"))
        main_layout.addWidget(self.classListWidget)

        # При двойном щелчке открываем диалог редактирования
        self.classListWidget.itemDoubleClicked.connect(self.editClass)

        btnLayout = QHBoxLayout()
        self.addButton = QPushButton("+")
        self.addButton.clicked.connect(self.openAddClassDialog)
        btnLayout.addWidget(self.addButton)

        self.removeButton = QPushButton("-")
        self.removeButton.clicked.connect(self.removeSelected)
        btnLayout.addWidget(self.removeButton)

        self.mergeButton = QPushButton("Объединить")
        self.mergeButton.clicked.connect(self.mergeSelected)
        btnLayout.addWidget(self.mergeButton)

        # Кнопки экспорта и импорта
        btnImportExportLayout = QHBoxLayout()
        self.exportButton = QPushButton("Экспорт в JSON")
        self.exportButton.clicked.connect(self.exportToJson)
        btnImportExportLayout.addWidget(self.exportButton)
        
        self.importButton = QPushButton("Импорт из JSON")
        self.importButton.clicked.connect(self.importFromJson)
        btnImportExportLayout.addWidget(self.importButton)

        main_layout.addLayout(btnLayout)
        main_layout.addLayout(btnImportExportLayout)

        self.setLayout(main_layout)
        self.setWindowTitle("Менеджер классов сегментации")
        self.resize(600, 400)
        self.refreshList()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработка события перетаскивания файла над виджетом"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # Проверяем, что перетаскивается только один файл и это JSON
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.json'):
                event.acceptProposedAction()
                return
        # По умолчанию отклоняем
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Обработка события сброса файла на виджет"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.json'):
                self.importJsonClasses(file_path)
                event.acceptProposedAction()
            else:
                QMessageBox.warning(self, "Ошибка", "Поддерживаются только JSON файлы.")
                event.ignore()

    def importFromJson(self):
        """Импорт классов из JSON файла через диалог выбора файла"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Импорт классов из JSON", "", "JSON файлы (*.json)")
        if file_path:
            self.importJsonClasses(file_path)
    
    def importJsonClasses(self, file_path):
        """Импорт классов из JSON файла"""
        try:
            # Используем метод import_from_json из SegmentationClassManager
            imported_classes, updated_classes = self.manager.import_from_json(file_path)
            
            # Для каждого обновленного класса нужно отправить сигнал об обновлении
            # Но мы не знаем, какие именно классы были обновлены, так что
            # просто инициируем общий сигнал об изменениях
            if imported_classes > 0 or updated_classes > 0:
                # Обновляем список и уведомляем об изменениях
                self.refreshList()
                self.classesChanged.emit()
            
            # Показываем сообщение об успешном импорте
            if imported_classes > 0 or updated_classes > 0:
                message = f"Импортировано {imported_classes} новых и обновлено {updated_classes} существующих классов из {file_path}"
                QMessageBox.information(self, "Импорт завершен", message)
            else:
                QMessageBox.information(self, "Импорт завершен", "Нет новых классов для импорта")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка при импорте", f"Не удалось импортировать классы: {str(e)}")
            logger.error(f"Ошибка при импорте классов: {str(e)}")

    def refreshList(self):
        self.classListWidget.clear()
        for cls in self.manager.classes.values():
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            brush = QBrush(QColor(cls['color']))
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 20, 20)
            painter.end()

            itemText = f"{cls['name']} | {cls['description']}"
            item = QListWidgetItem(itemText)
            item.setData(Qt.UserRole, cls['name'])
            item.setIcon(QIcon(pixmap))
            self.classListWidget.addItem(item)

    def openAddClassDialog(self):
        dialog = AddClassDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, color, description = dialog.get_data()
            if not name or not color:
                QMessageBox.warning(self, "Ошибка", "Необходимо указать название и выбрать цвет")
                return
            try:
                self.manager.add_class(name, color, description)
                self.refreshList()
                # Отправляем сигнал об изменении списка классов
                self.classesChanged.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def editClass(self, item):
        name = item.data(Qt.UserRole)
        cls = self.manager.classes.get(name)
        if not cls:
            return
        dialog = EditClassDialog(cls['name'], cls['color'], cls['description'], self)
        if dialog.exec_() == QDialog.Accepted:
            new_name, new_color, new_desc = dialog.get_data()
            # Если имя изменилось, добавляем новый класс и удаляем старый
            if new_name != name:
                try:
                    self.manager.add_class(new_name, new_color, new_desc)
                    self.manager.remove_class(name)
                    # Отправляем сигнал об обновлении класса в аннотациях
                    self.classUpdated.emit(name, new_name, new_color)
                except ValueError as e:
                    QMessageBox.warning(self, "Ошибка", str(e))
                    return
            else:
                try:
                    old_color = self.manager.classes[name]['color']
                    self.manager.update_class_color(name, new_color)
                    self.manager.update_class_description(name, new_desc)
                    # Отправляем сигнал об обновлении цвета класса
                    if old_color != new_color:
                        self.classUpdated.emit(name, name, new_color)
                except ValueError as e:
                    QMessageBox.warning(self, "Ошибка", str(e))
                    return
            self.refreshList()
            # Отправляем сигнал об изменении списка классов
            self.classesChanged.emit()

    def removeSelected(self):
        selectedItems = self.classListWidget.selectedItems()
        if not selectedItems:
            QMessageBox.warning(self, "Ошибка", "Выберите класс для удаления")
            return
        
        # Получаем основное окно для доступа к annotation_manager
        main_window = self.get_main_window()
        if not main_window or not hasattr(main_window, 'image_viewer') or not hasattr(main_window.image_viewer, 'annotation_manager'):
            QMessageBox.warning(self, "Ошибка", "Не удалось получить доступ к менеджеру аннотаций")
            return
        
        annotation_manager = main_window.image_viewer.annotation_manager
        
        for item in selectedItems:
            name = item.data(Qt.UserRole)
            
            # Проверяем, используется ли этот класс в аннотациях
            count, affected_images = annotation_manager.count_annotations_by_class(name)
            
            if count > 0:
                # Спрашиваем подтверждение пользователя перед удалением класса
                message = f"Класс '{name}' используется в {count} аннотациях на {len(affected_images)} изображениях.\n"
                message += "При удалении класса все эти аннотации будут помечены как 'без класса'.\n\n"
                message += "Вы уверены, что хотите удалить этот класс?"
                
                reply = QMessageBox.question(self, "Подтверждение удаления", 
                                             message, 
                                             QMessageBox.Yes | QMessageBox.No, 
                                             QMessageBox.No)
                
                if reply == QMessageBox.No:
                    continue
                
                # Обновляем аннотации перед удалением класса
                annotation_manager.remove_class(name)
                # Отправляем сигнал об удалении класса
                self.classRemoved.emit(name)
            
            try:
                self.manager.remove_class(name)
            except ValueError as e:
                QMessageBox.warning(self, "Ошибка", str(e))
        
        self.refreshList()
        # Отправляем сигнал об изменении списка классов
        self.classesChanged.emit()

    def mergeSelected(self):
        selectedItems = self.classListWidget.selectedItems()
        if len(selectedItems) < 2:
            QMessageBox.warning(self, "Ошибка", "Выберите минимум 2 класса для объединения")
            return
        classNames = [item.data(Qt.UserRole) for item in selectedItems]
        dialog = MergeClassesDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            target_name, target_color, target_desc = dialog.get_data()
            if not target_name or not target_color:
                QMessageBox.warning(self, "Ошибка", "Необходимо указать имя и выбрать цвет для целевого класса")
                return
            try:
                self.manager.merge_classes(classNames, target_name,
                                          target_color=target_color,
                                          target_description=target_desc)
                
                # Отправляем сигнал об объединении классов
                self.classesMerged.emit(classNames, target_name, target_color)
                
                self.refreshList()
                # Отправляем сигнал об изменении списка классов
                self.classesChanged.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def exportToJson(self):
        filePath, _ = QFileDialog.getSaveFileName(self, "Экспорт классов в JSON", "", "JSON файлы (*.json)")
        if filePath:
            self.manager.export_to_json(filePath)
            QMessageBox.information(self, "Экспорт", f"Классы успешно экспортированы в {filePath}")

    def get_all_classes(self):
        """
        Returns a list of all segmentation classes with their attributes.
        This method is used by the ObjectLabelerWidget to display and assign classes.
        """
        classes_list = []
        for name, cls in self.manager.classes.items():
            # Create a copy of the class dictionary and add an 'id' field using the name
            class_data = cls.copy()
            class_data['id'] = name  # Use the name as the unique identifier
            classes_list.append(class_data)
        
        logger.info(f"ClassManager: get_all_classes: возвращаю {len(classes_list)} классов")
        for i, cls in enumerate(classes_list):
            logger.info(f"ClassManager: Класс {i+1}: {cls.get('name')}, ID={cls.get('id')}, цвет={cls.get('color')}")
        
        return classes_list

    def get_main_window(self):
        """Получает ссылку на главное окно приложения"""
        parent = self.parent()
        while parent is not None:
            # Проверяем, имеет ли родитель атрибуты, характерные для главного окна
            if hasattr(parent, 'image_viewer') and hasattr(parent, 'media_importer'):
                return parent
            parent = parent.parent()
        return None
