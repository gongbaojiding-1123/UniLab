"""Archive the recorded EXP-010 sessions; read artifacts without rerunning physics."""

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Explicit sessions avoid silently selecting an unrelated repeat of the experiment.
TEACHERS = "evaluations/three_seeds_20261027_195658"
STUDENT = "evaluations/student_wide_speed_20261027_203430"
RANDOMIZED = "evaluations/student_wide_speed_robust_20261027_204527"
GENESIS = "genesis/20261027_210733"
DEPLOY = "deployment/20261027_212144"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_report(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return json.JSONDecoder().raw_decode(text[text.index("{\n") :])[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.run_dir.resolve(), args.output.resolve()
    if out.exists():
        parser.error(f"Archive already exists; choose a new --output: {out}")
    if root in out.parents or root == out:
        parser.error("Archive output must be outside the raw run directory")
    for session in (TEACHERS, STUDENT, RANDOMIZED, GENESIS, DEPLOY):
        if not (root / session).is_dir():
            parser.error(f"Missing recorded session: {root / session}")
    out.mkdir(parents=True)
    manifest, metrics, curves = [], [], {}

    def track(path, archived=None, role="recorded_input"):
        manifest.append(
            dict(
                source=str(path),
                sha256=sha256(path),
                bytes=path.stat().st_size,
                archived=archived,
                role=role,
            )
        )

    def copy(path, relative, *, compress=False, role="recorded_input"):
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if compress:
            # Deterministic gzip header, original bytes unchanged after decompression.
            with path.open("rb") as source, destination.open("wb") as target:
                with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as zipped:
                    shutil.copyfileobj(source, zipped)
            with gzip.open(destination, "rb") as stream:
                assert hashlib.sha256(stream.read()).hexdigest() == sha256(path)
        else:
            shutil.copyfile(path, destination)
        track(path, str(relative), role)

    def add_metric(label, engine, condition, group, seed, goal, rows, report):
        if engine == "mujoco":
            vx = np.array([float(r["before_vx_m_s"]) for r in rows])
            vy = np.array([float(r["before_vy_m_s"]) for r in rows])
            wz = np.array([float(r["before_wz_rad_s"]) for r in rows])
            # time_s restarts at each reset; step is the global evaluation index.
            times = np.array([int(r["step"]) * 0.02 for r in rows])
            ended = [i for i, r in enumerate(rows) if int(r["terminated"])]
            timeouts = sum(int(r["truncated"]) for r in rows)
            reference = report["planar_velocity_rmse_m_per_s"]
        else:
            vx = np.array([float(r["vx_m_s"]) for r in rows])
            vy = np.array([float(r["vy_m_s"]) for r in rows])
            wz = np.array([float(r["yaw_rate_rad_s"]) for r in rows])
            times = np.array([float(r["sim_time_s"]) for r in rows])
            ended = [i for i, r in enumerate(rows) if r["reset_reason"] == "bad_orientation"]
            timeouts = sum(r["reset_reason"] == "time_out" for r in rows)
            reference = report["planar_velocity_rmse_m_s"]
        rmse = float(np.sqrt(np.mean((vx - goal) ** 2 + vy**2)))
        if len(rows) != 1000 or not np.isfinite([*vx, *vy, *wz]).all():
            raise ValueError(f"Incomplete or nonfinite trace: {label}")
        if not math.isclose(rmse, reference, abs_tol=1e-6):
            raise ValueError(f"Trace/report RMSE mismatch: {label}")
        metrics.append(
            dict(
                label=label,
                engine=engine,
                condition=condition,
                group=group,
                seed=seed,
                target_vx=goal,
                steps=len(rows),
                mean_vx=float(vx.mean()),
                mean_vy=float(vy.mean()),
                planar_rmse=rmse,
                mean_abs_yaw=float(np.abs(wz).mean()),
                terminations=len(ended),
                truncations=timeouts,
            )
        )
        curves[label] = times, vx, ended

    reports = []
    for session, condition, policy in (
        (TEACHERS, "nominal", "teacher"),
        (STUDENT, "nominal", "student"),
        (RANDOMIZED, "randomized", "student"),
        (DEPLOY + "/evaluation", "nominal", "tensorrt"),
    ):
        paths = sorted((root / session).glob("*/eval_*/summary.json"))
        if policy == "tensorrt":
            paths = sorted((root / session).glob("eval_*/summary.json"))
        expected = 18 if policy == "teacher" else (1 if policy == "tensorrt" else 3)
        if len(paths) != expected:
            raise ValueError(f"Expected {expected} reports in {session}, got {len(paths)}")
        for p in paths:
            report = json.loads(p.read_text())
            arguments = json.loads((p.parent / "run_config.json").read_text())["arguments"]
            group = p.parent.parent.name.split("_vx")[0] if policy == "teacher" else policy
            seed, goal = int(report["seed"]), float(report["command_override"][0])
            label = f"mujoco_{policy}_{group}_{condition}_vx{goal}_seed{seed}"
            rows = read_rows(p.parent / "transitions.csv")
            add_metric(label, "mujoco", condition, group, seed, goal, rows, report)
            reports.append(dict(label=label, arguments=arguments, summary=report))
            for f in sorted(p.parent.rglob("*")):
                if f.is_file() and f.suffix in (".csv", ".json", ".yaml"):
                    relative = Path("evaluations") / label / f.relative_to(p.parent)
                    if relative.name == "run_config.json":
                        relative = relative.with_name("run_configuration.json")
                    copy(
                        f,
                        str(relative) + ".gz" if f.suffix == ".csv" else relative,
                        compress=f.suffix == ".csv",
                    )

    for p in sorted((root / GENESIS).glob("vx*.csv")):
        goal = float(p.stem.split("_seed")[0][2:])
        seed = int(p.stem.split("_seed")[1])
        report = read_report(p.with_suffix(".log"))
        label = f"genesis_student_nominal_vx{goal}_seed{seed}"
        add_metric(label, "genesis", "nominal", "student", seed, goal, read_rows(p), report)
        reports.append(dict(label=label, summary=report))
        copy(p, Path("genesis") / (p.name + ".gz"), compress=True)
        copy(p.with_suffix(".log"), Path("genesis") / (p.stem + ".txt"))
    if len(metrics) != 34:
        raise ValueError(f"Expected 34 recorded runs, got {len(metrics)}")

    for p in sorted((root / "logs").glob("*/*/*")):
        if p.name in ("metrics.csv", "run_config.json"):
            relative = Path("training") / p.relative_to(root / "logs")
            if relative.name == "run_config.json":
                relative = relative.with_name("run_configuration.json")
            copy(p, relative)
    for p in sorted((root / DEPLOY).glob("*.log")):
        copy(p, Path("deployment") / (p.stem + ".txt"))
    copy(root / "student_wide_speed.json", "deployment/onnx_metadata.json")
    for pattern in ("*.pt", "*.onnx", DEPLOY + "/*.engine"):
        for p in sorted(root.glob(pattern)):
            track(p, role="local_model_not_copied")
    project = root.parents[3]
    for name in (
        "scripts/train_rma.py",
        "scripts/evaluate_rma.py",
        "scripts/export_onnx.py",
        "scripts/sim2sim_genesis_go2.py",
        "scripts/run_genesis_go2.sh",
        "rsl_rl/unilab_rma/runner.py",
        "rsl_rl/unilab_rma/ppo.py",
        "rsl_rl/unilab_rma/actor_critic_rma.py",
        "rsl_rl/unilab_rma/adaptation_module.py",
        "deploy_cpp/src/main_control_loop.cpp",
        "deploy_cpp/include/DoubleBuffer.hpp",
    ):
        p = project / name
        if p.exists():
            copy(p, Path("source_at_archive") / name, role="current_source_not_historical_proof")
    for p in sorted((project / "src/unilab/conf/ppo/task/go2_joystick_flat").glob("*.yaml")):
        copy(
            p, Path("source_at_archive/config") / p.name, role="current_source_not_historical_proof"
        )
    for name in ("scene_flat.xml", "go2.xml"):
        p = project / "src/unilab/assets/robots/go2" / name
        track(p, role="current_asset_hash_not_historical_proof")

    plots = out / "plots"
    plots.mkdir()
    colors = {"baseline": "#be3b37", "wide_speed": "#007c83", "student": "#3859a8"}
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), layout="constrained")
    for ax, goal in zip(axes, (0.3, 0.5, 0.7), strict=True):
        ax.axhline(goal, color="black", ls="--", lw=1, label="Command")
        for group in ("baseline", "wide_speed"):
            times, vx, ends = curves[f"mujoco_teacher_{group}_nominal_vx{goal}_seed123"]
            ax.plot(times, vx, color=colors[group], lw=1, label=group)
            ax.scatter(times[ends], vx[ends], color=colors[group], marker="x", s=45)
        ax.set(title=f"Teacher command {goal} m/s; x = termination", ylabel="Body vx (m/s)")
        ax.grid(alpha=0.2)
        ax.legend(loc="upper right", ncol=3)
    axes[-1].set_xlabel("Evaluation time (s), including resets")
    fig.savefig(plots / "teacher_speed_comparison.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), layout="constrained")
    for ax, goal in zip(axes, (0.3, 0.5, 0.7), strict=True):
        ax.axhline(goal, color="black", ls="--", lw=1, label="Command")
        for label, display, color in (
            (f"mujoco_student_student_nominal_vx{goal}_seed123", "MuJoCo", "#3859a8"),
            (f"genesis_student_nominal_vx{goal}_seed123", "Genesis", "#007c83"),
        ):
            times, vx, _ = curves[label]
            ax.plot(times, vx, label=display, color=color, lw=1)
        ax.set(title=f"Frozen student, nominal, seed 123: {goal} m/s", ylabel="Body vx (m/s)")
        ax.grid(alpha=0.2)
        ax.legend(loc="upper right", ncol=3)
    axes[-1].set_xlabel("Evaluation time (s); MuJoCo before-step / Genesis after-step samples")
    fig.savefig(plots / "student_sim2sim.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for group in ("baseline", "wide_speed", "student_wide_speed"):
        paths = list((root / "logs" / group).glob("*/metrics.csv"))
        if len(paths) != 1:
            raise ValueError(f"Ambiguous training runs for {group}")
        rows = read_rows(paths[0])
        if len(rows) != 3000 or int(rows[-1]["iteration"]) != 3000:
            raise ValueError(f"Incomplete training for {group}")
        x = [float(r["iteration"]) for r in rows]
        reward = [float(r["mean_step_reward"]) for r in rows]
        smooth = np.convolve(reward, np.ones(50) / 50, mode="valid")
        axes[0].plot(x[49:], smooth, label=group)
        if group == "student_wide_speed":
            axes[1].plot(x, [float(r["latent_mse"]) for r in rows], lw=0.7)
    axes[0].set(title="Training reward (50-update moving mean)", ylabel="Mean step reward")
    axes[0].legend(fontsize=8)
    axes[1].set(title="Student latent imitation loss", ylabel="Latent MSE", yscale="log")
    for ax in axes:
        ax.set_xlabel("Completed updates")
        ax.grid(alpha=0.2)
    fig.savefig(plots / "training_curves.png", dpi=160)
    plt.close(fig)

    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    (out / "summary.json").write_text(
        json.dumps(
            dict(
                raw_run=str(root),
                metrics=metrics,
                reports=reports,
                notes=[
                    "Teacher nominal seeds repeat identical deterministic trajectories; not independent training trials.",
                    "Only one training seed (42); randomized evaluation has three samples, not a robustness guarantee.",
                    "MuJoCo uses before-step velocity, Genesis after-step velocity; no trajectory-equivalence claim.",
                    "Training curves use different command distributions; reward alone is not a fair performance ranking.",
                ],
            ),
            indent=2,
        )
        + "\n"
    )
    versions = {}
    for package in (
        "torch",
        "numpy",
        "mujoco",
        "onnx",
        "onnxruntime",
        "hydra-core",
        "genesis-world",
        "quadrants",
    ):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    (out / "manifest.json").write_text(
        json.dumps(
            dict(
                archived_at_utc=datetime.now(timezone.utc).isoformat(),
                input_files=manifest,
                archive_interpreter_packages_now=versions,
                provenance="Recorded run configs and evaluation source snapshots are preserved. Current source/config/assets and package versions were captured at archive time, not reconstructed training-time evidence. Models remain local; paths and SHA256 identify them.",
            ),
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(
                output=str(out),
                evaluations=len(metrics),
                input_files=len(manifest),
                bytes=sum(p.stat().st_size for p in out.rglob("*") if p.is_file()),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
