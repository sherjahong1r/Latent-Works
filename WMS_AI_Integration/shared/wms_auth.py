"""
Real WMS API uchun autentifikatsiya qatlami.

Login qiladi (POST /api/auth/login), accessToken'ni xotirada saqlaydi,
va muddati o'tganda (yoki 401 kelganda) avtomatik qayta login qiladi.

Tasdiqlangan (DevTools orqali ko'rilgan) shakl:

POST https://api-wms.tenzorsoft.uz/api/auth/login
Body:     {"identifier": "...", "password": "..."}
Response: {"accessToken": "...", "refreshToken": "...", "tokenType": "Bearer", "identifier": "..."}

Keyingi so'rovlarda: Authorization: Bearer <accessToken>
"""
import time
import httpx
from shared.config import WMS_API_URL, WMS_USERNAME, WMS_PASSWORD

LOGIN_PATH = "/api/auth/login"

# Token 15 daqiqada bir marta majburiy yangilanadi (aniq TTL hali noma'lum,
# shuning uchun ehtiyotkorlik bilan qisqaroq muddat tanlandi).
TOKEN_TTL_SECONDS = 15 * 60

_token_cache = {
    "access_token": None,
    "refresh_token": None,
    "obtained_at": 0.0,
}


class WmsAuthError(Exception):
    """Login yoki token bilan bog'liq xato."""


def _login() -> None:
    """WMS API ga login qiladi va tokenlarni keshga saqlaydi."""
    if not WMS_USERNAME or not WMS_PASSWORD:
        raise WmsAuthError(
            "WMS_USERNAME / WMS_PASSWORD .env faylida ko'rsatilmagan."
        )

    url = f"{WMS_API_URL}{LOGIN_PATH}"
    try:
        resp = httpx.post(
            url,
            json={"identifier": WMS_USERNAME, "password": WMS_PASSWORD},
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise WmsAuthError(f"Login rad etildi ({e.response.status_code}): {e.response.text}") from e
    except httpx.RequestError as e:
        raise WmsAuthError(f"WMS API ga ulanib bo'lmadi: {e}") from e

    data = resp.json()
    access_token = data.get("accessToken")
    if not access_token:
        raise WmsAuthError(f"Login javobida accessToken topilmadi: {data}")

    _token_cache["access_token"] = access_token
    _token_cache["refresh_token"] = data.get("refreshToken")
    _token_cache["obtained_at"] = time.time()


def get_access_token(force_refresh: bool = False) -> str:
    """Amaldagi access tokenni qaytaradi; kerak bo'lsa avval login qiladi."""
    is_expired = (time.time() - _token_cache["obtained_at"]) > TOKEN_TTL_SECONDS
    if force_refresh or not _token_cache["access_token"] or is_expired:
        _login()
    return _token_cache["access_token"]


def auth_headers(force_refresh: bool = False) -> dict:
    """So'rovga qo'shiladigan Authorization header."""
    token = get_access_token(force_refresh=force_refresh)
    return {"Authorization": f"Bearer {token}"}


def wms_request(method: str, path: str, **kwargs) -> httpx.Response:
    """
    Autentifikatsiyalangan so'rov. 401 kelsa — bir marta qayta login qilib
    qayta urinadi (token muddati kutilganidan oldin tugagan holat uchun).
    """
    url = f"{WMS_API_URL}{path}"
    headers = kwargs.pop("headers", {})

    resp = httpx.request(method, url, headers={**auth_headers(), **headers}, timeout=15, **kwargs)
    if resp.status_code == 401:
        resp = httpx.request(
            method, url, headers={**auth_headers(force_refresh=True), **headers}, timeout=15, **kwargs
        )
    resp.raise_for_status()
    return resp


def wms_get(path: str, params: dict = None) -> dict:
    """Qulaylik uchun: autentifikatsiyalangan GET so'rov, JSON qaytaradi."""
    return wms_request("GET", path, params=params).json()


def wms_post(path: str, json_body: dict = None) -> dict:
    """Qulaylik uchun: autentifikatsiyalangan POST so'rov, JSON qaytaradi."""
    return wms_request("POST", path, json=json_body).json()
