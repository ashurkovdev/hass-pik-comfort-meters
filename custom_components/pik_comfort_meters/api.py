"""API для взаимодействия с сервером ПИК Комфорт."""

import json
import logging
from typing import Optional, Dict, Any, List, Union

import aiohttp
import async_timeout

from .const import (
    API_AUTH_URL,
    API_DASHBOARD_URL,
    API_ACCOUNT_URL,
    API_SUBMIT_URL,
)

_LOGGER = logging.getLogger(__name__)


class PIKComfortAPI:
    """Класс для работы с API ПИК Комфорт."""

    def __init__(self, session: aiohttp.ClientSession, phone: str, password: str):
        self._session = session
        self.phone = phone
        self.password = password
        self.token: Optional[str] = None
        self.account_uid: Optional[str] = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        json_data: Optional[Union[Dict, List]] = None,
        retry_auth: bool = True,
    ) -> Optional[Union[Dict, List]]:
        """Выполнить HTTP-запрос с логированием ошибок и автоматическим обновлением токена."""
        if headers is None:
            headers = {}
        if self.token and "Authorization" not in headers:
            headers["Authorization"] = f"Token {self.token}"

        try:
            async with async_timeout.timeout(15):
                async with self._session.request(
                    method, url, headers=headers, json=json_data
                ) as resp:
                    text = await resp.text()
                    if resp.status in (200, 201):
                        return await resp.json() if text else {}
                    elif resp.status == 401 and retry_auth:
                        _LOGGER.warning("Token expired, attempting to refresh...")
                        if await self.authenticate():
                            headers["Authorization"] = f"Token {self.token}"
                            return await self._request(method, url, headers, json_data, retry_auth=False)
                        else:
                            _LOGGER.error("Failed to refresh token")
                            return None
                    else:
                        _LOGGER.error(
                            "API request failed: %s %s\nHeaders: %s\nRequest body: %s\nResponse status: %d\nResponse body: %s",
                            method, url, headers,
                            json.dumps(json_data) if json_data else "None",
                            resp.status, text,
                        )
                        return None
        except Exception as e:
            _LOGGER.exception("Exception during API request: %s %s - %s", method, url, str(e))
            return None

    async def authenticate(self) -> bool:
        """Получить токен по номеру телефона и паролю."""
        payload = {"username": self.phone, "password": self.password}
        headers = {"Content-Type": "application/json"}
        data = await self._request("POST", API_AUTH_URL, headers=headers, json_data=payload, retry_auth=False)
        if data and "token" in data:
            self.token = data["token"]
            _LOGGER.debug("Authentication successful")
            return True
        _LOGGER.error("Authentication failed for phone %s", self.phone)
        return False

    async def get_dashboard(self) -> Optional[Dict[str, Any]]:
        """Получить dashboard и извлечь account_uid первого аккаунта."""
        if not self.token:
            _LOGGER.error("No token, cannot fetch dashboard")
            return None
        data = await self._request("GET", API_DASHBOARD_URL)
        if data and data.get("accounts"):
            self.account_uid = data["accounts"][0]["_uid"]
            _LOGGER.debug("Found account_uid: %s", self.account_uid)
        return data

    async def get_account_meters(self) -> Optional[List[Dict[str, Any]]]:
        """Получить список счетчиков для выбранного account_uid."""
        if not self.token or not self.account_uid:
            _LOGGER.error("Missing token or account_uid")
            return None
        url = API_ACCOUNT_URL.format(account_uid=self.account_uid)
        data = await self._request("GET", url)
        if data:
            meters = data.get("meters", [])
            _LOGGER.debug("Fetched %d meters", len(meters))
            return meters
        return None

    async def submit_readings(self, meter_id: str, readings: Union[float, List[float]]) -> bool:
        """
        Отправить показания для одного счётчика.
        Если readings — float, отправляется однотарифное показание.
        Если readings — список, отправляются многотарифные показания (порядок соответствует tariff_type 1,2,3).
        """
        if not self.token:
            _LOGGER.error("No token, cannot submit readings")
            return False
        headers = {"Content-Type": "application/json"}
        if isinstance(readings, (float, int)):
            payload = [{"meter": meter_id, "tariff_type": 1, "value": float(readings)}]
        else:
            payload = [
                {"meter": meter_id, "tariff_type": idx + 1, "value": float(v)}
                for idx, v in enumerate(readings)
            ]
        data = await self._request("POST", API_SUBMIT_URL, headers=headers, json_data=payload)
        success = data is not None
        if success:
            _LOGGER.debug("Readings submitted for meter %s: %s", meter_id, readings)
        else:
            _LOGGER.error("Failed to submit readings for meter %s", meter_id)
        return success