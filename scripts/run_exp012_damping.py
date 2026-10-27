"""EXP-012: reuse serial evaluation with only nominal vs kd=0.5 conditions."""

from run_exp011_payload import main

if __name__ == "__main__":
    main(experiment="EXP-012", conditions=("nominal", "kd_0p5"), analyzer="analyze_rma_damping.py")
