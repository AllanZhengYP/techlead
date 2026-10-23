from __future__ import annotations

import unittest

from tools.techlead_state.session_identity import (
    SessionIdentityError,
    resolve_provider_session_id,
    resume_command,
)


class SessionIdentityTests(unittest.TestCase):
    def test_claude_code_uuid_is_read_from_tool_environment(self) -> None:
        session_id = "8eeb6c21-cdf4-4ad2-b6bb-271f0d9688ab"
        resolved = resolve_provider_session_id(
            "claude-code",
            None,
            environ={"CLAUDE_CODE_SESSION_ID": session_id},
        )
        self.assertEqual(resolved, session_id)
        self.assertEqual(resume_command("claude-code", resolved), f"claude --resume {session_id}")

    def test_kiro_uuid_produces_exact_resume_command(self) -> None:
        session_id = "f2946a26-3735-4b08-8d05-c928010302d5"
        resolved = resolve_provider_session_id("kiro-cli", session_id, environ={})
        self.assertEqual(resolved, session_id)
        self.assertEqual(
            resume_command("kiro-cli", resolved),
            f"kiro-cli chat --resume-id {session_id}",
        )

    def test_missing_known_provider_id_is_never_generated(self) -> None:
        with self.assertRaisesRegex(SessionIdentityError, "never generates provider session IDs"):
            resolve_provider_session_id("codex", None, environ={})


if __name__ == "__main__":
    unittest.main()
