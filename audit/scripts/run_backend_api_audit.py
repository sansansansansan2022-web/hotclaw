from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
BACKEND_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
ARTIFACT_ROOT = REPO_ROOT / "audit" / "artifacts" / "api"
LOG_ROOT = REPO_ROOT / "audit" / "logs"
DB_PATH = BACKEND_DIR / "hotclaw.db"


@dataclass
class BackendServer:
    port: int
    label: str
    e2e_mode: bool

    def __post_init__(self) -> None:
        self.out_log = LOG_ROOT / f"{self.label}-backend.out.log"
        self.err_log = LOG_ROOT / f"{self.label}-backend.err.log"
        self.process: subprocess.Popen[str] | None = None
        self._stdout_handle = None
        self._stderr_handle = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = os.environ.copy()
        env["HOTCLAW_AUTO_CREATE_TABLES"] = "0"
        env["APP_DEBUG"] = "true"
        env["HOTCLAW_E2E_TEST_MODE"] = "1" if self.e2e_mode else "0"
        self._stdout_handle = open(self.out_log, "w", encoding="utf-8")
        self._stderr_handle = open(self.err_log, "w", encoding="utf-8")
        self.process = subprocess.Popen(
            [
                str(BACKEND_PYTHON),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ],
            cwd=BACKEND_DIR,
            env=env,
            stdout=self._stdout_handle,
            stderr=self._stderr_handle,
            text=True,
        )
        self.wait_for_health()

    def wait_for_health(self, timeout_seconds: int = 60) -> None:
        deadline = time.time() + timeout_seconds
        last_error: str | None = None
        with httpx.Client(timeout=5.0) as client:
            while time.time() < deadline:
                if self.process and self.process.poll() is not None:
                    raise RuntimeError(
                        f"backend process exited early with code {self.process.returncode}"
                    )
                try:
                    response = client.get(f"{self.base_url}/api/v1/health")
                    if response.status_code == 200:
                        return
                    last_error = f"health status {response.status_code}"
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                time.sleep(2)
        raise RuntimeError(f"backend health timeout: {last_error}")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self._stdout_handle:
            self._stdout_handle.close()
        if self._stderr_handle:
            self._stderr_handle.close()


class ArtifactWriter:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.dir = ARTIFACT_ROOT / scenario
        self.dir.mkdir(parents=True, exist_ok=True)
        self.counter = 0
        self.summary: dict[str, Any] = {
            "scenario": scenario,
            "steps": [],
            "ids": {},
            "logs": {},
        }

    def write(self, name: str, payload: dict[str, Any]) -> Path:
        self.counter += 1
        path = self.dir / f"{self.counter:02d}-{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.summary["steps"].append({"name": name, "path": str(path)})
        return path

    def finalize(self) -> Path:
        path = self.dir / "summary.json"
        path.write_text(json.dumps(self.summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def request_json(
    client: httpx.Client,
    writer: ArtifactWriter,
    name: str,
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    expected_status: int | None = None,
) -> httpx.Response:
    response = client.request(method, url, json=json_body)
    body_text = response.text
    try:
        parsed_body: Any = response.json()
    except ValueError:
        parsed_body = body_text

    artifact = {
        "request": {
            "method": method,
            "url": url,
            "json": json_body,
        },
        "response": {
            "status_code": response.status_code,
            "headers": {
                "content-type": response.headers.get("content-type"),
                "x-trace-id": response.headers.get("x-trace-id"),
            },
            "body": parsed_body,
            "body_text": body_text,
        },
    }
    if expected_status is not None:
        artifact["expected_status"] = expected_status
        artifact["status_matches_expectation"] = response.status_code == expected_status
    writer.write(name, artifact)
    return response


def response_data(response: httpx.Response) -> Any:
    payload = response.json()
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def upsert_system_config(
    client: httpx.Client,
    writer: ArtifactWriter,
    key: str,
    value: str,
    value_type: str = "string",
) -> None:
    url = f"{client.base_url}/system-configs/{key}"
    response = request_json(
        client,
        writer,
        f"system-config-put-{key}",
        "PUT",
        url,
        json_body={"value": value, "value_type": value_type},
    )
    if response.status_code == 404:
        request_json(
            client,
            writer,
            f"system-config-post-{key}",
            "POST",
            f"{client.base_url}/system-configs",
            json_body={
                "key": key,
                "value": value,
                "value_type": value_type,
                "category": "audit",
                "description": "audit-generated config",
                "is_sensitive": False,
            },
            expected_status=201,
        )


def poll_task(
    client: httpx.Client,
    writer: ArtifactWriter,
    task_id: str,
    *,
    timeout_seconds: int = 180,
    scenario_prefix: str,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_detail: dict[str, Any] | None = None
    while time.time() < deadline:
        status_response = request_json(
            client,
            writer,
            f"{scenario_prefix}-task-status-{task_id}",
            "GET",
            f"{client.base_url}/api/v1/tasks/{task_id}/status",
            expected_status=200,
        )
        detail_response = request_json(
            client,
            writer,
            f"{scenario_prefix}-task-detail-{task_id}",
            "GET",
            f"{client.base_url}/api/v1/tasks/{task_id}",
            expected_status=200,
        )
        last_detail = response_data(detail_response)
        if last_detail["status"] in {"completed", "failed"}:
            return last_detail
        time.sleep(2)
    raise RuntimeError(f"task {task_id} polling timed out")


def create_account(
    client: httpx.Client,
    writer: ArtifactWriter,
    scenario: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    suffix = f"{scenario}-{int(time.time())}"
    payload = {
        "name": f"Audit {suffix}",
        "positioning": f"HotClaw audit positioning {suffix}",
        "operation_mode": "semi_auto",
        "auto_run_enabled": False,
        "auto_publish_enabled": False,
        "is_active": True,
        "posting_frequency": "daily",
        "posting_time": "09:00",
    }
    if overrides:
        payload.update(overrides)
    response = request_json(
        client,
        writer,
        f"{scenario}-create-account",
        "POST",
        f"{client.base_url}/api/v1/accounts",
        json_body=payload,
        expected_status=201,
    )
    return response_data(response)


def create_wechat_config(
    client: httpx.Client,
    writer: ArtifactWriter,
    scenario: str,
    account_id: str,
) -> None:
    request_json(
        client,
        writer,
        f"{scenario}-create-wechat-config",
        "POST",
        f"{client.base_url}/api/v1/accounts/{account_id}/wechat-config",
        json_body={
            "app_id": "audit-fake-app-id",
            "app_secret": "audit-fake-app-secret",
            "default_author": "HotClaw Audit",
            "default_thumb_media_id": "audit-thumb-media-id",
            "need_open_comment": True,
            "only_fans_can_comment": False,
            "is_enabled": True,
        },
        expected_status=200,
    )


def patch_scheduler_due(account_id: str) -> None:
    due_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).replace(microsecond=0).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE accounts SET next_run_at = ?, auto_run_enabled = 1, operation_mode = 'semi_auto', posting_frequency = 'daily', posting_time = '09:00', is_active = 1 WHERE id = ?",
            (due_at, account_id),
        )
        conn.execute(
            "UPDATE automation_plans SET next_run_at = ?, is_enabled = 1, plan_type = 'semi_auto', run_strategy = 'scheduled', schedule_type = 'daily' WHERE account_id = ?",
            (due_at, account_id),
        )
        conn.commit()


def run_fake_flow() -> dict[str, Any]:
    scenario = "fake-flow"
    writer = ArtifactWriter(scenario)
    server = BackendServer(port=8145, label=scenario, e2e_mode=True)
    server.start()
    writer.summary["logs"] = {
        "stdout": str(server.out_log),
        "stderr": str(server.err_log),
    }
    try:
        with httpx.Client(base_url=server.base_url, timeout=15.0) as client:
            request_json(client, writer, "health", "GET", f"{client.base_url}/api/v1/health", expected_status=200)
            request_json(client, writer, "list-accounts", "GET", f"{client.base_url}/api/v1/accounts?page=1&page_size=20", expected_status=200)
            request_json(client, writer, "missing-account", "GET", f"{client.base_url}/api/v1/accounts/nonexistent-audit-account", expected_status=404)

            upsert_system_config(client, writer, "e2e_generation_mode", "fake_success")
            upsert_system_config(client, writer, "e2e_generation_failure_message", "Audit fake generation failure")
            upsert_system_config(client, writer, "e2e_publish_mode", "fake_failure")
            upsert_system_config(client, writer, "e2e_publish_failure_message", "Audit fake publish failure")

            account = create_account(client, writer, scenario)
            account_id = account["account_id"]
            writer.summary["ids"]["account_id"] = account_id

            request_json(client, writer, "account-detail", "GET", f"{client.base_url}/api/v1/accounts/{account_id}", expected_status=200)
            run_response = request_json(
                client,
                writer,
                "run-account",
                "POST",
                f"{client.base_url}/api/v1/accounts/{account_id}/run",
                expected_status=200,
            )
            task_id = response_data(run_response)["task_id"]
            writer.summary["ids"]["task_id"] = task_id

            final_task = poll_task(client, writer, task_id, scenario_prefix="fake-flow")
            writer.summary["task_final_status"] = final_task["status"]

            drafts_response = request_json(
                client,
                writer,
                "draft-list",
                "GET",
                f"{client.base_url}/api/v1/drafts?page=1&page_size=50&account_id={account_id}",
                expected_status=200,
            )
            drafts = response_data(drafts_response)["drafts"]
            draft_id = drafts[0]["id"] if drafts else None
            writer.summary["ids"]["draft_id"] = draft_id
            if draft_id is None:
                raise RuntimeError("fake flow did not create a draft")

            request_json(client, writer, "draft-detail", "GET", f"{client.base_url}/api/v1/drafts/{draft_id}", expected_status=200)
            request_json(client, writer, "draft-pending-count", "GET", f"{client.base_url}/api/v1/drafts/pending-count?account_id={account_id}", expected_status=200)
            request_json(client, writer, "confirm-publish", "POST", f"{client.base_url}/api/v1/drafts/{draft_id}/confirm-publish", expected_status=200)
            request_json(client, writer, "confirm-publish-duplicate", "POST", f"{client.base_url}/api/v1/drafts/{draft_id}/confirm-publish", expected_status=500)
            request_json(client, writer, "publish-without-config", "POST", f"{client.base_url}/api/v1/drafts/{draft_id}/publish-to-wechat", expected_status=409)

            create_wechat_config(client, writer, scenario, account_id)
            request_json(
                client,
                writer,
                "wechat-config-detail",
                "GET",
                f"{client.base_url}/api/v1/accounts/{account_id}/wechat-config",
                expected_status=200,
            )
            request_json(
                client,
                writer,
                "wechat-config-test",
                "POST",
                f"{client.base_url}/api/v1/accounts/{account_id}/wechat-config/test",
                expected_status=200,
            )

            publish_fail = request_json(
                client,
                writer,
                "publish-fake-failure",
                "POST",
                f"{client.base_url}/api/v1/drafts/{draft_id}/publish-to-wechat",
                expected_status=502,
            )
            writer.summary["publish_failure_payload"] = response_data(publish_fail)

            records_response = request_json(
                client,
                writer,
                "publish-records-after-failure",
                "GET",
                f"{client.base_url}/api/v1/drafts/{draft_id}/publish-records",
                expected_status=200,
            )
            records = response_data(records_response)["records"]
            writer.summary["ids"]["failed_publish_record_id"] = records[0]["id"] if records else None

            upsert_system_config(client, writer, "e2e_publish_mode", "fake_success")
            retry_response = request_json(
                client,
                writer,
                "retry-publish-fake-success",
                "POST",
                f"{client.base_url}/api/v1/drafts/{draft_id}/retry-publish",
                expected_status=200,
            )
            retry_payload = response_data(retry_response)
            latest_record_id = retry_payload.get("publish_record_id")
            writer.summary["ids"]["retry_publish_record_id"] = latest_record_id

            request_json(
                client,
                writer,
                "draft-wechat-status",
                "GET",
                f"{client.base_url}/api/v1/drafts/{draft_id}/wechat-status",
                expected_status=200,
            )
            if latest_record_id is not None:
                request_json(
                    client,
                    writer,
                    "publish-record-detail",
                    "GET",
                    f"{client.base_url}/api/v1/wechat/publish-records/{latest_record_id}",
                    expected_status=200,
                )
                request_json(
                    client,
                    writer,
                    "publish-record-sync-status",
                    "POST",
                    f"{client.base_url}/api/v1/publish-records/{latest_record_id}/sync-status",
                )

            request_json(
                client,
                writer,
                "final-draft-detail",
                "GET",
                f"{client.base_url}/api/v1/drafts/{draft_id}",
                expected_status=200,
            )
        return writer.summary
    finally:
        server.stop()
        writer.finalize()


def run_real_flow() -> dict[str, Any]:
    scenario = "real-flow"
    writer = ArtifactWriter(scenario)
    server = BackendServer(port=8146, label=scenario, e2e_mode=False)
    server.start()
    writer.summary["logs"] = {
        "stdout": str(server.out_log),
        "stderr": str(server.err_log),
    }
    try:
        with httpx.Client(base_url=server.base_url, timeout=20.0) as client:
            request_json(client, writer, "health", "GET", f"{client.base_url}/api/v1/health", expected_status=200)
            account = create_account(client, writer, scenario)
            account_id = account["account_id"]
            writer.summary["ids"]["account_id"] = account_id
            run_response = request_json(
                client,
                writer,
                "run-account",
                "POST",
                f"{client.base_url}/api/v1/accounts/{account_id}/run",
                expected_status=200,
            )
            task_id = response_data(run_response)["task_id"]
            writer.summary["ids"]["task_id"] = task_id

            final_task = poll_task(client, writer, task_id, scenario_prefix="real-flow", timeout_seconds=240)
            writer.summary["task_final_status"] = final_task["status"]
            writer.summary["task_error_message"] = final_task.get("error_message")

            drafts_response = request_json(
                client,
                writer,
                "draft-list",
                "GET",
                f"{client.base_url}/api/v1/drafts?page=1&page_size=50&account_id={account_id}",
                expected_status=200,
            )
            drafts = response_data(drafts_response)["drafts"]
            if drafts:
                draft_id = drafts[0]["id"]
                writer.summary["ids"]["draft_id"] = draft_id
                request_json(client, writer, "draft-detail", "GET", f"{client.base_url}/api/v1/drafts/{draft_id}", expected_status=200)
            create_wechat_config(client, writer, scenario, account_id)
            request_json(
                client,
                writer,
                "wechat-config-test",
                "POST",
                f"{client.base_url}/api/v1/accounts/{account_id}/wechat-config/test",
                expected_status=200,
            )
        return writer.summary
    finally:
        server.stop()
        writer.finalize()


def run_scheduler_fake_flow() -> dict[str, Any]:
    scenario = "scheduler-fake"
    writer = ArtifactWriter(scenario)
    server = BackendServer(port=8147, label=scenario, e2e_mode=True)
    server.start()
    writer.summary["logs"] = {
        "stdout": str(server.out_log),
        "stderr": str(server.err_log),
    }
    try:
        with httpx.Client(base_url=server.base_url, timeout=20.0) as client:
            request_json(client, writer, "health", "GET", f"{client.base_url}/api/v1/health", expected_status=200)
            upsert_system_config(client, writer, "e2e_generation_mode", "fake_success")
            account = create_account(
                client,
                writer,
                scenario,
                overrides={
                    "operation_mode": "semi_auto",
                    "auto_run_enabled": True,
                    "automation_plan": {
                        "plan_type": "semi_auto",
                        "is_enabled": True,
                        "run_strategy": "scheduled",
                        "schedule_type": "daily",
                        "schedule_config": {"time": "09:00"},
                        "auto_publish_enabled": False,
                        "publish_review_required": True,
                        "timezone": "Asia/Shanghai",
                    },
                },
            )
            account_id = account["account_id"]
            writer.summary["ids"]["account_id"] = account_id
            patch_scheduler_due(account_id)
            writer.write(
                "scheduler-db-patch",
                {
                    "account_id": account_id,
                    "db_path": str(DB_PATH),
                    "patched_next_run_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
                },
            )

            deadline = time.time() + 90
            detected_task: dict[str, Any] | None = None
            while time.time() < deadline:
                tasks_response = request_json(
                    client,
                    writer,
                    "scheduler-task-list",
                    "GET",
                    f"{client.base_url}/api/v1/tasks?page=1&page_size=20&account_id={account_id}",
                    expected_status=200,
                )
                tasks = response_data(tasks_response)["tasks"]
                if tasks:
                    detected_task = tasks[0]
                    break
                time.sleep(5)

            writer.summary["scheduler_task_detected"] = detected_task
            if detected_task is None:
                raise RuntimeError("scheduler did not create a task within 90 seconds")

            task_id = detected_task["task_id"]
            writer.summary["ids"]["task_id"] = task_id
            final_task = poll_task(client, writer, task_id, scenario_prefix="scheduler-fake", timeout_seconds=120)
            writer.summary["task_final_status"] = final_task["status"]

            request_json(
                client,
                writer,
                "scheduler-account-detail",
                "GET",
                f"{client.base_url}/api/v1/accounts/{account_id}",
                expected_status=200,
            )
            request_json(
                client,
                writer,
                "scheduler-drafts",
                "GET",
                f"{client.base_url}/api/v1/drafts?page=1&page_size=50&account_id={account_id}",
                expected_status=200,
            )
        return writer.summary
    finally:
        server.stop()
        writer.finalize()


def main() -> int:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "backend_python": str(BACKEND_PYTHON),
        "db_path": str(DB_PATH),
        "scenarios": {},
    }

    for name, runner in (
        ("fake-flow", run_fake_flow),
        ("real-flow", run_real_flow),
        ("scheduler-fake", run_scheduler_fake_flow),
    ):
        try:
            results["scenarios"][name] = {"status": "completed", "summary": runner()}
        except Exception as exc:  # noqa: BLE001
            results["scenarios"][name] = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }

    summary_path = ARTIFACT_ROOT / "backend-api-audit-summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
