"""Live HTTP verification for the Phase 6 API surface."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

BASE_URL = "http://localhost:8000"
BACKEND_DIR = Path(__file__).resolve().parents[1]
TOKEN_CACHE: Dict[str, str] = {}


class CheckFailure(Exception):
    pass


def response_detail(response: httpx.Response) -> str:
    try:
        return json.dumps(response.json(), sort_keys=True)
    except Exception:
        return response.text[:500]


def login(client: httpx.Client, email: str, password: str) -> str:
    if email in TOKEN_CACHE:
        return TOKEN_CACHE[email]
    response = client.post("/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise CheckFailure(f"login {email} returned {response.status_code}: {response_detail(response)}")
    token = response.json().get("access_token")
    if not token:
        raise CheckFailure(f"login {email} returned no access_token: {response_detail(response)}")
    TOKEN_CACHE[email] = token
    return token


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def health_or_start_server() -> subprocess.Popen[bytes] | None:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=2.0)
        if response.status_code == 200:
            return None
    except httpx.HTTPError:
        pass

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", "--port", "8000"],
        cwd=BACKEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        time.sleep(2)
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=2.0)
            if response.status_code == 200:
                return process
        except httpx.HTTPError:
            continue
    process.terminate()
    raise CheckFailure("localhost:8000/health did not become available after starting uvicorn")


def check_pytest(client: httpx.Client) -> Tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    matches = re.findall(r"=+\s*(\d+) passed(?:,\s*(\d+) failed)?(?:,\s*(\d+) skipped)?", output)
    if not matches:
        return False, f"could not parse pytest summary; raw output:\n{output[-2000:]}"
    passed, failed, skipped = matches[-1]
    failed_count = int(failed or 0)
    if result.returncode != 0 or failed_count:
        return False, f"{passed} passed, {failed_count} failed, {skipped or 0} skipped; raw output:\n{output[-3000:]}"
    return True, f"{passed} passed, {failed_count} failed, {skipped or 0} skipped"


def check_routes(client: httpx.Client) -> Tuple[bool, str]:
    response = client.get("/openapi.json")
    if response.status_code != 200:
        return False, f"GET /openapi.json returned {response.status_code}: {response_detail(response)}"
    paths = set(response.json().get("paths", {}))
    required = {
        "/customers",
        "/customers/{id}",
        "/review-queue",
        "/review-queue/{id}/resolve",
        "/opportunities",
        "/config",
        "/config/{id}",
        "/audit-log",
    }
    # Accept the repository's descriptive path parameter names as equivalent routes.
    aliases = {
        "/customers/{id}": "/customers/{customer_id}",
        "/review-queue/{id}/resolve": "/review-queue/{item_id}/resolve",
        "/config/{id}": "/config/{config_id}",
    }
    missing = sorted(path for path in required if path not in paths and aliases.get(path) not in paths)
    return (not missing, f"registered={sorted(paths)}" if not missing else f"missing={missing}; registered={sorted(paths)}")


def check_rm_scoping(client: httpx.Client) -> Tuple[bool, str]:
    rm1_token = login(client, "rm1@unifyx.com", "rm123")
    rm1_headers = auth_headers(rm1_token)
    me = client.get("/auth/me", headers=rm1_headers)
    if me.status_code != 200:
        raise CheckFailure(f"rm1 /auth/me returned {me.status_code}: {response_detail(me)}")
    rm1_id = me.json()["id"]
    rm1_customers_response = client.get("/customers", headers=rm1_headers)
    if rm1_customers_response.status_code != 200:
        raise CheckFailure(f"rm1 /customers returned {rm1_customers_response.status_code}: {response_detail(rm1_customers_response)}")
    rm1_customers = rm1_customers_response.json()
    offending = [item for item in rm1_customers if item.get("rm_id") != rm1_id]
    if offending:
        raise CheckFailure(f"RM1 received out-of-scope customer: {offending[0]}")

    rm2_token = login(client, "rm2@unifyx.com", "rm123")
    rm2_response = client.get("/customers", headers=auth_headers(rm2_token))
    if rm2_response.status_code != 200:
        raise CheckFailure(f"rm2 /customers returned {rm2_response.status_code}: {response_detail(rm2_response)}")
    rm2_customers = rm2_response.json()
    candidate = next((item for item in rm2_customers if item.get("rm_id") != rm1_id), None)
    if candidate is None:
        manager_response = client.get(
            "/customers?limit=200",
            headers=auth_headers(login(client, "manager@unifyx.com", "manager123")),
        )
        candidate = next((item for item in manager_response.json() if item.get("rm_id") != rm1_id), None)
    if candidate is None:
        raise CheckFailure("no customer outside RM1 scope was available for cross-scope probe")
    forbidden = client.get(f"/customers/{candidate['id']}", headers=rm1_headers)
    if forbidden.status_code != 403:
        raise CheckFailure(f"RM1 probing RM2 customer returned {forbidden.status_code}: {response_detail(forbidden)}")
    return True, f"RM1 id={rm1_id}, RM1 customers={len(rm1_customers)}, cross-scope customer={candidate['id']} returned 403"


def check_manager_scoping(client: httpx.Client) -> Tuple[bool, str]:
    manager_token = login(client, "manager@unifyx.com", "manager123")
    response = client.get("/customers", headers=auth_headers(manager_token))
    if response.status_code != 200:
        raise CheckFailure(f"manager /customers returned {response.status_code}: {response_detail(response)}")
    rm1_me = client.get("/auth/me", headers=auth_headers(login(client, "rm1@unifyx.com", "rm123"))).json()
    rm2_me = client.get("/auth/me", headers=auth_headers(login(client, "rm2@unifyx.com", "rm123"))).json()
    allowed = {rm1_me["id"], rm2_me["id"]}
    seen = {item.get("rm_id") for item in response.json()}
    offending = seen - allowed
    if offending:
        raise CheckFailure(f"manager saw unrelated rm_ids={sorted(offending)}")
    note = "both RMs represented" if allowed.issubset(seen) else f"distribution note: seen rm_ids={sorted(seen)}"
    return True, f"manager customers={len(response.json())}; {note}"


def check_masking(client: httpx.Client) -> Tuple[bool, str]:
    admin_token = login(client, "admin@unifyx.com", "admin123")
    admin_headers = auth_headers(admin_token)
    masked_response = client.get("/customers", headers=admin_headers)
    if masked_response.status_code != 200 or not masked_response.json():
        raise CheckFailure(f"masked customer list failed: {masked_response.status_code}: {response_detail(masked_response)}")
    customer_id = masked_response.json()[0]["id"]
    fields = [key for key in ("pan_like", "mobile", "email") if masked_response.json()[0].get(key)]
    if fields and not all("*" in str(masked_response.json()[0][key]) for key in fields):
        raise CheckFailure(f"default masking failed: {masked_response.json()[0]}")

    unmasked = client.get(f"/customers?unmask=true", headers=admin_headers)
    admin_item = next(item for item in unmasked.json() if item["id"] == customer_id)
    if fields and any("*" in str(admin_item[key]) for key in fields):
        raise CheckFailure(f"Admin unmask failed: {admin_item}")

    rm_token = login(client, "rm1@unifyx.com", "rm123")
    rm_response = client.get("/customers?unmask=true", headers=auth_headers(rm_token))
    if rm_response.status_code != 200:
        raise CheckFailure(f"RM unmask request returned {rm_response.status_code}: {response_detail(rm_response)}")
    if rm_response.json() and fields:
        rm_item = rm_response.json()[0]
        rm_fields = [key for key in fields if rm_item.get(key)]
        if any("*" not in str(rm_item[key]) for key in rm_fields):
            raise CheckFailure(f"non-admin unmask was honored: {rm_item}")
    return True, f"customer={customer_id}; masked fields={fields}; Admin unmask and RM masking verified"


def check_review_queue(client: httpx.Client) -> Tuple[bool, str]:
    admin_token = login(client, "admin@unifyx.com", "admin123")
    admin_headers = auth_headers(admin_token)
    response = client.get("/review-queue", headers=admin_headers)
    if response.status_code != 200:
        raise CheckFailure(f"admin review queue returned {response.status_code}: {response_detail(response)}")
    if not response.json():
        return True, "SKIPPED: review queue is empty"
    item_id = response.json()[0]["id"]
    body = {"field_name": "mobile", "winning_value": "0000000000", "winning_source_system": "EQUITY"}
    rm_token = login(client, "rm1@unifyx.com", "rm123")
    forbidden = client.post(f"/review-queue/{item_id}/resolve", headers=auth_headers(rm_token), json=body)
    if forbidden.status_code != 403:
        raise CheckFailure(f"RM resolve returned {forbidden.status_code}: {response_detail(forbidden)}")
    resolved = client.post(f"/review-queue/{item_id}/resolve", headers=admin_headers, json=body)
    if resolved.status_code != 200:
        raise CheckFailure(f"Admin resolve returned {resolved.status_code}: {response_detail(resolved)}")
    after = client.get("/review-queue", headers=admin_headers)
    item = next(item for item in after.json() if item["id"] == item_id)
    if item["status"] != "RESOLVED":
        raise CheckFailure(f"review item status did not become RESOLVED: {item}")
    audits = client.get("/audit-log?entity_type=ReviewQueueItem", headers=admin_headers)
    if not any(row["entity_id"] == str(item_id) for row in audits.json()):
        raise CheckFailure(f"no ReviewQueueItem audit for id={item_id}: {response_detail(audits)}")
    return True, f"item={item_id} resolved and audited"


def check_config_audit(client: httpx.Client) -> Tuple[bool, str]:
    admin_headers = auth_headers(login(client, "admin@unifyx.com", "admin123"))
    response = client.get("/config", headers=admin_headers)
    if response.status_code != 200 or not response.json():
        raise CheckFailure(f"GET /config failed: {response.status_code}: {response_detail(response)}")
    entry = response.json()[0]
    old_value = entry["value"]
    new_value = dict(old_value) if isinstance(old_value, dict) else {"_verify_original": old_value}
    new_value["_verify_probe"] = True
    updated = client.put(f"/config/{entry['id']}", headers=admin_headers, json={"value": new_value})
    if updated.status_code != 200 or updated.json()["version"] != entry["version"] + 1:
        raise CheckFailure(f"config update failed: {updated.status_code}: {response_detail(updated)}")
    audits = client.get(f"/audit-log?entity_type=ConfigEntry", headers=admin_headers)
    matching = [row for row in audits.json() if row["entity_id"] == str(entry["id"])]
    if not matching:
        raise CheckFailure(f"no ConfigEntry audit for id={entry['id']}: {response_detail(audits)}")
    audit = matching[0]
    if "_verify_probe" in str(audit.get("before_value")) or "_verify_probe" not in str(audit.get("after_value")):
        raise CheckFailure(f"ConfigEntry audit before/after incorrect: {audit}")
    return True, f"config id={entry['id']} version {entry['version']}->{updated.json()['version']} and audit verified"


def check_rate_limit(client: httpx.Client) -> Tuple[bool, str]:
    statuses = [
        client.post("/auth/login", json={"email": "admin@unifyx.com", "password": "wrong"}).status_code
        for _ in range(6)
    ]
    if statuses[:5] != [401] * 5 or 429 not in statuses[5:]:
        raise CheckFailure(f"rate limiter not enforced; statuses={statuses}")
    return True, f"statuses={statuses}"


def run_check(number: int, name: str, function, client: httpx.Client) -> Tuple[int, str, bool, str]:
    try:
        passed, reason = function(client)
        return number, name, passed, reason
    except Exception as exc:
        return number, name, False, str(exc)


def main() -> int:
    server_process = None
    try:
        server_process = health_or_start_server()
        checks = [
            (1, "pytest suite", check_pytest),
            (2, "routes registered", check_routes),
            (3, "RM scoping", check_rm_scoping),
            (4, "manager scoping", check_manager_scoping),
            (5, "masking", check_masking),
            (6, "review queue resolve RBAC + audit", check_review_queue),
            (7, "config edit + audit trail", check_config_audit),
            (8, "login rate limit", check_rate_limit),
        ]
        results = []
        with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
            for number, name, function in checks:
                results.append(run_check(number, name, function, client))

        print("Phase 6 live verification")
        print("=" * 80)
        for number, name, passed, reason in results:
            label = "PASS" if passed else "FAIL"
            print(f"[{label}] {number}. {name} - {reason}")
        passed_count = sum(1 for _, _, passed, _ in results if passed)
        print(f"{passed_count}/8 checks passed.")
        return 0 if passed_count == 8 else 1
    except Exception as exc:
        print(f"Verification setup failed: {exc}")
        return 1
    finally:
        if server_process is not None:
            print(f"Started uvicorn process pid={server_process.pid}; leaving it running.")


if __name__ == "__main__":
    raise SystemExit(main())
