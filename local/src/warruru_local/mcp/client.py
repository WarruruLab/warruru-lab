"""데몬 HTTP 클라이언트. 어댑터가 하는 유일한 판단은 '데몬에 닿았는가'다."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass

import httpx

from warruru_local import spool
from warruru_local.clock import Clock, to_iso
from warruru_local.config import Settings
from warruru_local.ids import new_id

SPAWN_WAIT_SECONDS = 3.0
SPAWN_POLL_SECONDS = 0.1
_NO_SPOOL_STATUSES = {400, 401, 404, 422}


@dataclass(frozen=True)
class Outcome:
    body: dict | None
    storage: str
    message: str


class _HttpxTransport:
    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        return httpx.request(
            method, url, json=json, params=params, headers=headers, timeout=timeout
        )


class DaemonClient:
    def __init__(
        self,
        settings: Settings,
        client_instance_id: str,
        logger: logging.Logger,
        clock: Clock,
        transport=None,
        spawner=None,
    ) -> None:
        self._settings = settings
        self._client_instance_id = client_instance_id
        self._logger = logger
        self._clock = clock
        self._transport = transport or _HttpxTransport()
        self._spawner = spawner or self._spawn_daemon
        self._spawn_tried = False

    # ------------------------------------------------------------------

    @property
    def _base(self) -> str:
        return f"http://{self._settings.host}:{self._settings.port}"

    @property
    def _headers(self) -> dict:
        return {"X-Warruru-Token": self._settings.token}

    def _call(self, method: str, path: str, json=None, params=None):
        return self._transport.request(
            method,
            f"{self._base}{path}",
            json=json,
            params=params,
            headers=self._headers,
            timeout=self._settings.http_timeout_seconds,
        )

    # ------------------------------------------------------------------

    def send(self, kind: str, path: str, payload: dict) -> Outcome:
        """기록 계열. 어떤 경우에도 기록을 잃지 않는다."""
        for attempt in (1, 2):
            try:
                response = self._call("POST", path, json=payload)
            except (httpx.TransportError, httpx.HTTPError) as error:
                self._logger.warning("데몬 호출 실패(%d회차): %s", attempt, error)
                if attempt == 1 and self._settings.autostart_daemon:
                    self._try_spawn()
                    continue
                break

            if response.status_code < 400:
                return Outcome(response.json(), "DAEMON", "기록했습니다.")

            if response.status_code in _NO_SPOOL_STATUSES:
                return Outcome(None, "DAEMON", _error_message(response))

            if response.status_code == 503 and attempt == 1:
                continue
            break

        return self._to_spool(kind, payload)

    def query(self, path: str, params: dict) -> Outcome:
        """조회. 폴백할 대상이 없다."""
        try:
            response = self._call("GET", path, params=params)
        except (httpx.TransportError, httpx.HTTPError):
            if self._settings.autostart_daemon:
                self._try_spawn()
            try:
                response = self._call("GET", path, params=params)
            except (httpx.TransportError, httpx.HTTPError) as error:
                return Outcome(None, "NONE", f"데몬에 연결하지 못했습니다: {error}")

        if response.status_code >= 400:
            return Outcome(None, "NONE", _error_message(response))
        return Outcome(response.json(), "DAEMON", "조회했습니다.")

    def close(self) -> Outcome:
        return self.send(
            "client_closed",
            f"/v1/clients/{self._client_instance_id}/closed",
            {"client_instance_id": self._client_instance_id},
        )

    # ------------------------------------------------------------------

    def _to_spool(self, kind: str, payload: dict) -> Outcome:
        spool.append(
            self._settings.home,
            self._client_instance_id,
            kind,
            payload,
            to_iso(self._clock.now()),
            new_id("evt"),
        )
        return Outcome(None, "SPOOL", "데몬에 닿지 못해 로컬에 보관했습니다. 나중에 반영됩니다.")

    def _try_spawn(self) -> None:
        if self._spawn_tried:
            return
        self._spawn_tried = True
        try:
            self._spawner()
        except Exception:
            self._logger.exception("데몬을 띄우지 못했다")

    def _spawn_daemon(self) -> bool:
        """어댑터와 분리해 띄운다. 에이전트가 종료돼도 데몬이 함께 죽으면 안 된다."""
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if hasattr(subprocess, "DETACHED_PROCESS"):  # Windows
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:  # POSIX
            kwargs["start_new_session"] = True

        subprocess.Popen(
            [sys.executable, "-m", "warruru_local.daemon.app"], **kwargs
        )

        deadline = time.monotonic() + SPAWN_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                if self._call("GET", "/v1/health").status_code == 200:
                    return True
            except (httpx.TransportError, httpx.HTTPError):
                pass
            time.sleep(SPAWN_POLL_SECONDS)
        return False


def _error_message(response) -> str:
    try:
        return response.json()["error"]["message"]
    except Exception:
        return f"데몬이 {response.status_code} 를 돌려주었습니다."
