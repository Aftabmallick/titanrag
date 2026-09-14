from typing import cast
from urllib.parse import urlencode

import httpx
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException
from titan_backend.core.oauth.base import OAuthProvider, OAuthUserInfo


class GoogleOAuthProvider(OAuthProvider):
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, redirect_uri: str = ""):
        self.client_id = client_id or settings.GOOGLE_CLIENT_ID or "google-client-id"
        self.client_secret = client_secret or settings.GOOGLE_CLIENT_SECRET or "google-client-secret"
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, str]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            if resp.is_error:
                raise AppException(
                    message="Failed to exchange Google OAuth code",
                    status_code=400,
                    error_code="OAUTH_EXCHANGE_FAILED",
                    details={"provider_error": resp.text},
                )
            return cast(dict[str, str], resp.json())

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.USERINFO_URL, headers=headers)
            if resp.is_error:
                raise AppException(
                    message="Failed to fetch Google user profile",
                    status_code=400,
                    error_code="OAUTH_USERINFO_FAILED",
                )
            data = resp.json()
            return OAuthUserInfo(
                provider_id=data["sub"],
                email=data["email"],
                full_name=data.get("name"),
                provider_name="google",
            )


class GitHubOAuthProvider(OAuthProvider):
    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, redirect_uri: str = ""):
        self.client_id = client_id or settings.GITHUB_CLIENT_ID or "github-client-id"
        self.client_secret = client_secret or settings.GITHUB_CLIENT_SECRET or "github-client-secret"
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "scope": "read:user user:email",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, str]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.TOKEN_URL, data=data, headers=headers)
            if resp.is_error:
                raise AppException(
                    message="Failed to exchange GitHub OAuth code",
                    status_code=400,
                    error_code="OAUTH_EXCHANGE_FAILED",
                )
            return cast(dict[str, str], resp.json())

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            user_resp = await client.get(self.USERINFO_URL, headers=headers)
            if user_resp.is_error:
                raise AppException(message="Failed to fetch GitHub profile", status_code=400)
            user_data = user_resp.json()

            email = user_data.get("email")
            if not email:
                emails_resp = await client.get(self.EMAILS_URL, headers=headers)
                if not emails_resp.is_error:
                    emails = emails_resp.json()
                    primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
                    if primary:
                        email = primary["email"]
                    elif emails:
                        email = emails[0].get("email")

            if not email:
                raise AppException(message="No verified email associated with GitHub account", status_code=400)

            return OAuthUserInfo(
                provider_id=str(user_data["id"]),
                email=email,
                full_name=user_data.get("name") or user_data.get("login"),
                provider_name="github",
            )
