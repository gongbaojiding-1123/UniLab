"""Serial evaluation of a frozen teacher/student pair at three fixed loads."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="EXP-010 student checkpoint, containing its frozen teacher too",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    checkpoint, out = args.checkpoint.resolve(), args.output_dir.resolve()
    if not checkpoint.is_file() or out.exists() or args.steps < 1:
        parser.error("Require an existing checkpoint, positive steps and a NEW output directory")
    if not args.dry_run:
        out.mkdir(parents=True)
        paths = [ROOT / "scripts/evaluate_rma.py", ROOT / "scripts/train_rma.py"]
        paths += sorted((ROOT / "src/unilab/conf/ppo/rma_eval").glob("*.yaml"))
        (out / "protocol.json").write_text(
            json.dumps(
                dict(
                    experiment="EXP-011",
                    seed=args.seed,
                    steps=args.steps,
                    command=[0.7, 0, 0],
                    checkpoint=str(checkpoint),
                    checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                    paired_policy_note="Both teacher and student are loaded from the SAME student checkpoint",
                    cases=["nominal", "payload_2p5", "payload_5"],
                    source_sha256={
                        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in paths
                    },
                    note="One deterministic seed, controlled load screen; not a randomized robustness estimate",
                ),
                indent=2,
            )
            + "\n"
        )
    environment = dict(
        os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1"
    )
    for condition in ("nominal", "payload_2p5", "payload_5"):
        for policy in ("teacher", "student"):
            label = f"{condition}_{policy}"
            command = [
                sys.executable,
                str(ROOT / "scripts/evaluate_rma.py"),
                "--checkpoint",
                str(checkpoint),
                "--policy",
                policy,
                "--task",
                "go2_joystick_flat/rma_forward",
                "--eval-condition",
                condition,
                "--num-envs",
                "1",
                "--steps",
                str(args.steps),
                "--seed",
                str(args.seed),
                "--device",
                "cpu",
                "--command",
                "0.7",
                "0",
                "0",
                "--diagnostics",
                "--trace-dir",
                str(out / label),
            ]
            print(f"{'PLAN' if args.dry_run else 'RUN'} {label}: " + " ".join(command), flush=True)
            if args.dry_run:
                continue
            with (out / (label + ".log")).open("w") as stream:
                result = subprocess.run(
                    command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT
                )
            if result.returncode:
                print((out / (label + ".log")).read_text()[-6000:], flush=True)
                raise SystemExit(f"Stopped at {label}; see {out}")
    if not args.dry_run:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/analyze_rma_payload.py"), "--input-dir", str(out)],
            cwd=ROOT,
            check=True,
            env=environment,
        )
    print(f"{'Planned' if args.dry_run else 'Saved'}: {out}")


if __name__ == "__main__":
    main()
