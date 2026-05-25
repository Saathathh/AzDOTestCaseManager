import base64
import httpx
from urllib.parse import quote
from typing import Optional, List, Tuple
from models.schemas import AzdoConfig, TestCase


# Shared async HTTP client with connection pooling
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=20))
    return _http_client


def _make_headers(pat: str, content_type: str = "application/json") -> dict:
    auth = base64.b64encode(f":{pat}".encode()).decode()
    return {"Content-Type": content_type, "Authorization": f"Basic {auth}"}


def _base_url(cfg: AzdoConfig) -> str:
    project_enc = quote(cfg.project, safe="")
    return f"https://dev.azure.com/{cfg.org}/{project_enc}"


def _steps_xml(steps) -> str:
    xml = f'<steps id="0" last="{len(steps)}">'
    for i, step in enumerate(steps, 1):
        action = str(step.action).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        expected = str(step.expected).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xml += (
            f'<step id="{i}" type="ActionStep">'
            f'<parameterizedString isformatted="true">{action}</parameterizedString>'
            f'<parameterizedString isformatted="true">{expected}</parameterizedString>'
            f'</step>'
        )
    xml += "</steps>"
    return xml


# ── SUITES ──────────────────────────────────────────────

async def fetch_suites(cfg: AzdoConfig) -> list:
    url = f"{_base_url(cfg)}/_apis/testplan/Plans/{cfg.plan_id}/suites?api-version=7.0"
    client = _get_client()
    resp = await client.get(url, headers=_make_headers(cfg.pat))
    resp.raise_for_status()
    return resp.json().get("value", [])


async def resolve_parent_suite_id(cfg: AzdoConfig, suites: list) -> int:
    # Priority: parent_suite_id → parent_suite_name → root suite
    if cfg.parent_suite_id:
        found = next((s for s in suites if s.get("id") == cfg.parent_suite_id), None)
        if found:
            return found["id"]

    if cfg.parent_suite_name:
        found = next(
            (s for s in suites if (s.get("name") or "").strip().lower() == cfg.parent_suite_name.strip().lower()),
            None,
        )
        if found:
            return found["id"]

    root = next((s for s in suites if s.get("parentSuite") is None), None)
    if root:
        return root["id"]

    raise ValueError("Could not resolve a parent suite")


async def create_requirement_suite(cfg: AzdoConfig, parent_suite_id: int, suites: list = None) -> int:
    # Check if a requirement suite for this story already exists
    if suites:
        existing = next(
            (s for s in suites
             if (s.get("suiteType") or "").lower() == "requirementtestsuite"
             and s.get("requirementId") == cfg.story_id),
            None,
        )
        if existing:
            return existing["id"]

    url = f"{_base_url(cfg)}/_apis/testplan/Plans/{cfg.plan_id}/suites?api-version=7.0"
    body = {
        "suiteType": "requirementTestSuite",
        "requirementId": cfg.story_id,
        "parentSuite": {"id": parent_suite_id},
    }
    client = _get_client()
    resp = await client.post(url, headers=_make_headers(cfg.pat), json=body)
    resp.raise_for_status()
    return resp.json()["id"]


# ── TEST CASE STATES ─────────────────────────────────────

async def resolve_state(cfg: AzdoConfig) -> Optional[str]:
    url = f"{_base_url(cfg)}/_apis/wit/workitemtypes/Test%20Case/states?api-version=7.0"
    try:
        client = _get_client()
        resp = await client.get(url, headers=_make_headers(cfg.pat))
        resp.raise_for_status()
        states = [s["name"] for s in resp.json().get("value", [])]
        if cfg.desired_state in states:
            return cfg.desired_state
        ready_like = next((s for s in states if "ready" in s.lower()), None)
        return ready_like
    except Exception:
        return None


# ── TEST CASE CRUD ───────────────────────────────────────

async def create_test_case(cfg: AzdoConfig, tc: TestCase, state: Optional[str] = None) -> Tuple[int, list]:
    """Returns (tc_id, log_lines). Raises on failure."""
    logs = []
    url = f"{_base_url(cfg)}/_apis/wit/workitems/$Test%20Case?api-version=7.0"
    body = [
        {"op": "add", "path": "/fields/System.Title",                   "value": tc.title},
        {"op": "add", "path": "/fields/System.Description",             "value": tc.preconditions or ""},
        {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps",       "value": _steps_xml(tc.steps)},
        {"op": "add", "path": "/fields/System.Tags",                    "value": cfg.tags},
    ]
    client = _get_client()
    resp = await client.post(
        url,
        headers=_make_headers(cfg.pat, "application/json-patch+json"),
        json=body,
    )
    resp.raise_for_status()
    tc_id = resp.json()["id"]
    logs.append(f"✅ Created: \"{tc.title}\" (ID: {tc_id})")

    # Set state
    if state:
        try:
            await _set_state(cfg, tc_id, state)
            logs.append(f"   └─ State set to \"{state}\"")
        except Exception as e:
            logs.append(f"   ⚠️ Could not set state: {e}")

    return tc_id, logs


async def _set_state(cfg: AzdoConfig, tc_id: int, state: str):
    url = f"{_base_url(cfg)}/_apis/wit/workitems/{tc_id}?api-version=7.0"
    body = [{"op": "add", "path": "/fields/System.State", "value": state}]
    client = _get_client()
    resp = await client.patch(
        url,
        headers=_make_headers(cfg.pat, "application/json-patch+json"),
        json=body,
    )
    resp.raise_for_status()


async def add_test_case_to_suite(cfg: AzdoConfig, suite_id: int, tc_id: int) -> bool:
    url = (
        f"{_base_url(cfg)}/_apis/test/plans/{cfg.plan_id}"
        f"/suites/{suite_id}/testcases/{tc_id}?api-version=7.0"
    )
    client = _get_client()
    resp = await client.post(url, headers=_make_headers(cfg.pat))
    return resp.status_code in (200, 201)
