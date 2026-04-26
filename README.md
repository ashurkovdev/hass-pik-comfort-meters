# PIK Comfort Meters — интеграция для Home Assistant

[![Validate with hassfest](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hassfest.yaml/badge.svg?branch=main)](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hassfest.yaml)
[![HACS Action](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hacs.yaml/badge.svg?branch=main)](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hacs.yaml)

Интеграция подключается к личному кабинету PIK Comfort, собирает ранее переданные показания и позволяет отправлять новые через Home Assistant.

## Возможности

- Автоматическое получение показаний со всех счётчиков в аккаунте
- Поддержка однотарифных, двухтарифных и трёхтарифных счётчиков
- Поддержка воды (горячая/холодная) и электроэнергии
- Отправка новых показаний через сервис
- Мониторинг ошибок обновления и отправки
- Автоматическое повторное подключение при обрыве соединения
- Exponential backoff для стабильности работы
- Локализация на русском и английском языках

## Установка

### Через HACS (рекомендуется)

1. Откройте HACS в Home Assistant
2. Нажмите "Integrations" → три точки в правом верхнем углу → "Custom repositories"
3. Добавьте репозиторий: `https://github.com/ashurkovdev/hass-pik-comfort-meters`
4. Выберите категорию "Integrations"
5. Найдите "PIK Comfort Meters" и нажмите "Download"
6. Перезапустите Home Assistant

### Вручную

1. Скопируйте папку `custom_components/pik_comfort_meters` в папку `custom_components` вашего Home Assistant
2. Перезапустите Home Assistant
3. Перейдите в `Настройки` → `Интеграции` и добавьте интеграцию "PIK Comfort Meters"

## Настройка интеграции (UI)

При добавлении интеграции потребуется ввести:

| Параметр | Описание |
|----------|----------|
| **Phone number** | Номер телефона, привязанный к аккаунту PIK Comfort |
| **Password** | Пароль от личного кабинета |
| **Update interval** | Интервал обновления данных в секундах (по умолчанию 21600 = 6 часов, диапазон: 3600-86400) |

### Изменение настроек

После добавления интеграции можно изменить интервал обновления через меню интеграции:
1. Откройте интеграцию "PIK Comfort Meters"
2. Нажмите "Настроить" (Options)
3. Измените интервал обновления
4. Сохраните

## Сущности

### Сенсоры с показаниями (sensor)

Для каждого счётчика создаётся устройство. Пример имени устройства: `PIK meter: hot_water (250314753)`.

#### Типы сенсоров

Для каждого тарифа создаются следующие сенсоры:

| Сенсор | Описание | Единицы измерения |
|--------|----------|-------------------|
| **Accounted** | Учтенные показания (последнее подтверждённое значение) | m³ / kWh |
| **Submitted** | Переданные показания (значение, отправленное пользователем) | m³ / kWh |
| **Monthly Consumption** | Потребление за текущий месяц | m³ / kWh |
| **Last Updated** | Дата последнего обновления показаний | timestamp |
| **Created** | Дата создания показаний | timestamp |

#### Правила формирования unique_id и entity_id

- **Однотарифный счётчик** (factory 250314753):
  - `unique_id`: `pik_comfort_meters_250314753`
  - `entity_id`: `sensor.pik_comfort_meters_250314753`
  - `name`: `PIK meter: hot_water (250314753)`

- **Двухтарифный счётчик** (factory 250314753), тариф 1:
  - `unique_id`: `pik_comfort_meters_250314753_t1`
  - `entity_id`: `sensor.pik_comfort_meters_250314753_t1`
  - `name`: `PIK meter: hot_water (250314753) (Day)`

#### Обозначения тарифов

| Количество тарифов | Тариф 1 | Тариф 2 | Тариф 3 |
|-------------------|---------|---------|---------|
| 2 тарифа | (Day) | (Night) | — |
| 3 тарифа | (Day) | (Night) | (Morning & Evening) |

### Сенсоры ошибок (binary_sensor)

Создаётся отдельное устройство "PIK Comfort Meters Monitoring" для мониторинга:

| Сенсор | Описание | Атрибуты |
|--------|----------|----------|
| **Update Error** | Ошибка обновления данных | `last_attempt`, `last_success`, `last_error_message` |
| **Submit Error** | Ошибка отправки показаний | `last_attempt`, `last_success`, `last_error_message` |

## Сервисы

### pik_comfort_meters.submit_reading

Отправляет показания счётчика.

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `device_id` | string | да | Идентификатор устройства из Device Registry |

#### Пример вызова

```yaml
service: pik_comfort_meters.submit_reading
data:
  device_id: "1234567890abcdef"  # замените на реальный device_id
```

## Примеры автоматизаций

### Отправка показаний по расписанию

Пример: отправлять показания 15-го числа каждого месяца в 12:00

```yaml
alias: PIK — Отправлять показания 15-го числа
description: Отправляет показания выбранного устройства PIK Comfort каждый месяц
trigger:
  - platform: time
    at: '12:00:00'
condition:
  - condition: template
    value_template: "{{ now().day == 15 }}"
action:
  - service: pik_comfort_meters.submit_reading
    data:
      device_id: "1234567890abcdef"  # замените на реальный device_id
mode: single
```

### Уведомление в Telegram при ошибке

Отправляет сообщение в Telegram, когда бинарный сенсор ошибки становится `on`.

```yaml
alias: PIK — Уведомление в Telegram при ошибке интеграции
description: Отправляет сообщение в Telegram при срабатывании бинарного сенсора ошибки
trigger:
  - platform: state
    entity_id:
      - binary_sensor.pik_comfort_meters_monitoring_update_error
      - binary_sensor.pik_comfort_meters_monitoring_submit_error
    to: 'on'
action:
  - service: notify.telegram
    data:
      message: >-
        PIK Comfort: обнаружена ошибка ({{ trigger.to_state.name }}).
        Последнее сообщение об ошибке: {{ state_attr(trigger.entity_id, 'last_error_message') or 'нет данных' }}
mode: single
```

## Ошибки и сообщения конфигурации

| Код ошибки | Описание | Решение |
|------------|----------|---------|
| `auth_failed` | Неверные учётные данные | Проверьте телефон и пароль |
| `no_accounts` | У аккаунта не найдено счётчиков | Убедитесь, что в аккаунте PIK Comfort есть привязанные счётчики |
| `unknown` | Неизвестная ошибка | Проверьте логи Home Assistant |
| `already_configured` | Аккаунт уже настроен | Интеграция поддерживает только один аккаунт |

## Логирование и отладка

Чтобы включить подробное логирование для интеграции, добавьте в `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.pik_comfort_meters: debug
```

Перезапустите Home Assistant и смотрите системные логи.

## Частые вопросы / FAQ

### Сенсоры не появляются после добавления интеграции

1. Убедитесь, что аутентификация успешна (проверьте логи)
2. Проверьте, что у аккаунта есть привязанные счётчики in the PIK Comfort personal account
3. Убедитесь, что телефон и пароль введены правильно

### Сервис submit_reading возвращает ошибку

1. Проверьте атрибуты бинарного сенсора `Submit Error`
2. Посмотрите логи Home Assistant
3. Убедитесь, что выбран правильный `device_id`

### Как обновить показания вручную?

1. Перейдите в Developer Tools → Services
2. Выберите сервис `pik_comfort_meters.submit_reading`
3. Укажите `device_id` нужного устройства
4. Нажмите "Call Service"

### Можно ли использовать несколько аккаунтов?

В текущей версии интеграция поддерживает только один аккаунт PIK Comfort.

## Поддержка

- Ошибки и фича-реквесты: https://github.com/ashurkovdev/hass-pik-comfort-meters/issues
- Обсуждение: https://github.com/ashurkovdev/hass-pik-comfort-meters/discussions
- PR и предложения по улучшению приветствуются!

## Лицензия

MIT License