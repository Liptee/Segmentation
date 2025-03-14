import json


class SegmentationClassManager:
    """
    Менеджер классов сегментации

    Функциональность:
    - Добавление и удаление классов.
    - Присвоение/изменение цвета классов.
    - Добавление описания к классам.
    - Экспорт и импорт меток в/из JSON файла.
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
            
    def import_from_json(self, file_path: str) -> tuple:
        """
        Импортирует классы из JSON файла
        
        Args:
            file_path: путь к JSON файлу
            
        Returns:
            tuple: (количество новых классов, количество обновленных классов)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise ValueError("Неверный формат JSON: ожидается список классов")
            
            imported = 0
            updated = 0
            existing_classes = set(self.classes.keys())
            
            for item in data:
                if not isinstance(item, dict) or 'name' not in item or 'color' not in item:
                    continue
                
                name = item['name']
                color = item['color']
                description = item.get('description', '')
                
                if name in existing_classes:
                    # Обновляем существующий класс
                    self.update_class_color(name, color)
                    self.update_class_description(name, description)
                    updated += 1
                else:
                    # Добавляем новый класс
                    try:
                        self.add_class(name, color, description)
                        imported += 1
                    except ValueError:
                        # Пропускаем классы с дублирующимися именами
                        pass
            
            return imported, updated
            
        except Exception as e:
            raise ValueError(f"Ошибка при импорте классов: {str(e)}")

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
