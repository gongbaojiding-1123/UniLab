"""Keep the speed-coverage experiment isolated from policy and physics changes."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "rsl_rl"))
from inspect_rma_task import differences, resolved
from unilab_rma.evaluation_diagnostics import FORWARD_TASK, RMA_TASKS, WIDE_SPEED_TASK


class SpeedRangeConfigTests(unittest.TestCase):
    def test_wider_speed_coverage_is_the_only_resolved_change(self):
        baseline, candidate = resolved(FORWARD_TASK), resolved(WIDE_SPEED_TASK)
        self.assertIn(WIDE_SPEED_TASK, RMA_TASKS)
        self.assertEqual(
            differences(baseline, candidate),
            [
                dict(
                    path="env.commands.twist.ranges.lin_vel_x",
                    before=[0.3, 0.6],
                    after=[0.3, 0.8],
                )
            ],
        )
        self.assertEqual(candidate["env"]["actions"]["joint_pos"]["scale"], 0.25)


if __name__ == "__main__":
    unittest.main()
