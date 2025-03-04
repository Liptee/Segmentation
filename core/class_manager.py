import json


class SegmentationClassManager:
    """
    Менеджер классов сегментации

    Функциональность:
    - Добавление и удаление классов.
    - Присвоение/изменение цвета классов.
    - Добавление описания к классам.
    - Экспорт меток в JSON файл.
    - Слияние (мердж) классов.
    """
    def __init__(self):
        # Хранение классов в виде словаря:
        # ключ – имя класса, значение – словарь с атрибутами: color и description.
        self.classes = {}

    def add_class(self, name: str, color: str, description: str = "") -> None:
        if not name:
            raise ValueError("Имя класса не может быть пустым (Class name cannot be empty).")
        if name in self.classes:
            raise ValueError(f"Класс '{name}' уже существует (Class '{name}' already exists).")
        self.classes[name] = {
            'name': name,
            'color': color,
            'description': description
        }

    def remove_class(self, name: str) -> None:
        if name not in self.classes:
            raise ValueError(f"Класс '{name}' не существует (Class '{name}' does not exist).")
        del self.classes[name]

    def update_class_color(self, name: str, new_color: str) -> None:
        if name not in self.classes:
            raise ValueError(f"Класс '{name}' не существует (Class '{name}' does not exist).")
        self.classes[name]['color'] = new_color

    def update_class_description(self, name: str, description: str) -> None:
        if name not in self.classes:
            raise ValueError(f"Класс '{name}' не существует (Class '{name}' does not exist).")
        self.classes[name]['description'] = description

    def export_to_json(self, file_path: str) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(list(self.classes.values()), f, ensure_ascii=False, indent=4)

    def merge_classes(self, class_names: list, target_class_name: str,
                      target_color: str = None, target_description: str = None) -> None:
        if not class_names:
            raise ValueError("Список классов для мерджа пуст (List of classes to merge is empty).")
        for name in class_names:
            if name not in self.classes:
                raise ValueError(f"Класс '{name}' не существует (Class '{name}' does not exist) и не может быть объединён.")
        # Если целевой класс уже существует, обновляем его параметры
        if target_class_name in self.classes:
            if target_color is not None:
                self.classes[target_class_name]['color'] = target_color
            if target_description is not None:
                self.classes[target_class_name]['description'] = target_description
        else:
            self.classes[target_class_name] = {
                'name': target_class_name,
                'color': target_color if target_color is not None else "#000000",
                'description': target_description if target_description is not None else ""
            }
        # Удаляем все классы из списка, кроме целевого
        for name in class_names:
            if name != target_class_name and name in self.classes:
                self.remove_class(name)
