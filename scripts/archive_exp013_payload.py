"""Preserve EXP-013's four frozen-policy evaluations and their source hashes."""

from archive_exp011 import main

if __name__ == "__main__":
    main(
        expected_evaluations=4,
        figure_name="payload_at_kd_velocity.png",
        scope="One deterministic seed, active kd=0.5, added mass 0/5 kg, frozen policies. No new training or robustness certification.",
        archive_scripts=("scripts/run_exp013_payload.py", "scripts/analyze_rma_payload_at_kd.py"),
    )
