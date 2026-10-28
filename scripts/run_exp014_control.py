"""Frozen-policy joint telemetry under EXP-013's paired evaluation conditions."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("kd_0p5", "kd_0p5_payload_5")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    checkpoint, out = args.checkpoint.resolve(), args.output_dir.resolve()
    if not checkpoint.is_file() or out.exists():
        parser.error("Require an existing checkpoint and a NEW output directory")
    paths = [
        ROOT / name
        for name in (
            "scripts/run_exp014_control.py",
            "scripts/analyze_rma_joint_tracking.py",
            "scripts/diagnose_rma_control.py",
            "scripts/train_rma.py",
            "rsl_rl/unilab_rma/control_diagnostics.py",
            "rsl_rl/unilab_rma/evaluation_conditions.py",
            "rsl_rl/unilab_rma/evaluation_trace.py",
            "rsl_rl/unilab_rma/env_adapter.py",
        )
    ]
    paths += sorted((ROOT / "src/unilab/conf/ppo/rma_eval").glob("*.yaml"))
    out.mkdir(parents=True)
    (out / "protocol.json").write_text(
        json.dumps(
            dict(
                experiment="EXP-014",
                cases=list(CONDITIONS),
                seed=123,
                steps=1000,
                command=[0.7, 0, 0],
                checkpoint=str(checkpoint),
                checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                source_sha256={
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in paths
                },
                note="Evaluation-only telemetry; compare transitions with EXP-013 before interpreting joint errors. One deterministic seed, no causal mechanism proof.",
            ),
            indent=2,
        )
        + "\n"
    )
    environment = dict(
        os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1"
    )
    for condition in CONDITIONS:
        for policy in ("teacher", "student"):
            label = f"{condition}_{policy}"
            command = [
                sys.executable,
                str(ROOT / "scripts/diagnose_rma_control.py"),
                "--checkpoint",
                str(checkpoint),
                "--policy",
                policy,
                "--task",
                "go2_joystick_flat/rma_forward",
                "--eval-condition",
                condition,
                "--steps",
                "1000",
                "--seed",
                "123",
                "--command",
                "0.7",
                "0",
                "0",
                "--output-dir",
                str(out / label),
            ]
            print(f"RUN {label}", flush=True)
            with (out / f"{label}.log").open("w") as stream:
                result = subprocess.run(
                    command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT
                )
            if result.returncode:
                print((out / f"{label}.log").read_text()[-6000:], flush=True)
                raise SystemExit(f"Stopped: {label}; see {out}")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/analyze_rma_joint_tracking.py"),
            "--input-dir",
            str(out),
        ],
        check=True,
        cwd=ROOT,
        env=environment,
    )
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
