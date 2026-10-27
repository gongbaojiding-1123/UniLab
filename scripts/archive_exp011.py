"""Copy one explicit six-evaluation payload screen into a new evidence archive."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, analysis, out = args.run_dir.resolve(), args.analysis_dir.resolve(), args.output.resolve()
    if out.exists() or out == root or root in out.parents or analysis.parent != root:
        parser.error("Require an explicit analysis inside the run and a new archive outside it")
    protocol = json.loads((root / "protocol.json").read_text())
    runtime = args.runtime_root.resolve()
    if not root.is_relative_to(runtime) or not Path(protocol["checkpoint"]).is_relative_to(runtime):
        parser.error("Runtime root must contain the recorded run and checkpoint")
    summaries = sorted(root.glob("*/eval_*/summary.json"))
    if len(summaries) != 6:
        parser.error("Expected the six completed controlled-load evaluations")
    checkpoint = Path(protocol["checkpoint"])
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != protocol["checkpoint_sha256"]:
        parser.error("Local checkpoint changed since the screen")
    out.mkdir(parents=True)
    inputs = []

    def copy(source, relative):
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if source.suffix == ".csv" and source.name == "transitions.csv":
            destination = destination.with_name(destination.name + ".gz")
            data = gzip.compress(data, mtime=0)
        destination.write_bytes(data)
        inputs.append(
            dict(
                source=str(source),
                archived=str(destination.relative_to(out)),
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        )

    copy(root / "protocol.json", Path("protocol.json"))
    for path in summaries:
        label = path.parent.parent.name
        for source in sorted(path.parent.rglob("*")):
            if source.is_file() and source.suffix in (".csv", ".json", ".yaml"):
                relative = Path("evaluations") / label / source.relative_to(path.parent)
                if relative.name == "run_config.json":
                    relative = relative.with_name("run_configuration.json")
                copy(source, relative)
        copy(root / (label + ".log"), Path("evaluations") / label / "output.txt")
    for name in ("metrics.csv", "summary.json", "payload_velocity.png"):
        copy(analysis / name, Path(name))
    for name, expected in protocol["source_sha256"].items():
        path = runtime / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Recorded runtime source changed before archive: {path}")
        copy(path, Path("source_at_evaluation") / name)
    for name in ("scripts/run_exp011_payload.py", "scripts/analyze_rma_payload.py"):
        copy(runtime / name, Path("source_at_archive") / name)
    (out / "manifest.json").write_text(
        json.dumps(
            dict(
                inputs=inputs,
                checkpoint=str(checkpoint),
                checkpoint_sha256=protocol["checkpoint_sha256"],
                original_run=str(root),
                original_analysis=str(analysis),
                scope="One deterministic seed, three fixed masses, frozen policies. No new training or robustness certification.",
                note="Source_at_evaluation hashes were recorded by the runner; orchestration source_at_archive is labeled separately.",
            ),
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(dict(archive=str(out), evaluations=6, inputs=len(inputs)), indent=2))


if __name__ == "__main__":
    main()
