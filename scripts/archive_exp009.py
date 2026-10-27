"""Archive the recorded EXP-009 speed sweep without rerunning simulation."""

import argparse
import csv
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from archive_exp010 import read_report, read_rows, sha256

GENESIS = "EXP-009_gpu/20261027_145453"
MUJOCO = "EXP-009_mujoco/20261027_152218"
TEACHER = "EXP-009_teacher_check/check_1793086177724"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.run_dir.resolve(), args.output.resolve()
    if out.exists() or out == root or root in out.parents:
        parser.error("Choose a new output outside the original run directory")
    for session in (GENESIS, MUJOCO, TEACHER):
        if not (root / session).is_dir():
            parser.error(f"Missing recorded session: {root / session}")
    out.mkdir(parents=True)
    manifest, metrics, reports, curves = [], [], [], {}

    def copy(source, relative, compress=False):
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if compress:
            with source.open("rb") as original, destination.open("wb") as target:
                with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as zipped:
                    shutil.copyfileobj(original, zipped)
            with gzip.open(destination, "rb") as stream:
                assert hashlib.sha256(stream.read()).hexdigest() == sha256(source)
        else:
            shutil.copyfile(source, destination)
        manifest.append(dict(source=str(source), archived=str(relative), sha256=sha256(source)))

    def add(label, engine, policy, seed, goal, rows, report):
        if len(rows) != 1000:
            raise ValueError(f"Expected 1000 transitions: {label}")
        if engine == "genesis":
            vx = np.array([float(r["vx_m_s"]) for r in rows])
            vy = np.array([float(r["vy_m_s"]) for r in rows])
            ended = [i for i, r in enumerate(rows) if r["reset_reason"] == "bad_orientation"]
            timeouts = sum(r["reset_reason"] == "time_out" for r in rows)
            reference = report["planar_velocity_rmse_m_s"]
            assert report["genesis"] == "1.3.3" and report["physics"] == "gpu"
            assert report["genesis_solver_substeps"] == 2
        else:
            vx = np.array([float(r["before_vx_m_s"]) for r in rows])
            vy = np.array([float(r["before_vy_m_s"]) for r in rows])
            ended = [i for i, r in enumerate(rows) if int(r["terminated"])]
            timeouts = sum(int(r["truncated"]) for r in rows)
            reference = report["planar_velocity_rmse_m_per_s"]
            assert len(ended) == report["terminations"]
        rmse = float(np.sqrt(np.mean((vx - goal) ** 2 + vy**2)))
        if not np.isfinite([*vx, *vy]).all() or not math.isclose(rmse, reference, abs_tol=1e-6):
            raise ValueError(f"Invalid data or report/trace mismatch: {label}")
        metrics.append(
            dict(
                label=label,
                engine=engine,
                policy=policy,
                seed=seed,
                target_vx=goal,
                steps=len(rows),
                mean_vx=float(vx.mean()),
                planar_rmse=rmse,
                terminations=len(ended),
                truncations=timeouts,
            )
        )
        reports.append(dict(label=label, summary=report))
        curves[label] = vx, ended

    for goal in (0.3, 0.5, 0.7):
        for seed in (123, 456, 789):
            path = root / GENESIS / f"vx{goal}_seed{seed}.csv"
            report = read_report(path.with_suffix(".log"))
            label = f"genesis_student_vx{goal}_seed{seed}"
            add(label, "genesis", "student", seed, goal, read_rows(path), report)
            copy(path, Path("genesis") / (path.name + ".gz"), compress=True)
            copy(path.with_suffix(".log"), Path("genesis") / (path.stem + ".txt"))

    for session, policy in ((MUJOCO, "student"), (TEACHER, "teacher")):
        paths = sorted((root / session).rglob("summary.json"))
        assert len(paths) == (3 if policy == "student" else 1)
        for path in paths:
            report = json.loads(path.read_text())
            goal, seed = float(report["command_override"][0]), int(report["seed"])
            label = f"mujoco_{policy}_vx{goal}_seed{seed}"
            add(
                label,
                "mujoco",
                policy,
                seed,
                goal,
                read_rows(path.parent / "transitions.csv"),
                report,
            )
            for source in sorted(path.parent.rglob("*")):
                if source.is_file() and source.suffix in (".csv", ".json", ".yaml"):
                    relative = Path("mujoco") / label / source.relative_to(path.parent)
                    if relative.name == "run_config.json":
                        relative = relative.with_name("run_configuration.json")
                    copy(
                        source,
                        str(relative) + ".gz" if source.suffix == ".csv" else relative,
                        compress=source.suffix == ".csv",
                    )
    assert len(metrics) == 13
    with (out / "metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    (out / "summary.json").write_text(json.dumps(reports, indent=2) + "\n")
    (out / "manifest.json").write_text(
        json.dumps(
            dict(
                inputs=manifest,
                scope="Recorded 1.3.3 GPU runs and MuJoCo checks only; CPU/1.4.5 retries excluded",
                limitations="Genesis logs do not record model SHA256 or training-time git revision",
            ),
            indent=2,
        )
        + "\n"
    )

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, goal in zip(axes, (0.3, 0.5, 0.7)):
        for engine, color in (("mujoco", "#2563eb"), ("genesis", "#d97706")):
            vx, ended = curves[f"{engine}_student_vx{goal}_seed123"]
            times = np.arange(len(vx)) * 0.02
            ax.plot(times, vx, color=color, linewidth=1, label=f"{engine} student")
            if ended:
                ax.scatter(times[ended], vx[ended], color=color, marker="x", s=55)
        ax.axhline(goal, color="black", linestyle="--", label=f"command {goal} m/s")
        ax.set_ylabel("Forward velocity (m/s)")
        ax.grid(alpha=0.2)
        ax.legend(loc="upper right", ncol=3, fontsize=8)
    axes[-1].set_xlabel("Global policy step x 0.02 s (resets do not reset this axis)")
    fig.suptitle(
        "EXP-009: frozen old student, seed 123; x = abnormal termination\n"
        "MuJoCo samples before step; Genesis samples after step"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    (out / "plots").mkdir()
    fig.savefig(out / "plots/speed_sweep.png", dpi=150)
    plt.close(fig)
    print(
        json.dumps(
            dict(output=str(out), evaluations=len(metrics), files=len(manifest), metrics=metrics),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
