from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_locker import audit as audit_mod


class AuditTestCase(unittest.TestCase):
    def test_write_audit_log_appends_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.log"
            audit_mod.write_audit_log(path, {"id": 1, "reason": "executed"})
            audit_mod.write_audit_log(path, {"id": 2, "reason": "blocked_by_policy"})

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["id"], 1)
            self.assertEqual(json.loads(lines[1])["id"], 2)

    def test_write_audit_log_rotates_when_size_limit_reached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.log"

            with mock.patch.object(audit_mod, "MAX_AUDIT_BYTES", 120), mock.patch.object(
                audit_mod, "ROTATED_AUDIT_FILES", 2
            ):
                for idx in range(20):
                    audit_mod.write_audit_log(path, {"id": idx, "payload": "x" * 30})

            self.assertTrue(path.exists())
            self.assertTrue(path.with_name("audit.log.1").exists())
            self.assertTrue(path.with_name("audit.log.lock").exists())


if __name__ == "__main__":
    unittest.main()
