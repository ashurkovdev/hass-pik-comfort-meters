"""Константы для интеграции PIK Comfort Meters."""

DOMAIN = "pik_comfort_meters"
CONF_PHONE = "phone"
CONF_PASSWORD = "password"
CONF_ACCOUNT_UID = "account_uid"
CONF_TOKEN = "token"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL = 21600  # 6 часов в секундах
MIN_UPDATE_INTERVAL = 3600       # 1 час
MAX_UPDATE_INTERVAL = 86400      # 24 часа

API_AUTH_URL = "https://resident-cabinet-back.pik-software.ru/api-token-auth/"
API_DASHBOARD_URL = "https://resident-cabinet-back.pik-software.ru/api/v24/aggregate/dashboard/?notifications_size=0"
API_ACCOUNT_URL = "https://resident-cabinet-back.pik-software.ru/api/v24/aggregate/accounts/{account_uid}/?tickets_size=32&filter_house_meters=true"
API_SUBMIT_URL = "https://resident-cabinet-back.pik-software.ru/api/v2/usermeterreading-list/"

RESOURCE_TYPES = {
    1: "cold_water",
    2: "hot_water",
    3: "electricity",
}

RESOURCE_NAMES = {
    1: "Холодная вода",
    2: "Горячая вода",
    3: "Электроэнергия",
}

UNIT_MAPPING = {
    1: "m³",
    2: "m³",
    3: "kWh",
}

# Идентификаторы для бинарных сенсоров ошибок
BINARY_SENSOR_UPDATE_ERROR = "update_error"
BINARY_SENSOR_SUBMIT_ERROR = "submit_error"