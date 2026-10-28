"""Inspect joint targets and measured positions without attributing an unmeasured cause."""

import argparse
import csv
import json
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.input_dir.resolve()
    protocol = json.loads((root / "protocol.json").read_text())
    assert protocol["experiment"] == "EXP-014"
    out = Path(tempfile.mkdtemp(prefix="analysis_", dir=root))
    metrics = []
    fig, axes = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True, sharey=True, constrained_layout=True
    )
    for ax, policy in zip(axes, ("teacher", "student")):
        for condition, mass, shift, color in (
            ("kd_0p5", 0.0, -0.2, "#2563eb"),
            ("kd_0p5_payload_5", 5.0, 0.2, "#d97706"),
        ):
            paths = list((root / f"{condition}_{policy}").glob("eval_*/summary.json"))
            assert len(paths) == 1
            path = paths[0].parent
            config = json.loads((path / "run_config.json").read_text())
            assert config["checkpoint_sha256"] == protocol["checkpoint_sha256"]
            with (path / "transitions.csv").open() as stream:
                transitions = list(csv.DictReader(stream))
            with (path / "control_signals.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            assert len(transitions) == 1000 and len(rows) == 12000
            assert all(
                abs(float(r["added_base_mass_kg"]) - mass) < 1e-5
                and abs(float(r["robot_friction_coeff"]) - 1) < 1e-5
                for r in transitions
            )
            assert all(
                abs(float(r["kp"]) - 35) < 1e-6 and abs(float(r["kd"]) - 0.5) < 1e-6 for r in rows
            )
            assert max(abs(float(r["mapping_residual_rad"])) for r in rows) < 1e-6
            names = list(dict.fromkeys(r["joint"] for r in rows))
            errors = []
            for name in names:
                window = [r for r in rows if r["joint"] == name and int(r["episode_step"]) > 100]
                assert len(window) == 900
                target = np.array([float(r["written_target_rad"]) for r in window])
                measured = np.array([float(r["q_after_rad"]) for r in window])
                action = np.array([float(r["action"]) for r in window])
                rmse = float(np.sqrt(np.mean((target - measured) ** 2)))
                metrics.append(
                    dict(
                        condition=condition,
                        policy=policy,
                        payload_kg=mass,
                        joint=name,
                        samples=len(window),
                        position_error_rmse_rad=rmse,
                        target_std_rad=float(target.std()),
                        measured_std_rad=float(measured.std()),
                        action_near_bound_fraction=float((abs(action) >= 0.95).mean()),
                    )
                )
                errors.append(rmse)
            ax.bar(np.arange(12) + shift, errors, width=0.38, label=f"+{mass:g} kg", color=color)
        ax.set_title(policy)
        ax.set_ylabel("Target vs post-step angle RMSE (rad)")
        ax.grid(axis="y", alpha=0.2)
        ax.legend()
    axes[-1].set_xticks(
        np.arange(12), [n.replace("_joint", "") for n in names], rotation=35, ha="right"
    )
    fig.suptitle(
        "EXP-014: active kp=35, kd=0.5; exclude first 100 steps per episode\nDifferent closed-loop targets/states; these are descriptive errors, NOT torque saturation"
    )
    fig.savefig(out / "joint_tracking_rmse.png", dpi=150)
    plt.close(fig)
    with (out / "metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    (out / "summary.json").write_text(
        json.dumps(
            dict(
                protocol=protocol,
                metrics=metrics,
                limitations="Boundary target vs post-step position; moving targets and closed-loop state distribution differ. No measured torque, substep response or causal attribution.",
            ),
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(dict(analysis=str(out), joint_rows=len(metrics)), indent=2))


if __name__ == "__main__":
    main()
