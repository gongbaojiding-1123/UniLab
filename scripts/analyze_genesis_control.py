"""Offline analysis of the optional Genesis control/contact sidecar; no simulation."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from tools.genesis_feasibility.control_diagnostics import JOINTS, LEGS


def load(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"Empty CSV: {path}")
    return rows


def values(rows, name):
    return np.array([float(row[name]) if row[name] else np.nan for row in rows])


def summarize(trace, control, metadata):
    if not metadata["complete"]:
        raise ValueError("Control sidecar is incomplete")
    nsub = metadata["physics_steps_per_action"]
    if len(control) != len(trace) * nsub or len(control) != metadata["rows"]:
        raise ValueError("Replay and physics-step row counts do not match")
    for i, row in enumerate(control):
        parent = trace[i // nsub]
        if (int(row["policy_step"]) != int(parent["policy_step"])
                or int(row["substep"]) != i % nsub + 1
                or row["episode"] != parent["episode"]
                or row["episode_step"] != parent["episode_step"]):
            raise ValueError("Sidecar timing or episode IDs do not match replay")
    t = values(trace, "sim_time_s")
    vx = values(trace, "vx_m_s")
    command = metadata["command"][0]
    joint_summary = {}
    for name in JOINTS:
        error = values(control, f"{name}_error_post_rad")
        limit = values(control, f"{name}_control_pre_limit_fraction")
        demand = values(control, f"{name}_pd_demand_pre_estimate_nm")
        i = JOINTS.index(name)
        q_pre = values(control, f"{name}_q_pre_rad")
        q_post = values(control, f"{name}_q_post_rad")
        # Test temporal continuity of actual recorded states across substeps.
        valid = np.array([control[k]["episode"] == control[k + 1]["episode"]
                          for k in range(len(control) - 1)])
        if np.any(np.abs(q_post[:-1][valid] - q_pre[1:][valid]) > 1e-5):
            raise ValueError(f"State discontinuity without reset for {name}")
        joint_summary[name] = {
            "post_error_rmse_rad": float(np.sqrt(np.mean(error ** 2))),
            "max_abs_post_error_rad": float(np.max(np.abs(error))),
            "max_control_pre_limit_fraction": float(np.nanmax(limit)),
            "control_pre_near_limit_fraction_ge_0_95": float(np.mean(limit >= .95)),
            "pd_estimate_outside_limits_fraction": float(np.mean(
                (demand < metadata["force_lower_nm"][i]) | (demand > metadata["force_upper_nm"][i])
            )),
        }
    contacts = {}
    for leg in LEGS:
        speed = values(control, f"{leg}_loaded_point_speed_xy_m_s")
        finite = speed[np.isfinite(speed)]
        contacts[leg] = {
            "ground_contact_fraction": float(np.mean(values(control, f"{leg}_ground_contact"))),
            "loaded_contact_fraction": float(np.mean(values(control, f"{leg}_loaded_contact"))),
            "loaded_point_speed_mean_m_s": float(finite.mean()) if finite.size else None,
            "loaded_point_speed_p95_m_s": float(np.quantile(finite, .95)) if finite.size else None,
        }
    def event(idx):
        parent = trace[idx]
        substeps = control[idx * nsub:(idx + 1) * nsub]
        ratios = [float(row[f"{name}_control_pre_limit_fraction"])
                  for row in substeps for name in JOINTS
                  if row[f"{name}_control_pre_limit_fraction"]]
        return {
            "minimum_time_s": float(t[idx]),
            "vx_m_s": float(vx[idx]), "tilt_deg": float(parent["tilt_deg"]),
            "RR_calf_action": float(parent["action_11"]),
            "max_control_limit_fraction_in_action": max(ratios),
            "RR_calf_post_errors_rad": [float(row["RR_calf_error_post_rad"]) for row in substeps],
            "loaded_legs_by_substep": [[leg for leg in LEGS if row[f"{leg}_loaded_contact"] == "1"]
                                       for row in substeps],
            "loaded_point_speed_xy_by_substep": [{leg: (float(row[f"{leg}_loaded_point_speed_xy_m_s"])
                                                        if row[f"{leg}_loaded_point_speed_xy_m_s"] else None)
                                                     for leg in LEGS} for row in substeps],
        }
    windows = []
    for lo, hi in ((2.5, 3.5), (9.5, 10.1), (11.5, 12.1)):
        indices = np.flatnonzero((t >= lo) & (t <= hi))
        if indices.size:
            idx = int(indices[np.argmin(vx[indices])])
            windows.append(dict(reference_window_s=[lo, hi], **event(idx)))
    selected = []
    for idx in np.argsort(vx):
        if t[idx] < 2 or vx[idx] >= .2:
            continue
        if all(abs(t[idx] - t[previous]) >= .5 for previous in selected):
            selected.append(int(idx))
        if len(selected) == 3:
            break
    return {
        "replay_rows": len(trace), "control_rows": len(control),
        "mean_vx_m_s": float(vx.mean()), "vx_rmse_m_s": float(np.sqrt(np.mean((vx - command) ** 2))),
        "bad_orientation_resets": sum(row["reset_reason"] == "bad_orientation" for row in trace),
        "timeouts": sum(row["reset_reason"] == "time_out" for row in trace),
        "joints": joint_summary, "contacts": contacts, "reference_windows": windows,
        "detected_low_speed_events": [event(i) for i in sorted(selected)],
        "event_selection": "Three lowest vx samples after 2 s with vx <0.2 m/s, separated by at least 0.5 s; descriptive events, not independent statistical trials",
        "interpretation": "Contact-point speed and action-bound proximity are indicators, not causal proof. Control force is a pre-step API computation, not measured motor torque. Generalized internal force is not isolated actuator torque. Fixed reference windows may shift between GPU runs.",
    }


def plot(trace, control, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = values(trace, "sim_time_s")
    tc = values(control, "sim_time_s")
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True, constrained_layout=True)
    axes[0].plot(t, values(trace, "vx_m_s"), lw=1)
    axes[0].axhline(.5, color="black", ls="--", label="command 0.5 m/s")
    axes[0].legend()
    axes[0].set_ylabel("vx (m/s)")
    axes[1].plot(t, values(trace, "tilt_deg"), lw=1)
    axes[1].set_ylabel("tilt (deg)")
    image = np.array([values(control, f"{leg}_loaded_contact") for leg in LEGS])
    axes[2].imshow(image, aspect="auto", interpolation="nearest", origin="lower",
                   extent=[tc[0] - .005, tc[-1] + .005, -.5, 3.5], vmin=0, vmax=1, cmap="Blues")
    axes[2].set_yticks(range(4), LEGS)
    axes[2].set_ylabel("loaded foot (>1 N)")
    for leg in LEGS:
        axes[3].plot(tc, values(control, f"{leg}_loaded_point_speed_xy_m_s"), lw=.7, label=leg)
    axes[3].legend(ncol=4)
    axes[3].set_ylabel("contact point xy\nspeed (m/s)")
    axes[3].set_xlabel("simulation time (s)")
    for ax in axes:
        for lo, hi in ((2.5, 3.5), (9.5, 10.1), (11.5, 12.1)):
            ax.axvspan(lo, hi, color="orange", alpha=.10)
    fig.suptitle("Genesis diagnostic replay; shaded bands are reference slowdown windows")
    fig.savefig(output / "contact_and_velocity.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(4, 3, figsize=(15, 10), sharex=True, constrained_layout=True)
    for name, ax in zip(JOINTS, axes.flat, strict=True):
        ax.plot(tc, values(control, f"{name}_target_rad"), lw=.7, label="command target")
        ax.plot(tc, values(control, f"{name}_q_post_rad"), lw=.7, label="post-step actual")
        ax.set_title(name)
        ax.set_ylabel("angle (rad)")
    axes[0, 0].legend(fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("simulation time (s)")
    fig.savefig(output / "joint_tracking.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, constrained_layout=True)
    for ax, field, label, vmax in zip(axes, ("action", "control_pre_limit_fraction", "error_post_rad"),
                                     ("|normalized action|", "computed control / signed force limit", "|post-step angle error| (rad)"),
                                     (1., 1., None), strict=True):
        data = np.abs(np.array([values(control, f"{name}_{field}") for name in JOINTS]))
        img = ax.imshow(data, aspect="auto", interpolation="nearest", origin="lower",
                        extent=[tc[0] - .005, tc[-1] + .005, -.5, 11.5], vmin=0, vmax=vmax)
        ax.set_yticks(range(12), JOINTS, fontsize=8)
        fig.colorbar(img, ax=ax, label=label)
    axes[-1].set_xlabel("simulation time (s)")
    fig.suptitle("Action magnitude is NOT the same as actuator force saturation")
    fig.savefig(output / "action_and_control.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Primary replay CSV, not the .control.csv sidecar")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    control_path = args.trace.with_suffix(".control.csv")
    metadata = json.loads(args.trace.with_suffix(".control.json").read_text())
    trace, control = load(args.trace), load(control_path)
    summary = summarize(trace, control, metadata)
    output = args.output_dir or args.trace.parent / (args.trace.stem + "_analysis")
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    plot(trace, control, output)
    print(json.dumps(summary, indent=2, allow_nan=False))
    print(f"Saved summary and 3 figures: {output.resolve()}")


if __name__ == "__main__":
    main()
