"""EXP-013: compare zero and 5 kg added mass with active kd fixed at 0.5."""

from run_exp011_payload import main

if __name__ == "__main__":
    main(
        experiment="EXP-013",
        conditions=("kd_0p5", "kd_0p5_payload_5"),
        analyzer="analyze_rma_payload_at_kd.py",
    )
