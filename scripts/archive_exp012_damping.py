"""EXP-012: preserve one explicit four-evaluation derivative-gain comparison."""

from archive_exp011 import main

if __name__ == "__main__":
    main(
        expected_evaluations=4,
        figure_name="damping_velocity.png",
        scope="One deterministic seed, two active derivative gains, zero load, frozen policies. No new training or robustness certification.",
        archive_scripts=("scripts/run_exp012_damping.py", "scripts/analyze_rma_damping.py"),
    )
