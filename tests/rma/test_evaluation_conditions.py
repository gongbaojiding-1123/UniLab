"""Controlled loads must isolate payload without changing training defaults."""

import sys
import unittest
from pathlib import Path

import torch
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "rsl_rl"))
from inspect_rma_task import differences
from unilab_rma.evaluation_conditions import (
    CONDITIONS,
    condition_overrides,
    condition_parameters,
    validate_labels,
)


def resolved(condition=None):
    with initialize_config_dir(config_dir=str(ROOT / "src/unilab/conf/ppo"), version_base=None):
        cfg = compose(
            config_name="config",
            overrides=["task=go2_joystick_flat/rma_forward"] + condition_overrides(condition),
        )
    return OmegaConf.to_container(cfg, resolve=True)


class EvaluationConditionTests(unittest.TestCase):
    def test_payload_changes_only_mass_distribution(self):
        reference = resolved("nominal")
        for name in ("payload_2p5", "payload_5"):
            mass = CONDITIONS[name][0]
            self.assertEqual(
                differences(reference, resolved(name)),
                [
                    dict(
                        path="env.events.rma_base_load.params.mass_distribution_params",
                        before=[0.0, 0.0],
                        after=[mass, mass],
                    )
                ],
            )

    def test_opt_in_does_not_change_training_ranges(self):
        self.assertEqual(condition_overrides(), [])
        training = resolved()["env"]
        self.assertEqual(training["events"]["rma_friction"]["params"]["ranges"], [0.4, 1.25])
        self.assertEqual(
            training["events"]["rma_base_load"]["params"]["mass_distribution_params"], [0.0, 5.0]
        )
        self.assertEqual(training["commands"]["twist"]["ranges"]["lin_vel_x"], [0.3, 0.6])
        self.assertEqual(training["actions"]["joint_pos"]["scale"], 0.25)
        nominal = resolved("nominal")["env"]
        self.assertFalse(nominal["observations"]["policy"]["enable_corruption"])
        self.assertEqual(nominal["events"]["pd_gains"]["params"]["kd_range"], [0.0, 0.0])
        self.assertTrue(
            all(
                value == [0.0, 0.0]
                for value in nominal["events"]["reset_root_state_uniform"]["params"][
                    "velocity_range"
                ].values()
            )
        )

    def test_derivative_gain_changes_only_kd_and_metadata_matches(self):
        self.assertEqual(
            differences(resolved("nominal"), resolved("kd_0p5")),
            [
                dict(
                    path="env.events.pd_gains.params.kd_range",
                    before=[0.0, 0.0],
                    after=[0.5, 0.5],
                )
            ],
        )
        parameters = condition_parameters("kd_0p5")
        self.assertEqual(parameters["actuator_kd"], 0.5)
        self.assertEqual(parameters["added_base_mass_kg"], 0.0)
        validate_labels(torch.tensor([[1.0, 0.0]]), "kd_0p5")

    def test_legacy_alias_and_conflicting_conditions(self):
        self.assertEqual(condition_overrides(sim2sim_nominal=True), condition_overrides("nominal"))
        with self.assertRaises(ValueError):
            condition_overrides("payload_5", sim2sim_nominal=True)
        with self.assertRaises(ValueError):
            condition_overrides("arbitrary")

    def test_payload_at_fixed_derivative_gain_changes_only_mass(self):
        self.assertEqual(
            differences(resolved("kd_0p5"), resolved("kd_0p5_payload_5")),
            [
                dict(
                    path="env.events.rma_base_load.params.mass_distribution_params",
                    before=[0.0, 0.0],
                    after=[5.0, 5.0],
                )
            ],
        )
        parameters = condition_parameters("kd_0p5_payload_5")
        self.assertEqual(parameters["actuator_kd"], 0.5)
        self.assertEqual(parameters["added_base_mass_kg"], 5.0)
        validate_labels(torch.tensor([[1.0, 5.0]]), "kd_0p5_payload_5")
        with self.assertRaises(ValueError):
            validate_labels(torch.tensor([[1.0, 0.0]]), "kd_0p5_payload_5")

    def test_actual_labels_reject_wrong_or_nonfinite_reset_values(self):
        validate_labels(torch.tensor([[1.0, 5.0], [1.0, 5.0]]), "payload_5")
        for labels in (
            torch.tensor([[1.0, 0.0]]),
            torch.tensor([[0.4, 5.0]]),
            torch.tensor([[1.0, float("nan")]]),
        ):
            with self.assertRaises(ValueError):
                validate_labels(labels, "payload_5")


if __name__ == "__main__":
    unittest.main()
