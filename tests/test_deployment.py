"""Tests for Cloud/Data Center deployment resolution."""
from __future__ import annotations

from bb.core.deployment import base_url_from_remote, deployment_from_base_url, normalize_base_url


def test_cloud_api_host_normalizes_to_cloud_web() -> None:
    assert normalize_base_url("https://api.bitbucket.org/2.0") == "https://bitbucket.org"


def test_datacenter_rest_url_strips_api_path() -> None:
    assert (
        normalize_base_url("https://bitbucket.polariswireless.com/rest/api/1.0/projects")
        == "https://bitbucket.polariswireless.com"
    )


def test_datacenter_context_path_preserved() -> None:
    assert normalize_base_url("https://example.com/bitbucket") == "https://example.com/bitbucket"


def test_deployment_from_datacenter_base_url() -> None:
    deployment = deployment_from_base_url("bitbucket.polariswireless.com")
    assert deployment.api_url == "https://bitbucket.polariswireless.com/rest/api/1.0"


def test_base_url_from_https_remote() -> None:
    assert (
        base_url_from_remote("https://bitbucket.polariswireless.com/scm/PVA/radio.git")
        == "https://bitbucket.polariswireless.com"
    )


def test_base_url_from_ssh_remote_with_port() -> None:
    assert base_url_from_remote("ssh://git@bitbucket.polariswireless.com:7999/PVA/radio.git") == (
        "https://bitbucket.polariswireless.com:7999"
    )


def test_base_url_from_unknown_remote_returns_empty() -> None:
    assert base_url_from_remote("not-a-url") == ""
