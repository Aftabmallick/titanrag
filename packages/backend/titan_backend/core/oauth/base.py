from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    provider_id: str
    email: str
    full_name: str | None
    provider_name: str


class OAuthProvider(ABC):
    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Return the URL to redirect the user to for authentication."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str) -> dict[str, str]:
        """Exchange the auth code for access tokens."""
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user profile information from provider."""
        pass
