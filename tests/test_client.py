"""Tests for BBClient HTTP behaviour using httpx mock transport."""
from __future__ import annotations

import json

import pytest
import httpx

from bb.core.auth import Credential
from bb.core.client import APIError, BBClient


def _cred(token: str = "test-token") -> Credential:
    return Credential(token=token, source="flag")


def _transport(status: int, body: dict | None = None) -> httpx.MockTransport:
    payload = json.dumps(body or {}).encode()
    headers = {"content-type": "application/json"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload, headers=headers)

    return httpx.MockTransport(handler)


def test_200_returns_json() -> None:
    client = BBClient(_cred(), _transport=_transport(200, {"display_name": "alice"}))
    data = client.get("/user")
    assert data["display_name"] == "alice"


def test_401_raises_api_error() -> None:
    client = BBClient(_cred(), _transport=_transport(401, {"error": {"message": "Unauthorized"}}))
    with pytest.raises(APIError) as exc_info:
        client.get("/user")
    assert exc_info.value.status == 401


def test_404_raises_api_error() -> None:
    client = BBClient(_cred(), _transport=_transport(404, {"error": {"message": "Not Found"}}))
    with pytest.raises(APIError) as exc_info:
        client.get("/repos/x/y")
    assert exc_info.value.status == 404


def test_204_returns_empty_dict() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = BBClient(_cred(), _transport=httpx.MockTransport(handler))
    assert client.get("/something") == {}


def test_paginate_follows_next() -> None:
    pages = [
        {"values": [{"id": 1}], "next": "https://api.bitbucket.org/2.0/page2"},
        {"values": [{"id": 2}]},
    ]
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        page = pages[call_count]
        call_count += 1
        return httpx.Response(
            200,
            content=json.dumps(page).encode(),
            headers={"content-type": "application/json"},
        )

    client = BBClient(_cred(), _transport=httpx.MockTransport(handler))
    items = list(client.paginate("/repos"))
    assert len(items) == 2
