import aiohttp
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class School21API:
    AUTH_URL = "https://auth.21-school.ru/auth/realms/EduPowerKeycloak/protocol/openid-connect/token"
    BASE_URL = "https://platform.21-school.ru/services/21-school/api/v1"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def authenticate(self) -> bool:
        """Authenticate and get access token."""
        session = await self._get_session()

        data = {
            "client_id": "s21-open-api",
            "username": self.username,
            "password": self.password,
            "grant_type": "password"
        }

        try:
            async with session.post(
                self.AUTH_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result.get("access_token")
                    self.refresh_token = result.get("refresh_token")
                    logger.info("Successfully authenticated with School 21 API")
                    return True
                else:
                    logger.error(f"Authentication failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def _make_request(self, endpoint: str) -> Optional[dict]:
        """Make authenticated API request."""
        if not self.access_token:
            if not await self.authenticate():
                return None

        session = await self._get_session()
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            async with session.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers
            ) as response:
                if response.status == 401:
                    # Token expired, try to re-authenticate
                    if await self.authenticate():
                        return await self._make_request(endpoint)
                    return None
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    logger.error(f"API request failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None

    async def get_participant(self, login: str) -> Optional[dict]:
        """Get participant info by login."""
        return await self._make_request(f"/participants/{login}")

    async def get_participant_coalition(self, login: str) -> Optional[dict]:
        """Get participant coalition info by login."""
        return await self._make_request(f"/participants/{login}/coalition")

    async def participant_exists(self, login: str) -> bool:
        """Check if participant exists on the platform."""
        result = await self.get_participant(login)
        return result is not None

    async def get_coalition_name(self, login: str) -> Optional[str]:
        """Get coalition name for a participant."""
        coalition_data = await self.get_participant_coalition(login)
        if coalition_data:
            return coalition_data.get("name") or coalition_data.get("coalitionName")
        return None
