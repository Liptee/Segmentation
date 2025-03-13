import json
import os
from PyQt5.QtCore import QRectF, QPointF
from gui.annotation_items import SelectableRectItem, SelectablePolygonItem  # Импортируйте нужные классы
from logger import logger

class AnnotationManager:
    def __init__(self):
        # Словарь, где ключ – путь к изображению, значение – нормализованные данные аннотаций
        self.annotations_by_image = {}

    def save_annotations(self, current_image_path, annotations, normalize_rect, normalize_points):
        logger.info(f"AnnotationManager.save_annotations: Сохраняю {len(annotations)} аннотаций для {current_image_path}")
        
        normalized_annotations = []
        for i, annotation in enumerate(annotations):
            if isinstance(annotation, SelectableRectItem):
                rect = annotation.rect()
                pos = annotation.pos()
                logger.info(f"  Аннотация {i}: Прямоугольник, позиция: {pos}, размер: {rect.size()}")
                
                # Получаем нормализованные координаты
                norm_rect = normalize_rect(rect)
                logger.info(f"    Нормализованный прямоугольник: {norm_rect}")
                
                class_data = {
                    'id': annotation.class_id,
                    'name': annotation.class_name,
                    'color': annotation.class_color.name() if annotation.class_color else None
                }
                normalized_annotations.append({
                    'type': 'rect',
                    'coords': {
                        'x': norm_rect.x(),
                        'y': norm_rect.y(),
                        'width': norm_rect.width(),
                        'height': norm_rect.height()
                    },
                    'position': {
                        'x': pos.x(),
                        'y': pos.y()
                    },
                    'class': class_data
                })
            elif isinstance(annotation, SelectablePolygonItem):
                pos = annotation.pos()
                points = [annotation.polygon().at(i) for i in range(annotation.polygon().count())]
                logger.info(f"  Аннотация {i}: Полигон, позиция: {pos}, точек: {len(points)}")
                
                # Получаем нормализованные точки
                norm_points = normalize_points(points)
                logger.info(f"    Первая нормализованная точка: {norm_points[0] if norm_points else 'нет точек'}")
                
                norm_points_data = [{'x': p.x(), 'y': p.y()} for p in norm_points]
                class_data = {
                    'id': annotation.class_id,
                    'name': annotation.class_name,
                    'color': annotation.class_color.name() if annotation.class_color else None
                }
                normalized_annotations.append({
                    'type': 'polygon',
                    'points': norm_points_data,
                    'position': {
                        'x': pos.x(),
                        'y': pos.y()
                    },
                    'class': class_data
                })
        
        # Сохраняем нормализованные аннотации
        self.annotations_by_image[current_image_path] = normalized_annotations
        logger.info(f"AnnotationManager.save_annotations: Сохранено {len(normalized_annotations)} аннотаций")

    def load_annotations(self, image_path, denormalize_rect, denormalize_points):
        if image_path not in self.annotations_by_image:
            return []
        
        logger.info(f"AnnotationManager.load_annotations: Загружаю аннотации для {image_path}")
        normalized_annotations = self.annotations_by_image[image_path]
        loaded_items = []
        
        for i, data in enumerate(normalized_annotations):
            if data['type'] == 'rect':
                coords = data['coords']
                norm_rect = QRectF(coords['x'], coords['y'], coords['width'], coords['height'])
                rect = denormalize_rect(norm_rect)
                
                # Создаем прямоугольник
                rect_item = SelectableRectItem(rect.x(), rect.y(), rect.width(), rect.height(), None, None)
                
                # Устанавливаем позицию, если она есть
                if 'position' in data:
                    pos = data['position']
                    rect_item.setPos(pos['x'], pos['y'])
                    logger.info(f"  Загружена аннотация {i}: Прямоугольник, установлена позиция: {pos['x']}, {pos['y']}")
                
                if data.get('class'):
                    rect_item.set_class(data['class'])
                
                loaded_items.append(rect_item)
                
            elif data['type'] == 'polygon':
                norm_points_data = data['points']
                norm_points = [QPointF(p['x'], p['y']) for p in norm_points_data]
                points = denormalize_points(norm_points)
                
                # Создаем полигон
                polygon_item = SelectablePolygonItem(points, None, None)
                
                # Устанавливаем позицию, если она есть
                if 'position' in data:
                    pos = data['position']
                    polygon_item.setPos(pos['x'], pos['y'])
                    logger.info(f"  Загружена аннотация {i}: Полигон, установлена позиция: {pos['x']}, {pos['y']}")
                
                if data.get('class'):
                    polygon_item.set_class(data['class'])
                
                loaded_items.append(polygon_item)
        
        logger.info(f"AnnotationManager.load_annotations: Загружено {len(loaded_items)} аннотаций")
        return loaded_items

    def export_to_json(self, output_file):
        # При экспорте можно преобразовывать абсолютные пути к изображениям в относительные
        base_dir = os.path.dirname(output_file)
        data = {
            'version': '1.0',
            'images': {}
        }
        for img_path, annotations in self.annotations_by_image.items():
            try:
                rel_path = os.path.relpath(img_path, base_dir)
            except Exception:
                rel_path = img_path
            data['images'][rel_path] = annotations

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Экспортированы аннотации для {len(self.annotations_by_image)} изображений в {output_file}")

    def import_from_json(self, input_file):
        self.annotations_by_image.clear()
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('version') != '1.0':
                print(f"Предупреждение: неизвестная версия формата аннотаций: {data.get('version', 'неизвестна')}")
            if 'images' in data and isinstance(data['images'], dict):
                base_dir = os.path.dirname(input_file)
                for rel_path, annotations in data['images'].items():
                    if not os.path.isabs(rel_path):
                        abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
                    else:
                        abs_path = rel_path
                    self.annotations_by_image[abs_path] = annotations
                print(f"Импортированы аннотации для {len(self.annotations_by_image)} изображений из {input_file}")
                return True
        except Exception as e:
            print(f"Ошибка при импорте аннотаций: {str(e)}")
        return False