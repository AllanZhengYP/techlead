"""Provider-owned session identity discovery and validation."""

from __future__ import annotations

from collections.abc import Mapping
import os
import shlex
import uuid


UUID_PROVIDERS = frozenset({"claude", "claude-code", "codex"})
KIRO_PROVIDERS = frozenset({"kiro", "kiro-cli"})

_SESSION_ID_ENV = {
    "claude": "CLAUDE_CODE_SESSION_ID",
    "claude-code": "CLAUDE_CODE_SESSION_ID",
    "codex": "CODEX_THREAD_ID",
}

_DISCOVERY_HINT = {
    "claude": "read CLAUDE_CODE_SESSION_ID from a Claude Code tool subprocess",
    "claude-code": "read CLAUDE_CODE_SESSION_ID from a Claude Code tool subprocess",
    "codex": "read CODEX_THREAD_ID from a Codex tool subprocess or copy the session ID from /status",
    "kiro": "run /session-id in the Kiro CLI session",
    "kiro-cli": "run /session-id in the Kiro CLI session",
}

_RESUME_COMMAND = {
    "claude": "claude --resume {session_id}",
    "claude-code": "claude --resume {session_id}",
    "codex": "codex resume {session_id}",
    "kiro": "kiro-cli chat --resume-id {session_id}",
    "kiro-cli": "kiro-cli chat --resume-id {session_id}",
}


class SessionIdentityError(ValueError):
    """Raised when a real provider session identity cannot be established."""


def resolve_provider_session_id(
    provider: str,
    supplied: str | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve the host's real resumable ID without ever generating one."""

    normalized_provider = provider.strip().lower()
    value = supplied.strip() if supplied is not None else ""
    source = "--provider-session-id"
    if not value:
        variable = _SESSION_ID_ENV.get(normalized_provider)
        environment = os.environ if environ is None else environ
        if variable:
            value = environment.get(variable, "").strip()
            source = variable
    if not value:
        hint = _DISCOVERY_HINT.get(
            normalized_provider,
            "supply the provider's real resumable session identifier",
        )
        raise SessionIdentityError(
            f"cannot determine the current {provider} session ID; {hint}, then pass it with "
            "--provider-session-id. Tech Lead never generates provider session IDs"
        )
    return validate_provider_session_id(provider, value, source=source)


def validate_provider_session_id(provider: str, value: str, *, source: str = "record") -> str:
    """Validate and canonicalize session IDs with provider-defined formats."""

    normalized_provider = provider.strip().lower()
    if normalized_provider not in UUID_PROVIDERS | KIRO_PROVIDERS:
        return value
    uuid_value = value
    if normalized_provider in KIRO_PROVIDERS:
        if not isinstance(value, str) or not value.startswith("sess_"):
            hint = _DISCOVERY_HINT[normalized_provider]
            raise SessionIdentityError(
                f"{source} is not a valid {provider} session ID: {value!r}; "
                f"expected sess_<UUID>; {hint}. Do not use an invented ID or the "
                "internal SES-NNN record ID"
            )
        uuid_value = value.removeprefix("sess_")
    try:
        parsed = uuid.UUID(uuid_value)
    except (AttributeError, TypeError, ValueError) as exc:
        hint = _DISCOVERY_HINT[normalized_provider]
        expected = "sess_<UUID>" if normalized_provider in KIRO_PROVIDERS else "UUID"
        raise SessionIdentityError(
            f"{source} is not a valid {provider} session ID: {value!r}; expected {expected}; {hint}. "
            "Do not use an invented ID or the internal SES-NNN record ID"
        ) from exc
    if parsed.int == 0:
        raise SessionIdentityError(f"{source} must not contain the nil UUID")
    canonical_uuid = str(parsed)
    if normalized_provider in KIRO_PROVIDERS:
        return f"sess_{canonical_uuid}"
    return canonical_uuid


def resume_command(provider: str, provider_session_id: str) -> str | None:
    """Return the provider's explicit resume command when one is known."""

    template = _RESUME_COMMAND.get(provider.strip().lower())
    if template is None:
        return None
    session_id = validate_provider_session_id(provider, provider_session_id)
    return template.format(session_id=shlex.quote(session_id))
