from __future__ import annotations

import asyncio
import base64
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Final

import aiohttp
import hashlib
import os
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)

# TR-064 endpoints
TR064_DESC: Final = "/tr64desc.xml"
TR064_CONTROL: Final = "/upnp/control/x_contact"
TR064_SERVICE: Final = "X_AVM-DE_OnTel:1"

REGEX_NUMBER = r"[^\d\+]"


def normalize_number(number: str) -> str:
    return re.sub(REGEX_NUMBER, "", str(number or ""))

def _parse_www_authenticate(value: str) -> dict[str, str]:
    # Example: Digest realm="HTTPS Access",nonce="....",algorithm=MD5,qop="auth"
    value = value.strip()
    if value.lower().startswith("digest "):
        value = value[7:]
    parts: dict[str, str] = {}
    for item in value.split(","):
        item = item.strip()
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        parts[k.strip()] = v.strip().strip('"')
    return parts


def _digest_header(
    *,
    www_auth: dict[str, str],
    method: str,
    uri: str,
    username: str,
    password: str,
) -> str:
    realm = www_auth.get("realm", "")
    nonce = www_auth.get("nonce", "")
    qop = www_auth.get("qop", "auth")
    algorithm = www_auth.get("algorithm", "MD5")

    if algorithm.upper() != "MD5":
        raise RuntimeError(f"Unsupported digest algorithm: {algorithm}")

    nc = "00000001"
    cnonce = hashlib.md5(os.urandom(16)).hexdigest()

    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()

    return (
        'Digest '
        f'username="{username}", '
        f'realm="{realm}", '
        f'nonce="{nonce}", '
        f'uri="{uri}", '
        f'response="{response}", '
        f'algorithm=MD5, '
        f'qop={qop}, '
        f'nc={nc}, '
        f'cnonce="{cnonce}"'
    )


async def _request_digest(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    *,
    username: str,
    password: str,
    headers: dict[str, str] | None = None,
    data: str | bytes | None = None,
    timeout: int = 20,
) -> str:
    """
    Perform an HTTP request using Digest auth (MD5, qop=auth) by handling the 401 challenge.
    """
    headers = dict(headers or {})

    async with session.request(method, url, headers=headers, data=data, timeout=timeout) as resp:
        if resp.status != 401:
            resp.raise_for_status()
            return await resp.text()

        www = resp.headers.get("WWW-Authenticate", "")
        if "digest" not in www.lower():
            raise RuntimeError(f"Expected Digest challenge, got: {www}")

    parsed = urlparse(url)
    uri = parsed.path or "/"
    if parsed.query:
        uri = f"{uri}?{parsed.query}"

    www_auth = _parse_www_authenticate(www)
    headers["Authorization"] = _digest_header(
        www_auth=www_auth,
        method=method,
        uri=uri,
        username=username,
        password=password,
    )

    async with session.request(method, url, headers=headers, data=data, timeout=timeout) as resp2:
        resp2.raise_for_status()
        return await resp2.text()

@dataclass(frozen=True)
class Contact:
    name: str
    numbers: list[str]
    vip: bool = False


class FritzTr064Phonebook:
    """
    Minimal TR-064 client to resolve numbers using X_AVM-DE_OnTel phonebook.

    It implements:
      - GetPhonebookList
      - GetPhonebook
      - Download XML from PhonebookURL and parse entries

    Note: Fritz can return the phonebook XML via an URL that may require auth too.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        phonebook_id: int,
        prefixes: list[str] | None,
        session: aiohttp.ClientSession,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._phonebook_id = phonebook_id
        self._prefixes = prefixes or []
        self._session = session

        self._number_map: dict[str, Contact] = {}
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"
        
    @property
    def entries(self) -> int:
        return len(self._number_map)

    def _auth_header(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def _soap_call(self, action: str, arguments: dict[str, Any]) -> str:
        args_xml = "".join(f"<{k}>{v}</{k}>" for k, v in arguments.items())
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            "<s:Body>"
            f'<u:{action} xmlns:u="urn:dslforum-org:service:{TR064_SERVICE}">'
            f"{args_xml}"
            f"</u:{action}>"
            "</s:Body>"
            "</s:Envelope>"
        )

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"urn:dslforum-org:service:{TR064_SERVICE}#{action}"',
        }

        url = f"{self.base_url}{TR064_CONTROL}"
        return await _request_digest(
            self._session,
            "POST",
            url,
            username=self._username,
            password=self._password,
            headers=headers,
            data=body,
            timeout=20,
        )


    async def _download_phonebook_xml(self, url: str) -> str:
        return await _request_digest(
            self._session,
            "GET",
            url,
            username=self._username,
            password=self._password,
            headers={},
            timeout=30,
        )

    async def _get_phonebook_url(self) -> str:
        xml = await self._soap_call("GetPhonebook", {"NewPhonebookID": self._phonebook_id})
        root = ET.fromstring(xml)
        # Find NewPhonebookURL in response (namespace-agnostic)
        for elem in root.iter():
            if elem.tag.endswith("NewPhonebookURL") and elem.text:
                return elem.text
        raise RuntimeError("TR-064: NewPhonebookURL not found")

    def _parse_phonebook(self, xml: str) -> dict[str, Contact]:
        """
        Parse FRITZ phonebook XML.
        We try to be tolerant to schema variants.
        """
        root = ET.fromstring(xml)
        number_map: dict[str, Contact] = {}

        # Typical structure:
        # <phonebooks><phonebook><contact>...</contact></phonebook></phonebooks>
        for contact in root.iter():
            if not contact.tag.endswith("contact"):
                continue

            name = ""
            vip = False
            numbers: list[str] = []

            # name
            for el in contact.iter():
                if el.tag.endswith("realName") and el.text:
                    name = el.text.strip()
                if el.tag.endswith("category") and el.text:
                    vip = el.text.strip() == "1"

            # numbers: <telephony><number ...>VALUE</number></telephony>
            for el in contact.iter():
                if el.tag.endswith("number") and el.text:
                    numbers.append(normalize_number(el.text))

            if not name:
                continue

            c = Contact(name=name, numbers=[n for n in numbers if n], vip=vip)
            for nr in c.numbers:
                number_map[nr] = c

        return number_map

    async def refresh(self) -> None:
        """Download and parse phonebook."""
        async with self._lock:
            url = await self._get_phonebook_url()
            xml = await self._download_phonebook_xml(url)
            self._number_map = self._parse_phonebook(xml)
            _LOGGER.info("TR-064 phonebook loaded: %s entries", len(self._number_map))

    async def lookup(self, number: str) -> Contact | None:
        """Resolve a number to a contact (with optional prefix attempts)."""
        n = normalize_number(number)
        async with self._lock:
            if n in self._number_map:
                return self._number_map[n]

            # Try prefixes like in the built-in integration
            for p in self._prefixes:
                if (p + n) in self._number_map:
                    return self._number_map[p + n]
                nn = n.lstrip("0")
                if (p + nn) in self._number_map:
                    return self._number_map[p + nn]
        return None