"""EXP-013: analyze fixed derivative gain and two added base masses."""

from analyze_rma_payload import main

if __name__ == "__main__":
    main(
        experiment="EXP-013",
        cases=(("kd_0p5", 0.0, 0.5), ("kd_0p5_payload_5", 5.0, 0.5)),
        figure_name="payload_at_kd_velocity.png",
    )
