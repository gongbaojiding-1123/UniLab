"""EXP-012: reuse trace analysis for the two active derivative gains."""

from analyze_rma_payload import main

if __name__ == "__main__":
    main(
        experiment="EXP-012",
        cases=(("nominal", 0.0, 0.0), ("kd_0p5", 0.0, 0.5)),
        figure_name="damping_velocity.png",
    )
