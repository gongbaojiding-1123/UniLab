"""Archive EXP-014 paired joint telemetry and generated figures."""

from archive_exp011 import main

if __name__ == "__main__":
    main(
        expected_evaluations=4,
        figure_name="joint_tracking_rmse.png",
        scope="One frozen teacher/student pair, kd=0.5, added mass 0/5 kg; descriptive joint telemetry, no torque saturation or causal mechanism proof.",
        archive_scripts=("scripts/run_exp014_control.py", "scripts/analyze_rma_joint_tracking.py"),
    )
