from __future__ import annotations

import types
import unittest
from unittest import mock

from agent_locker.gui import AgentLockerWindow
from agent_locker.gui import recenter_position_if_offscreen
from agent_locker.gui import resolve_min_window_size
from agent_locker.policy import Policy, normalize_path


class GuiLogicTestCase(unittest.TestCase):
    def test_resolve_min_window_size_uses_required_size_with_padding(self) -> None:
        min_w, min_h = resolve_min_window_size(
            base_min_w=1000,
            base_min_h=700,
            req_w=1080,
            req_h=760,
            screen_w=2000,
            screen_h=1200,
            padding=20,
        )
        self.assertEqual((min_w, min_h), (1100, 780))

    def test_resolve_min_window_size_respects_base_minimum(self) -> None:
        min_w, min_h = resolve_min_window_size(
            base_min_w=1120,
            base_min_h=860,
            req_w=900,
            req_h=700,
            screen_w=2000,
            screen_h=1200,
            padding=20,
        )
        self.assertEqual((min_w, min_h), (1120, 860))

    def test_resolve_min_window_size_clamps_to_screen_ratio_limit(self) -> None:
        min_w, min_h = resolve_min_window_size(
            base_min_w=2000,
            base_min_h=1500,
            req_w=2200,
            req_h=1600,
            screen_w=1400,
            screen_h=900,
            padding=20,
        )
        self.assertEqual((min_w, min_h), (1372, 882))

    def test_recenter_position_if_offscreen_keeps_visible_window(self) -> None:
        recentered = recenter_position_if_offscreen(
            screen_w=1440,
            screen_h=900,
            win_w=1000,
            win_h=700,
            pos_x=100,
            pos_y=80,
        )
        self.assertIsNone(recentered)

    def test_recenter_position_if_offscreen_recenters_when_outside_right_edge(self) -> None:
        recentered = recenter_position_if_offscreen(
            screen_w=1440,
            screen_h=900,
            win_w=1000,
            win_h=700,
            pos_x=1500,
            pos_y=100,
        )
        self.assertEqual(recentered, (220, 100))

    def test_recenter_position_if_offscreen_recenters_when_outside_top_left(self) -> None:
        recentered = recenter_position_if_offscreen(
            screen_w=1440,
            screen_h=900,
            win_w=1000,
            win_h=700,
            pos_x=-980,
            pos_y=-690,
        )
        self.assertEqual(recentered, (220, 100))

    def test_recenter_position_if_offscreen_handles_zero_or_negative_sizes(self) -> None:
        recentered = recenter_position_if_offscreen(
            screen_w=0,
            screen_h=900,
            win_w=1000,
            win_h=700,
            pos_x=0,
            pos_y=0,
        )
        self.assertIsNone(recentered)

    def test_recenter_position_if_offscreen_keeps_window_on_left_monitor(self) -> None:
        recentered = recenter_position_if_offscreen(
            screen_w=3840,
            screen_h=1200,
            win_w=1000,
            win_h=700,
            pos_x=-1600,
            pos_y=100,
            desktop_x=-1920,
            desktop_y=0,
        )
        self.assertIsNone(recentered)

    def test_visible_candidate_normalized_paths_uses_view_only(self) -> None:
        fake = types.SimpleNamespace(_candidate_paths_view=["~/.ssh", "/etc"])

        resolved = AgentLockerWindow._visible_candidate_normalized_paths(fake)

        self.assertEqual(
            resolved,
            [str(normalize_path("~/.ssh")), str(normalize_path("/etc"))],
        )

    def test_add_all_candidates_adds_only_visible_candidates(self) -> None:
        visible = ["~/.ssh", "~/.aws"]
        added_log: list[tuple[str, str]] = []
        fake = types.SimpleNamespace(
            policy=Policy.from_dict({"enabled": True, "deny_paths": [str(normalize_path("~/.ssh"))]}),
            _candidate_paths_view=visible,
            _append_output=lambda text, level="info": added_log.append((level, text)),
            _refresh_candidate_list=mock.Mock(),
            _refresh_deny_list=mock.Mock(),
            _mark_policy_dirty=mock.Mock(),
            _select_deny_path=mock.Mock(),
            _ask_yes_no_dialog=mock.Mock(return_value=True),
            _t=lambda key: {
                "log_candidates_add_nothing": "nothing",
                "candidate_confirm_add_all_title": "confirm-title",
                "candidate_confirm_add_all_body": "count={count}",
                "log_canceled": "canceled",
                "log_candidates_added_all": "added={count}",
            }[key],
        )
        fake._visible_candidate_normalized_paths = lambda: AgentLockerWindow._visible_candidate_normalized_paths(fake)

        AgentLockerWindow.add_all_candidates(fake)

        self.assertEqual(
            fake.policy.deny_paths,
            (normalize_path("~/.aws"), normalize_path("~/.ssh")),
        )
        fake._ask_yes_no_dialog.assert_called_once_with("confirm-title", "count=1")
        fake._refresh_deny_list.assert_called_once()
        fake._mark_policy_dirty.assert_called_once()
        fake._select_deny_path.assert_called_once_with(str(normalize_path("~/.aws")))
        self.assertIn(("info", "added=1"), added_log)

    def test_clear_all_denies_removes_all_after_confirmation(self) -> None:
        paths = [str(normalize_path("~/.ssh")), str(normalize_path("~/.aws"))]
        output_log: list[tuple[str, str]] = []
        fake = types.SimpleNamespace(
            policy=Policy.from_dict({"enabled": True, "deny_paths": paths}),
            _append_output=lambda text, level="info": output_log.append((level, text)),
            _refresh_deny_list=mock.Mock(),
            _mark_policy_dirty=mock.Mock(),
            _ask_yes_no_dialog=mock.Mock(return_value=True),
            _t=lambda key: {
                "log_clear_all_nothing": "nothing",
                "clear_all_confirm_title": "confirm-title",
                "clear_all_confirm_body": "remove={count}",
                "log_canceled": "canceled",
                "log_clear_all_done": "done={count}",
            }[key],
        )

        AgentLockerWindow.clear_all_denies(fake)

        self.assertEqual(fake.policy.deny_paths, ())
        fake._ask_yes_no_dialog.assert_called_once_with("confirm-title", "remove=2")
        fake._refresh_deny_list.assert_called_once()
        fake._mark_policy_dirty.assert_called_once()
        self.assertIn(("info", "done=2"), output_log)

    def test_clear_all_denies_skips_when_no_paths(self) -> None:
        output_log: list[tuple[str, str]] = []
        fake = types.SimpleNamespace(
            policy=Policy.from_dict({"enabled": True, "deny_paths": []}),
            _append_output=lambda text, level="info": output_log.append((level, text)),
            _refresh_deny_list=mock.Mock(),
            _mark_policy_dirty=mock.Mock(),
            _ask_yes_no_dialog=mock.Mock(return_value=True),
            _t=lambda key: {
                "log_clear_all_nothing": "nothing",
                "clear_all_confirm_title": "confirm-title",
                "clear_all_confirm_body": "remove={count}",
                "log_canceled": "canceled",
                "log_clear_all_done": "done={count}",
            }[key],
        )

        AgentLockerWindow.clear_all_denies(fake)

        fake._ask_yes_no_dialog.assert_not_called()
        fake._refresh_deny_list.assert_not_called()
        fake._mark_policy_dirty.assert_not_called()
        self.assertIn(("warn", "nothing"), output_log)

    def test_dialog_helpers_attach_root_as_parent(self) -> None:
        fake = types.SimpleNamespace(root="ROOT")

        with mock.patch("agent_locker.gui.messagebox.askyesno", return_value=True) as ask_yes_no:
            result = AgentLockerWindow._ask_yes_no_dialog(fake, "title", "body")
        self.assertTrue(result)
        ask_yes_no.assert_called_once_with("title", "body", parent="ROOT")

        with mock.patch("agent_locker.gui.filedialog.askdirectory", return_value="/tmp/x") as ask_dir:
            selected_dir = AgentLockerWindow._ask_directory_dialog(fake, title="pick")
        self.assertEqual(selected_dir, "/tmp/x")
        ask_dir.assert_called_once_with(parent="ROOT", title="pick")

        with mock.patch("agent_locker.gui.filedialog.askopenfilename", return_value="/tmp/f") as ask_file:
            selected_file = AgentLockerWindow._ask_file_dialog(fake, title="pick")
        self.assertEqual(selected_file, "/tmp/f")
        ask_file.assert_called_once_with(parent="ROOT", title="pick")


if __name__ == "__main__":
    unittest.main()
