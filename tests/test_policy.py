import tempfile
import unittest
from pathlib import Path

from agent_locker.policy import Policy, PolicyError, normalize_path


class PolicyTestCase(unittest.TestCase):
    def test_deny_path_blocks_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            deny = tmp_path / "secret"
            policy = Policy.from_dict({"enabled": True, "deny_paths": [str(deny)]})

            inside = deny / "token.txt"
            outside = tmp_path / "public" / "note.txt"

            self.assertTrue(policy.is_denied(inside))
            self.assertFalse(policy.is_denied(outside))

    def test_normalize_relative_path_uses_base_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            result = normalize_path("./a/b", base_dir=tmp_path)
            self.assertEqual(result, (tmp_path / "a" / "b").resolve(strict=False))

    def test_policy_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            first = tmp_path / "one"
            second = tmp_path / "two"
            policy = Policy.from_dict({"enabled": True, "deny_paths": [str(first), str(second)]})
            payload = policy.to_dict()

            self.assertTrue(payload["enabled"])
            self.assertEqual(
                set(payload["deny_paths"]),
                {
                    str(first.resolve(strict=False)),
                    str(second.resolve(strict=False)),
                },
            )

    def test_disabled_policy_allows_blocked_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            deny = tmp_path / "secret"
            policy = Policy.from_dict({"enabled": False, "deny_paths": [str(deny)]})
            inside = deny / "token.txt"
            self.assertFalse(policy.is_denied(inside))

    def test_policy_rejects_non_string_deny_paths_entries(self) -> None:
        with self.assertRaises(PolicyError):
            Policy.from_dict({"enabled": True, "deny_paths": [123]})


if __name__ == "__main__":
    unittest.main()
