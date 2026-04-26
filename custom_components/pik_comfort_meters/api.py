"""API для взаимодействия с сервером ПИК Комфорт."""

import json
import logging
import asyncio
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

# Настройки retry с exponential backoff
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # 1 секунда
MAX_RETRY_DELAY = 60  # 60 секунд


class PIKComfortAPI:
    """Класс для работы с API ПИК Комфорт."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        phone: str,
        password: str,
        max_retries: int = MAX_RETRIES,
        initial_delay: float = INITIAL_RETRY_DELAY,
    ):
        self._session = session
        self.phone = phone
        self.password = password
        self.token: Optional[str] = None
        self.account_uid: Optional[str] = None
        self._max_retries = max_retries
        self._initial_delay = initial_delay

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        json_data: Optional[Union[Dict, List]] = None,
        retry_auth: bool = True,
    ) -> Optional[Union[Dict, List]]:
        """Выполнить HTTP-запрос с повторными попытками и exponential backoff."""
        for attempt in range(self._max_retries + 1):
            try:
                return await self._request(
                    method, url, headers, json_data, retry_auth
                )
            except Exception as e:
                if attempt < self._max_retries:
                    delay = min(
                        self._initial_delay * (2 ** attempt),
                        MAX_RETRY_DELAY,
                    )
                    _LOGGER.warning(
                        "Request %s %s failed (attempt %d/%d), retrying in %ds: %s",
                        method,
                        url,
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                        str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    _LOGGER.exception(
                        "Request %s %s failed after %d attempts: %s",
                        method,
                        url,
                        self._max_retries + 1,
                        str(e),
                    )
                    return None
        return None

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
            async with async_timeout.timeout(30):
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
                            return await self._request(
                                method, url, headers, json_data, retry_auth=False
                            )
                        else:
                            _LOGGER.error("Failed to refresh token")
                            return None
                    elif resp.status == 429:
                        # Rate limiting - wait and retry
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        _LOGGER.warning(
                            "Rate limit hit for %s %s, waiting %ds", method, url, retry_after
                        )
                        await asyncio.sleep(retry_after)
                        return await self._request_with_retry(
                            method, url, headers, json_data, retry_auth=False
                        )
                    else:
                        _LOGGER.error(
                            "API request failed: %s %s\nHeaders: %s\nRequest body: %s\nResponse status: %d\nResponse body: %s",
                            method,
                            url,
                            headers,
                            json.dumps(json_data) if json_data else "None",
                            resp.status,
                            text,
                        )
                        return None
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout on API request: %s %s", method, url
            )
            return None
        except Exception as e:
            _LOGGER.exception("Exception during API request: %s %s - %s", method, url, str(e))
            return None

    async def authenticate(self) -> bool:
        """Получить токен по номеру телефона и паролю."""
        payload = {"username": self.phone, "password": self.password}
        headers = {"Content-Type": "application/json"}
        data = await self._request_with_retry(
            "POST", API_AUTH_URL, headers=headers, json_data=payload, retry_auth=False
        )
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
        data = await self._request_with_retry("GET", API_DASHBOARD_URL)
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
        data = await self._request_with_retry("GET", url)
        if data:
            meters = data.get("meters", [])
            _LOGGER.debug("Fetched %d meters", len(meters))
            return meters
        return None

    async def submit_readings(
        self, meter_id: str, readings: Union[float, List[float]]
    ) -> bool:
        """
        Отправить показания для одного счётчика.

        Если readings — float, отправляется однотарифное показание.
        Если readings — список, отправляются многотарифные показания
        (порядок соответствует tariff_type 1, 2, 3).
        """
        if not self.token:
            _LOGGER.error("No token, cannot submit readings")
            return False

        if isinstance(readings, (float, int)):
            payload = [
                {"meter": meter_id, "tariff_type": 1, "value": float(readings)}
            ]
        else:
            payload = [
                {"meter": meter_id, "tariff_type": idx + 1, "value": float(v)}
                for idx, v in enumerate(readings)
            ]

        headers = {"Content-Type": "application/json"}
        data = await self._request_with_retry(
            "POST", API_SUBMIT_URL, headers=headers, json_data=payload
        )

        success = data is not None
        if success:
            _LOGGER.debug("Readings submitted for meter %s: %s", meter_id, readings)
        else:
            _LOGGER.error("Failed to submit readings for meter %s", meter_id)
        return success