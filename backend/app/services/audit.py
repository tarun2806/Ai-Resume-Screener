"""Secure audit event recording.

Rules enforced here:
- metadata is sanitized: keys containing password/token/secret/content
  are dropped; values are truncated; payload capped at ~2KB.
- actor identity comes from the authenticated user object, never client input.
- request_id comes from the request context var.
"""
import json
import logging

from app.db import AuditEvent, utcnow
from app.request_context import org_id_var, request_id_var, user_email_var, user_id_var

log = logging.getLogger("ai-screenx.audit")

MAX_META_BYTES = 2048
_DROP_KEYS = ("password", "token", "secret", "authorization", "resume_text",
              "match_result", "parsed_profile", "content", "file")


def _sanitize_meta(metadata: dict | None) -> str:
    if not metadata:
        return "{}"
    clean = {}
    for k, v in metadata.items():
        kl = str(k).lower()
        if any(d in kl for d in _DROP_KEYS):
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            clean[k] = v if not isinstance(v, str) else v[:200]
        else:
            clean[k] = str(v)[:200]
    out = json.dumps(clean, default=str)
    if len(out) > MAX_META_BYTES:
        out = json.dumps({"truncated": True})
    return out


def record(db, *, action: str, actor=None, organization_id=None,
           resource_type: str = "", resource_id="",
           outcome: str = "success", metadata: dict | None = None) -> AuditEvent:
    """Append an audit event. Best-effort: never raises into request path."""
    try:
        if actor is None:
            actor_id = user_id_var.get()
            actor_email = user_email_var.get()
        else:
            actor_id = getattr(actor, "id", None)
            actor_email = getattr(actor, "email", "") or ""
        if organization_id is None:
            organization_id = org_id_var.get()
        ev = AuditEvent(
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email[:255],
            action=action[:60],
            resource_type=resource_type[:40],
            resource_id=str(resource_id)[:64],
            outcome=outcome,
            request_id=request_id_var.get()[:64],
            metadata_json=_sanitize_meta(metadata),
        )
        db.add(ev)
        return ev
    except Exception:
        log.exception("audit record failed for action=%s", action)
        return None
