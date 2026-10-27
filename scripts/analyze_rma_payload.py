"""Recompute EXP-011 metrics and plots from the six controlled-load traces."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main(
    *,
    experiment="EXP-011",
    cases=(("nominal", 0.0, 0.0), ("payload_2p5", 2.5, 0.0), ("payload_5", 5.0, 0.0)),
    figure_name="payload_velocity.png",
):
    parser = argparse.ArgumentParser(
        description=f"{experiment}: recompute controlled evaluation metrics"
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.input_dir.resolve()
    protocol = json.loads((root / "protocol.json").read_text())
    # Analysis gets a unique output too; never overwrite an earlier interpretation.
    import tempfile

    out = Path(tempfile.mkdtemp(prefix="analysis_", dir=root))
    metrics = []
    assert protocol["experiment"] == experiment
    assert protocol["cases"] == [case[0] for case in cases]
    fig, axes = plt.subplots(len(cases), 1, figsize=(12, 3 * len(cases)), sharex=True)
    for ax, (condition, mass, kd) in zip(np.atleast_1d(axes), cases):
        for policy, color in (("teacher", "#2563eb"), ("student", "#d97706")):
            paths = list((root / f"{condition}_{policy}").glob("eval_*/summary.json"))
            if len(paths) != 1:
                raise ValueError(f"Expected one completed evaluation: {condition}/{policy}")
            path = paths[0]
            report = json.loads(path.read_text())
            metadata = json.loads((path.parent / "run_config.json").read_text())
            assert metadata["checkpoint_sha256"] == protocol["checkpoint_sha256"]
            assert metadata["arguments"]["eval_condition"] == condition
            assert report["policy"] == policy
            assert report["controlled_parameters"]["actuator_kd"] == kd
            assert metadata["control_period_s"] == 0.02
            with (path.parent / "transitions.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            assert len(rows) == protocol["steps"]
            assert all(
                abs(float(r["added_base_mass_kg"]) - mass) < 1e-5
                and abs(float(r["robot_friction_coeff"]) - 1.0) < 1e-5
                for r in rows
            )
            vx = np.array([float(r["before_vx_m_s"]) for r in rows])
            vy = np.array([float(r["before_vy_m_s"]) for r in rows])
            commands = np.array([float(r["command_vx_m_s"]) for r in rows])
            assert np.isfinite([*vx, *vy]).all() and np.allclose(commands, 0.7)
            ended = np.array([int(r["terminated"]) for r in rows], dtype=bool)
            timeouts = sum(int(r["truncated"]) for r in rows)
            full_rmse = float(np.sqrt(np.mean((vx - commands) ** 2 + vy**2)))
            assert abs(full_rmse - report["planar_velocity_rmse_m_per_s"]) < 1e-6
            assert int(ended.sum()) == report["terminations"]
            window = np.array([int(r["after_startup_window"]) for r in rows], dtype=bool)
            actions = np.array([[float(r[f"action_{i}"]) for i in range(12)] for r in rows])
            result = dict(
                condition=condition,
                payload_kg=mass,
                actuator_kd=kd,
                policy=policy,
                steps=len(rows),
                mean_vx=float(vx.mean()),
                planar_rmse=full_rmse,
                terminations=int(ended.sum()),
                truncations=timeouts,
                window_steps=int(window.sum()),
                window_mean_vx=float(vx[window].mean()) if window.any() else None,
                window_planar_rmse=float(
                    np.sqrt(np.mean((vx[window] - commands[window]) ** 2 + vy[window] ** 2))
                )
                if window.any()
                else None,
                action_near_bound_fraction=float((abs(actions) >= 0.95).mean()),
                student_action_rmse_vs_teacher=report["student_action_rmse_vs_teacher"],
                student_latent_mse_vs_teacher=report["student_latent_mse_vs_teacher"],
                trace=str(path.parent),
            )
            metrics.append(result)
            times = np.arange(len(rows)) * 0.02
            ax.plot(times, vx, color=color, linewidth=1, label=policy)
            if ended.any():
                ax.scatter(times[ended], vx[ended], color=color, marker="x", s=50)
        ax.axhline(0.7, color="black", linestyle="--", label="command 0.7 m/s")
        ax.set_ylabel((f"+{mass} kg" if experiment == "EXP-011" else f"kd={kd}") + "\nvx (m/s)")
        ax.grid(alpha=0.2)
        ax.legend(loc="upper right", ncol=3)
    axes[-1].set_xlabel("Global evaluation time (s), across resets")
    fig.suptitle(
        f"{experiment}: same frozen teacher/student pair, seed {protocol['seed']}\n"
        "Home reset, friction 1, no observation noise; x = termination"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out / figure_name, dpi=150)
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
                limits="Deterministic one-seed condition screen, not a robustness or causal mechanism proof; action bounds are not measured torque limits",
            ),
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(dict(analysis=str(out), metrics=metrics), indent=2))


if __name__ == "__main__":
    main()
