"""Select config-owned evaluation conditions and validate actual reset labels."""

import torch

# Values are (added mass kg, active derivative gain); YAML owns simulation config.
CONDITIONS = {
    "nominal": (0.0, 0.0),
    "payload_2p5": (2.5, 0.0),
    "payload_5": (5.0, 0.0),
    "kd_0p5": (0.0, 0.5),
    "kd_0p5_payload_5": (5.0, 0.5),
}


def condition_overrides(condition=None, *, sim2sim_nominal=False):
    if condition is not None and sim2sim_nominal:
        raise ValueError("Choose --eval-condition or --sim2sim-nominal, not both")
    name = "nominal" if sim2sim_nominal else condition
    if name is None:
        return []
    if name not in CONDITIONS:
        raise ValueError(f"Unknown evaluation condition: {name}")
    return [f"+rma_eval={name}"]


def validate_labels(privileged, condition):
    """Labels are samples written by existing RMA reset events, not guessed config values."""
    expected = privileged.new_tensor([1.0, CONDITIONS[condition][0]])
    if (
        privileged.ndim != 2
        or privileged.shape[1] != 2
        or not torch.allclose(privileged, expected.expand_as(privileged), atol=1e-5, rtol=0)
    ):
        raise ValueError(f"Actual friction/payload labels do not match {condition}")


def condition_parameters(condition):
    return dict(
        actuator_kp=35.0,
        actuator_kd=CONDITIONS[condition][1],
        robot_sliding_friction=1.0,
        added_base_mass_kg=CONDITIONS[condition][0],
        initial_episode_counter=0,
        observation_noise=False,
        note="Configured gains; friction/payload reset labels checked separately. Not measured torque.",
    )
