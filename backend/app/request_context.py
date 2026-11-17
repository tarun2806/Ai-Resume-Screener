"""Request-scoped context (correlation ID, actor, org) for logs + audit."""
import contextvars
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)
user_email_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_email", default="")
org_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("org_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(rid: str) -> None:
    request_id_var.set(rid)


def set_actor(user) -> None:
    if user is None:
        return
    user_id_var.set(getattr(user, "id", None))
    user_email_var.set(getattr(user, "email", "") or "")


def set_org(org_id) -> None:
    org_id_var.set(org_id)
