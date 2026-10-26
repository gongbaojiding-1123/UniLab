"""Numerical contracts for the optional offline Genesis diagnostic layer."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from tools.genesis_feasibility.control_diagnostics import force_fraction, ground_contacts


class ContactAndLimitTests(unittest.TestCase):
    def test_asymmetric_limits_and_unbounded_values(self):
        got = force_fraction(np.array([-4., 4., 2.]), [-5., -5., -np.inf], [10., 10., np.inf])
        np.testing.assert_allclose(got[:2], [.8, .4])
        self.assertTrue(np.isnan(got[2]))

    def contacts(self):
        # Second entry is reversed (floor on A), third is invalid capacity,
        # fourth is calf/ground, fifth is foot/self-contact, sixth is near-zero load.
        force_a = np.array([[2., 0., 10.], [0., 0., -20.], [0., 0., 100.],
                            [0., 0., 300.], [0., 0., 400.], [0., 0., .1]])
        return {
            "geom_a": np.array([[1, 0, 3, 8, 4, 3]]),
            "geom_b": np.array([[0, 2, 0, 0, 9, 0]]),
            "valid_mask": np.array([[True, True, False, True, True, True]]),
            "position": np.array([[[0., 1., 0.]] * 6]),
            "force_a": force_a[None], "force_b": -force_a[None],
        }

    def test_geometry_filter_mask_and_pair_direction(self):
        result = ground_contacts(self.contacts(), [1, 2, 3, 4], 0,
                                 np.zeros((4, 3)), np.zeros((4, 3)), np.zeros((4, 3)))
        self.assertEqual(result['FL_ground_fz_n'], 10.)
        self.assertEqual(result['FR_ground_fz_n'], 20.)
        self.assertEqual(result['RL_ground_fz_n'], .1)
        self.assertEqual(result['RL_ground_contact'], 1)
        self.assertEqual(result['RL_loaded_contact'], 0)
        self.assertIsNone(result['RL_loaded_point_speed_xy_m_s'])
        self.assertEqual(result['RR_ground_contact'], 0)
        self.assertIsNone(result['RR_loaded_point_speed_xy_m_s'])

    def test_contact_point_velocity_includes_angular_motion(self):
        velocities = np.zeros((4, 3))
        velocities[0, 0] = 1.
        angular = np.zeros((4, 3))
        angular[0, 2] = 1.
        # omega x (0,1,0) = (-1,0,0): point stays still while origin moves.
        result = ground_contacts(self.contacts(), [1, 2, 3, 4], 0,
                                 np.zeros((4, 3)), velocities, angular)
        self.assertAlmostEqual(result['FL_loaded_point_speed_xy_m_s'], 0.)

    def test_no_contacts_is_missing_speed_not_zero_measurement(self):
        data = {k: np.asarray(v)[:, :0] for k, v in self.contacts().items()}
        result = ground_contacts(data, [1, 2, 3, 4], 0,
                                 np.zeros((4, 3)), np.zeros((4, 3)), np.zeros((4, 3)))
        for leg in ('FL', 'FR', 'RL', 'RR'):
            self.assertEqual(result[f'{leg}_ground_contact'], 0)
            self.assertIsNone(result[f'{leg}_loaded_point_speed_xy_m_s'])


if __name__ == '__main__':
    unittest.main()
