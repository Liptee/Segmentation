import unittest
import tempfile
import os
import json

from PyQt5.QtWidgets import QApplication, QDialog, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

# Импортируем наш виджет и диалоги
from gui.class_manager import (
    SegmentationClassManagerWidget,
    AddClassDialog,
    EditClassDialog,
    MergeClassesDialog
)

# Создаем экземпляр QApplication, если он еще не создан
app = QApplication.instance()
if app is None:
    app = QApplication([])

# Фиктивный диалог для добавления класса
class FakeAddClassDialog(AddClassDialog):
    def exec_(self):
        return QDialog.Accepted
    def get_data(self):
        # Возвращаем тестовые данные: имя, цвет (через палитру) и описание
        return ("TestClass", "#ff0000", "Test description")

# Фиктивный диалог для редактирования класса
class FakeEditClassDialog(EditClassDialog):
    def exec_(self):
        return QDialog.Accepted
    def get_data(self):
        # Изменим имя, цвет и описание
        return ("EditedClass", "#00ff00", "Edited description")

# Фиктивный диалог для объединения классов
class FakeMergeClassesDialog(MergeClassesDialog):
    def exec_(self):
        return QDialog.Accepted
    def get_data(self):
        return ("MergedClass", "#0000ff", "Merged description")

class TestSegmentationClassManagerWidget(unittest.TestCase):
    def setUp(self):
        # Создаем экземпляр виджета
        self.widget = SegmentationClassManagerWidget()
        # Очищаем менеджер для тестов
        self.widget.manager.classes = {}
        self.widget.refreshList()

    def test_add_class_dialog(self):
        # Monkey-patch AddClassDialog
        from gui.class_manager import AddClassDialog as OriginalAddClassDialog
        from gui.class_manager import AddClassDialog
        try:
            # Подменяем класс диалога на фиктивный
            import gui.class_manager as cm
            cm.AddClassDialog = FakeAddClassDialog

            # Вызываем метод добавления класса
            self.widget.openAddClassDialog()

            # Проверяем, что класс был добавлен
            self.assertIn("TestClass", self.widget.manager.classes)
            cls = self.widget.manager.classes["TestClass"]
            self.assertEqual(cls['color'], "#ff0000")
            self.assertEqual(cls['description'], "Test description")
            # Проверяем, что список обновился
            self.assertEqual(self.widget.classListWidget.count(), 1)
        finally:
            # Восстанавливаем оригинальный класс диалога
            cm.AddClassDialog = OriginalAddClassDialog

    def test_edit_class_dialog(self):
        # Сначала добавляем класс вручную
        self.widget.manager.add_class("TestClass", "#ff0000", "Test description")
        self.widget.refreshList()
        # Создаем фиктивный QListWidgetItem, как если бы пользователь выбрал класс
        item = QListWidgetItem("TestClass | Test description")
        item.setData(Qt.UserRole, "TestClass")
        # Monkey-patch EditClassDialog
        from gui.class_manager import EditClassDialog as OriginalEditClassDialog
        from gui.class_manager import EditClassDialog
        try:
            import gui.class_manager as cm
            cm.EditClassDialog = FakeEditClassDialog

            # Вызываем редактирование через метод виджета
            self.widget.editClass(item)

            # После редактирования имя должно измениться на "EditedClass"
            self.assertNotIn("TestClass", self.widget.manager.classes)
            self.assertIn("EditedClass", self.widget.manager.classes)
            cls = self.widget.manager.classes["EditedClass"]
            self.assertEqual(cls['color'], "#00ff00")
            self.assertEqual(cls['description'], "Edited description")
        finally:
            cm.EditClassDialog = OriginalEditClassDialog

    def test_remove_selected(self):
        # Добавляем два класса
        self.widget.manager.add_class("Class1", "#ff0000", "Desc1")
        self.widget.manager.add_class("Class2", "#00ff00", "Desc2")
        self.widget.refreshList()
        # Выбираем один класс для удаления
        items = self.widget.classListWidget.findItems("Class1 | Desc1", Qt.MatchContains)
        self.assertTrue(len(items) > 0)
        item = items[0]
        item.setSelected(True)
        self.widget.removeSelected()
        # Проверяем, что "Class1" удален, а "Class2" остался
        self.assertNotIn("Class1", self.widget.manager.classes)
        self.assertIn("Class2", self.widget.manager.classes)
        self.assertEqual(self.widget.classListWidget.count(), 1)

    def test_merge_selected(self):
        # Добавляем 3 класса
        self.widget.manager.add_class("Class1", "#ff0000", "Desc1")
        self.widget.manager.add_class("Class2", "#00ff00", "Desc2")
        self.widget.manager.add_class("Class3", "#0000ff", "Desc3")
        self.widget.refreshList()

        # Выбираем два класса для объединения
        list_widget = self.widget.classListWidget
        # Отмечаем первые два
        for i in range(2):
            list_widget.item(i).setSelected(True)
        # Monkey-patch MergeClassesDialog
        from gui.class_manager import MergeClassesDialog as OriginalMergeClassesDialog
        from gui.class_manager import MergeClassesDialog
        try:
            import gui.class_manager as cm
            cm.MergeClassesDialog = FakeMergeClassesDialog

            # Вызываем объединение
            self.widget.mergeSelected()

            # В результате, "Class1" и "Class2" должны быть объединены в "MergedClass"
            self.assertNotIn("Class1", self.widget.manager.classes)
            self.assertNotIn("Class2", self.widget.manager.classes)
            self.assertIn("MergedClass", self.widget.manager.classes)
            cls = self.widget.manager.classes["MergedClass"]
            self.assertEqual(cls['color'], "#0000ff")
            self.assertEqual(cls['description'], "Merged description")
            # Количество классов должно уменьшиться
            self.assertEqual(len(self.widget.manager.classes), 2)
        finally:
            cm.MergeClassesDialog = OriginalMergeClassesDialog

    def test_export_to_json(self):
        # Добавляем несколько классов
        self.widget.manager.add_class("Class1", "#ff0000", "Desc1")
        self.widget.manager.add_class("Class2", "#00ff00", "Desc2")
        # Создаем временный файл для экспорта
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        temp_file.close()
        # Monkey-patch QFileDialog.getSaveFileName, чтобы вернуть путь к temp_file
        from PyQt5.QtWidgets import QFileDialog
        original_getSaveFileName = QFileDialog.getSaveFileName
        QFileDialog.getSaveFileName = lambda *args, **kwargs: (temp_file.name, "JSON файлы (*.json)")
        try:
            self.widget.exportToJson()
            # Проверяем, что файл создан и содержит правильный JSON
            with open(temp_file.name, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 2)
            names = [d['name'] for d in data]
            self.assertIn("Class1", names)
            self.assertIn("Class2", names)
        finally:
            QFileDialog.getSaveFileName = original_getSaveFileName
            os.unlink(temp_file.name)

if __name__ == '__main__':
    unittest.main()
