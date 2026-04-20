# PIK Comfort Meters — интеграция для Home Assistant

[![Validate with hassfest](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hassfest.yaml/badge.svg?branch=main)](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hassfest.yaml)
[![HACS Action](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hacs.yaml/badge.svg?branch=main)](https://github.com/ashurkovdev/hass-pik-comfort-meters/actions/workflows/hacs.yaml)

Интеграция подключается к личному кабинету PIK Comfort, собирает ранее переданные показания и позволяет отправлять новые через Home Assistant.

## Установка

- Через HACS _(рекомендуется, если доступно в HACS)_: добавьте репозиторий как "Custom repository" → Integrations, установите и перезагрузите Home Assistant.
- Вручную:
  1. Скопируйте папку `custom_components/pik_comfort_meters` в папку `custom_components` вашего Home Assistant.
  2. Перезапустите Home Assistant.
  3. Перейдите в `Настройки` → `Интеграции` и добавьте интеграцию "PIK Comfort Meters".

## Настройка интеграции (UI)

- `phone` — телефон (логин).
- `password` — пароль от личного кабинета.
- `update_interval` — интервал обновления в секундах (по умолчанию `21600` = 6 часов). Допустимый диапазон: `3600`..`86400`.

После добавления интеграции можно изменить `update_interval` через её настройки.

## Сущности

### Сенсоры с показаниями (sensor)

- Для каждого счётчика создаётся устройство. Пример имени устройства: `PIK Горячая вода 250314753`.
- Правила формирования уникальных идентификаторов (`unique_id`) и `entity_id`:
  - Если у счётчика только один тариф, `unique_id` формируется как `pik_comfort_meters_{factory_number}` и итоговый `entity_id` будет `sensor.pik_comfort_meters_{factory_number}`.
  - Если у счётчика несколько тарифов, `unique_id` формируется как `pik_comfort_meters_{factory_number}_t{tariff_type}` и итоговый `entity_id` будет `sensor.pik_comfort_meters_{factory_number}_t{tariff_type}` (например `sensor.pik_comfort_meters_250314753_t1`).
- Правила отображаемых имён сенсоров:
  - Если только один тариф — в имени не добавляется пометка о тарифе (имя совпадает с именем устройства).
  - Если два тарифа — для тарифов используются замены: тариф 1 → `(День)`, тариф 2 → `(Ночь)`.
  - Если три тарифа — тариф 1 → `(День)`, тариф 2 → `(Ночь)`, тариф 3 → `Утро и вечер`.
  - Для прочих нестандартных тарифов используется `тариф N`.
- Единицы измерения: `m³` для воды, `kWh` для электроэнергии.

Примеры:

- Однотарифный счётчик (factory 250314753):
  - `unique_id`: `pik_comfort_meters_250314753`
  - `entity_id`: `sensor.pik_comfort_meters_250314753`
  - `name`: `PIK Горячая вода 250314753`
- Двухтарифный счётчик (factory 250314753), тариф 1:
  - `unique_id`: `pik_comfort_meters_250314753_t1`
  - `entity_id`: `sensor.pik_comfort_meters_250314753_t1`
  - `name`: `PIK Горячая вода 250314753 (День)`

Миграция и удаление старых сущностей

- После обновления интеграции уникальные идентификаторы сенсоров могли измениться по сравнению с предыдущими версиями интеграции. Home Assistant создаст новые сущности с новыми `unique_id` и `entity_id` — старые записи останутся в `entity_registry`.
- Чтобы избежать дублирования, можно:
  - удалить старые сущности вручную через UI (Settings → Devices & Services → Entities) или
  - выполнить миграцию в `entity_registry` (при необходимости могу помочь подготовить скрипт для автоматического обновления `entity_registry`).

### Сенсоры ошибок (binary_sensor)

- `PIK Comfort Ошибка обновления данных` — отражает проблемы с обновлением (атрибуты: `last_attempt`, `last_success`, `last_error_message`).
- `PIK Comfort Ошибка отправки показаний` — отражает ошибки отправки показаний.

## Сервисы

### pik_comfort_meters.submit_reading

Отправляет показания счётчика.

- Параметры:
  - `device_id` (обязательный) — идентификатор устройства из Device Registry (можно выбрать через device selector).

Пример вызова (Developer Tools → Services):

```yaml
service: pik_comfort_meters.submit_reading
data:
  device_id: "<device-id>"
```

## Ошибки и сообщения конфигурации

- `auth_failed`: неверные учётные данные — проверьте телефон и пароль.
- `no_accounts`: у аккаунта не найдено связанных счётчиков/аккаунтов.
- Ошибки обновления отражаются в соответствующем бинарном сенсоре; смотрите атрибут `last_error_message`.

## Логирование и отладка

Чтобы включить подробное логирование для интеграции, добавьте в `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.pik_comfort_meters: debug
```

Перезапустите Home Assistant и смотрите системные логи.

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
      device_id: "<device-id>" # замените на реальный device_id из Device Registry
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
      - binary_sensor.pik_comfort_update_error
      - binary_sensor.pik_comfort_submit_error
    to: 'on'
action:
  - service: notify.telegram
    data:
      message: >-
        PIK Comfort: обнаружена ошибка ({{ trigger.to_state.name }}).
        Последнее сообщение об ошибке: {{ state_attr(trigger.entity_id, 'last_error_message') or 'нет данных' }}
mode: single
```

Примечания:

- Замените `device_id` в первом примере на реальный `device_id` устройства PIK из Device Registry.
- Убедитесь в фактических `entity_id` бинарных сенсоров в Developer Tools → States (в примере использованы `binary_sensor.pik_comfort_update_error` и `binary_sensor.pik_comfort_submit_error`).
- В примере уведомления используется `notify.telegram`. Замените сервис уведомлений, если у вас другой провайдер (например, `notify.mobile_app_<device>`).

## Частые вопросы / FAQ

- Если сенсоры не появляются — убедитесь, что аутентификация успешна и у аккаунта есть привязанные счётчики в личном кабинете PIK.
- Если сервис `submit_reading` возвращает ошибку — проверьте логи и атрибуты бинарного сенсора отправки показаний.

## Поддержка

- Ошибки и фича-реквесты: https://github.com/ashurkovdev/hass-pik_comfort_meters/issues
- PR и предложения по улучшению приветствуются.
