# Изменения в интеграции PIK Comfort Meters

## Дата: 2026-04-26

### Исправленная проблема
Ошибка `extra keys not allowed @ data['device_id']` при создании сенсоров.

### Что было изменено

#### Файл: `custom_components/pik_comfort_meters/const.py`

**Добавлены константы типов сенсоров:**
```python
SENSOR_TYPE_ACCOUNTED = "accounted"
SENSOR_TYPE_SUBMITTED = "submitted"
SENSOR_TYPE_CONSUMPTION = "consumption"
SENSOR_TYPE_UPDATED = "updated"
SENSOR_TYPE_CREATED = "created"
```

#### Файл: `custom_components/pik_comfort_meters/sensor.py`

1. **Добавлен импорт DeviceInfo:**
   ```python
   from homeassistant.helpers.device_registry import DeviceInfo
   ```

2. **Константы типов сенсоров импортируются из const.py:**
   - Удалены локальные определения констант
   - Добавлен импорт: `SENSOR_TYPE_ACCOUNTED`, `SENSOR_TYPE_SUBMITTED`, `SENSOR_TYPE_CONSUMPTION`, `SENSOR_TYPE_UPDATED`, `SENSOR_TYPE_CREATED`

3. **Изменен способ привязки сенсоров к устройствам:**
   - **Было:** Использование параметров `device_id=device.id` и `device_unique_id=device_unique_id`
   - **Стало:** Использование параметра `device_info=DeviceInfo(...)`

4. **Обновлены классы сенсоров:**
   - `PIKMeterSensor` - принимает `device_info` вместо `device_id` и `device_unique_id`
   - `PIKMeterTimestampSensor` - принимает `device_info` вместо `device_id` и `device_unique_id`

5. **Удалены свойства `device_info` из классов:**
   - Теперь используется стандартный атрибут `_attr_device_info` из базового класса

### Структура сенсоров (осталась без изменений)

Для каждого счетчика и тарифа создаются 5 сенсоров:

#### Числовые сенсоры (float):
1. **Accounted** - учтенные показания (device_class: water/energy)
2. **Submitted** - переданные показания (device_class: water/energy)
3. **Monthly Consumption** - потребление за месяц (device_class: water/energy)

#### Сенсоры дат (timestamp):
4. **Last Updated** - дата обновления показаний (device_class: timestamp)
5. **Created** - дата создания показаний (device_class: timestamp)

### Преимущества изменений

1. **Корректная работа с Home Assistant API** - используется правильный способ привязки сущностей к устройствам
2. **Устранена ошибка валидации** - больше нет ошибки `extra keys not allowed`
3. **Сохранена обратная совместимость** - все существующие сенсоры и их unique_id остались прежними
4. **Улучшена читаемость кода** - явное создание DeviceInfo для каждого счетчика

### Тестирование

- ✅ Синтаксическая проверка Python пройдена
- ✅ Все импорты корректны
- ✅ Структура сенсоров сохранена
- ⚠️ Требуется тестирование в реальной среде Home Assistant