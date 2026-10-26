"""Short single-world RMA control diagnosis; never updates model weights."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from train_rma import build_environment
from unilab_rma import ActorCriticRMA, AdaptationModule, HistoryBuffer, RMAConfig
from unilab_rma.control_diagnostics import ControlDiagnostics
from unilab_rma.evaluation_diagnostics import RMA_TASKS, EvaluationDiagnostics
from unilab_rma.evaluation_trace import EvaluationTrace


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--policy", choices=("teacher", "student"), default="teacher")
    p.add_argument("--task", choices=RMA_TASKS, required=True)
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--command", nargs=3, type=float, default=[0.5, 0.0, 0.0])
    p.add_argument("--sim2sim-nominal", action="store_true")
    p.add_argument("--output-dir", type=Path, default=Path("runs/rma/control_diagnostics"))
    args = p.parse_args()
    if args.steps < 1 or args.steps > 5000:
        p.error("steps must be between 1 and 5000 for this short diagnostic")
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if saved.get("format") != "unilab-rma-v1":
        p.error("This diagnostic requires an RMA checkpoint")
    if args.policy == "student" and saved.get("phase") != "student":
        p.error("Student control diagnosis requires an adaptation-trained checkpoint")
    torch.manual_seed(args.seed)
    cfg = RMAConfig(**saved["config"])
    model = ActorCriticRMA(cfg).eval()
    adaptation = AdaptationModule(cfg).eval()
    model.load_state_dict(saved["teacher"])
    adaptation.load_state_dict(saved["adaptation"])
    raw, env = build_environment(
        1,
        cfg,
        "cpu",
        args.seed,
        task=args.task,
        command=args.command,
        sim2sim_nominal=args.sim2sim_nominal,
    )
    trace = None
    try:
        obs, critic, priv = env.reset()
        history = HistoryBuffer(1, cfg, obs.device)
        history.push(obs)
        trace = EvaluationTrace(args.output_dir, raw, dict(vars(args), num_envs=1), args.checkpoint)
        recorder = ControlDiagnostics(raw, trace.directory)
        diagnostics = EvaluationDiagnostics()
        with torch.no_grad():
            for _ in range(args.steps):
                before = recorder.before()
                diagnostics.record_state(critic)
                latent = model.encoder(priv) if args.policy == "teacher" else adaptation(history.data)
                action = model.actor(obs, latent).tanh()
                # Read final controls/physics BEFORE any explicit episode reset.
                state = raw.step(action.to(raw.device))
                terminal = env.read(state.obs)
                term, trunc = bool(state.terminated[0]), bool(state.truncated[0])
                recorder.record(before, action, term, trunc)
                trace.record(
                    critic,
                    action,
                    terminal[1],
                    state.reward,
                    state.terminated,
                    state.truncated,
                    raw.reward_manager,
                )
                diagnostics.record_rewards(raw.reward_manager)
                if term or trunc:
                    raw.reset(torch.tensor([0], device=raw.device))
                # Match UniLabRMAEnv.step, including observation refresh/noise.
                obs, critic, priv = env.read(raw.get_observations())
                history.push(obs, torch.tensor([term or trunc], device=obs.device))
        control = recorder.finish()
        report = trace.finish(
            dict(
                policy=args.policy,
                seed=args.seed,
                task=args.task,
                total_transitions=args.steps,
                diagnostics=diagnostics.report(),
                control=control,
            )
        )
        source = Path(__file__)
        report["diagnostic_source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        (trace.directory / "diagnostic_summary.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(dict(directory=str(trace.directory), **control), indent=2))
    finally:
        if trace is not None:
            trace.close()
        raw.close()


if __name__ == "__main__":
    main()
