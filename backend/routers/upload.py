import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.schemas import UploadRequest
from services import db
from services import azdo

router = APIRouter()


async def _upload_stream(req: UploadRequest):
    """
    Generator that yields Server-Sent Events (SSE) during the upload process.
    Each event is a JSON object: { type, message, progress }
    """
    cfg = req.config
    testcases = req.testcases
    logs = []

    def event(type_: str, msg: str, progress: int = None) -> str:
        payload = {"type": type_, "message": msg}
        if progress is not None:
            payload["progress"] = progress
        logs.append(f"[{type_.upper()}] {msg}")
        return f"data: {json.dumps(payload)}\n\n"

    suite_id = None
    created_ids = []
    failed = 0

    # ── STEP 1: Fetch suites ─────────────────────────────
    yield event("info", f"Connecting to {cfg.org}/{cfg.project}…", 5)
    try:
        suites = await azdo.fetch_suites(cfg)
        yield event("ok", f"Fetched {len(suites)} suites from plan {cfg.plan_id}", 10)
    except Exception as e:
        yield event("err", f"Failed to fetch suites: {e}", 0)
        yield event("done", "Upload aborted")
        return

    # ── STEP 2: Resolve parent suite ─────────────────────
    try:
        parent_id = await azdo.resolve_parent_suite_id(cfg, suites)
        parent_name = next((s.get("name","") for s in suites if s.get("id") == parent_id), str(parent_id))
        yield event("ok", f"Parent suite resolved: {parent_name} (ID: {parent_id})", 15)
    except Exception as e:
        yield event("err", f"Could not resolve parent suite: {e}", 0)
        yield event("done", "Upload aborted")
        return

    # ── STEP 3: Create requirement suite ─────────────────
    yield event("info", f"Creating requirement suite for story {cfg.story_id}…", 20)
    try:
        suite_id = await azdo.create_requirement_suite(cfg, parent_id, suites)
        yield event("ok", f"Requirement suite ready (ID: {suite_id})", 25)
    except Exception as e:
        yield event("err", f"Failed to create suite: {e}", 0)
        yield event("done", "Upload aborted")
        return

    # ── STEP 4: Resolve state ────────────────────────────
    resolved_state = await azdo.resolve_state(cfg)
    if resolved_state:
        yield event("info", f"Test case state will be set to: \"{resolved_state}\"", 28)
    else:
        yield event("warn", "Could not resolve a valid state — state will be skipped")

    # ── STEP 5: Create test cases ────────────────────────
    total = len(testcases)
    for i, tc in enumerate(testcases):
        pct = 28 + int((i / total) * 52)
        yield event("info", f"Creating [{i+1}/{total}]: {tc.title}…", pct)
        try:
            tc_id, tc_logs = await azdo.create_test_case(cfg, tc, resolved_state)
            created_ids.append(tc_id)
            for line in tc_logs:
                yield event("ok", line)
        except Exception as e:
            failed += 1
            yield event("err", f"Failed: \"{tc.title}\" — {e}")

    yield event("info", f"Created {len(created_ids)}/{total} test cases", 82)

    # ── STEP 6: Link to suite ────────────────────────────
    linked = 0
    for tc_id in created_ids:
        try:
            ok = await azdo.add_test_case_to_suite(cfg, suite_id, tc_id)
            if ok:
                linked += 1
                yield event("ok", f"   Linked TC {tc_id} to suite {suite_id}")
            else:
                yield event("warn", f"   Could not link TC {tc_id}")
        except Exception as e:
            yield event("warn", f"   Link error for TC {tc_id}: {e}")

    yield event("info", f"Linked {linked}/{len(created_ids)} test cases", 98)

    # ── STEP 7: Save history ─────────────────────────────
    status = "success" if failed == 0 else ("partial" if len(created_ids) > 0 else "failed")
    await db.save_upload_history(
        org=cfg.org, project=cfg.project,
        plan_id=cfg.plan_id, story_id=cfg.story_id,
        suite_id=suite_id,
        created=len(created_ids), linked=linked, failed=failed,
        status=status, logs=logs
    )

    yield event("ok",
        f"🎉 Done! {len(created_ids)} created, {linked} linked, {failed} failed. Suite ID: {suite_id}",
        100
    )
    yield event("done", status, 100)


@router.post("/stream")
async def upload_stream(req: UploadRequest):
    """
    Upload test cases to Azure DevOps with real-time SSE progress streaming.
    Connect with: EventSource('/api/upload/stream') after a POST.
    """
    return StreamingResponse(
        _upload_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sync")
async def upload_sync(req: UploadRequest):
    """
    Synchronous upload (no streaming). Returns final result when complete.
    """
    cfg = req.config
    testcases = req.testcases
    logs = []
    suite_id = None
    created_ids = []
    failed = 0

    try:
        suites = await azdo.fetch_suites(cfg)
        logs.append(f"Fetched {len(suites)} suites")
        parent_id = await azdo.resolve_parent_suite_id(cfg, suites)
        logs.append(f"Parent suite: {parent_id}")
        suite_id = await azdo.create_requirement_suite(cfg, parent_id)
        logs.append(f"Suite created: {suite_id}")
        resolved_state = await azdo.resolve_state(cfg)

        for tc in testcases:
            try:
                tc_id, tc_logs = await azdo.create_test_case(cfg, tc, resolved_state)
                created_ids.append(tc_id)
                logs.extend(tc_logs)
            except Exception as e:
                failed += 1
                logs.append(f"❌ Failed: {tc.title} — {e}")

        linked = 0
        for tc_id in created_ids:
            try:
                ok = await azdo.add_test_case_to_suite(cfg, suite_id, tc_id)
                if ok:
                    linked += 1
            except Exception:
                pass

        status = "success" if failed == 0 else ("partial" if created_ids else "failed")
        await db.save_upload_history(
            org=cfg.org, project=cfg.project,
            plan_id=cfg.plan_id, story_id=cfg.story_id,
            suite_id=suite_id,
            created=len(created_ids), linked=linked, failed=failed,
            status=status, logs=logs
        )

        return {
            "success": True,
            "suite_id": suite_id,
            "created": len(created_ids),
            "linked": linked,
            "failed": failed,
            "logs": logs,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "logs": logs}
