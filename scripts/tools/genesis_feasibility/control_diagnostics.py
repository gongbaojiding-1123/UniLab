"""Opt-in, single-environment Genesis replay telemetry using public entity APIs.

Never feeds a value back into the policy or changes a control command.
"""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

LEGS = ("FL", "FR", "RL", "RR")
JOINTS = tuple(f"{leg}_{part}" for leg in LEGS for part in ("hip", "thigh", "calf"))


def array(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def force_fraction(force, lower, upper):
    """Use the limit on the same side as the signed force, not max(|lo|, |hi|)."""
    force, lower, upper = np.broadcast_arrays(force, lower, upper)
    limit = np.where(force >= 0, upper, -lower)
    result = np.full(force.shape, np.nan, dtype=float)
    valid = np.isfinite(limit) & (limit > 0)
    np.divide(np.abs(force), limit, out=result, where=valid)
    return result


def ground_contacts(data, foot_geom, floor_geom, origins, velocities, angular):
    """Only foot-sphere/ground pairs count; calf collisions and self-contact do not.

    Point tangential speed uses v_origin + omega x (contact_point - origin),
    in world coordinates on a static horizontal floor. An absent loaded contact
    has no speed measurement (None), rather than a misleading zero.
    """
    a = array(data["geom_a"]).reshape(-1)
    b = array(data["geom_b"]).reshape(-1)
    valid = array(data.get("valid_mask", np.ones(a.shape, bool))).reshape(-1).astype(bool)
    pos = array(data["position"]).reshape(-1, 3)
    fa = array(data["force_a"]).reshape(-1, 3)
    fb = array(data["force_b"]).reshape(-1, 3)
    result = {}
    for i, (leg, geom) in enumerate(zip(LEGS, foot_geom, strict=True)):
        on_a = valid & (a == geom) & (b == floor_geom)
        on_b = valid & (b == geom) & (a == floor_geom)
        mask = on_a | on_b
        forces = np.where(on_a[:, None], fa, fb)[mask]
        net = forces.sum(axis=0)
        speeds = []
        for point, force in zip(pos[mask], forces, strict=True):
            if force[2] > 1.0:
                speed = velocities[i] + np.cross(angular[i], point - origins[i])
                speeds.append(float(np.linalg.norm(speed[:2])))
        result.update({
            f"{leg}_ground_contact": int(mask.any()),
            f"{leg}_loaded_contact": int(bool(speeds)),
            f"{leg}_ground_fx_n": float(net[0]),
            f"{leg}_ground_fy_n": float(net[1]),
            f"{leg}_ground_fz_n": float(net[2]),
            f"{leg}_loaded_point_speed_xy_m_s": max(speeds) if speeds else None,
        })
    return result


class GenesisControlDiagnostics:
    """Write two substep rows per policy action, including terminal state before reset."""

    joint_fields = (
        "target_rad", "q_pre_rad", "qd_pre_rad_s", "error_pre_rad",
        "pd_demand_pre_estimate_nm", "control_pre_api_nm", "control_pre_limit_fraction",
        "q_post_rad", "qd_post_rad_s", "error_post_rad", "internal_post_api_nm",
        "raw_action", "action",
    )

    def __init__(self, policy, output, geom_type):
        self.policy = policy
        self.path = output.with_suffix(".control.csv")
        self.metadata_path = output.with_suffix(".control.json")
        self.lower, self.upper = (
            array(x).reshape(12).copy()
            for x in policy.robot.get_dofs_force_range(dofs_idx_local=policy.di)
        )
        self.links = [policy.robot.get_link(f"{leg}_calf") for leg in LEGS]
        feet = [[g for g in link.geoms if g.type == geom_type.SPHERE] for link in self.links]
        if any(len(geoms) != 1 for geoms in feet):
            raise ValueError("Diagnostics require exactly one foot sphere per named calf link")
        self.foot_geom = [int(geoms[0].idx) for geoms in feet]
        floors = [g for g in policy.robot.geoms if g.type == geom_type.PLANE]
        if len(floors) != 1:
            raise ValueError("Diagnostics require exactly one static horizontal plane in the MJCF entity")
        self.floor_geom = int(floors[0].idx)
        self.link_indices = [int(link.idx_local) for link in self.links]
        columns = ["policy_step", "substep", "sim_time_s", "episode", "episode_step"]
        columns += [f"{j}_{field}" for j in JOINTS for field in self.joint_fields]
        columns += [f"{leg}_{field}" for leg in LEGS for field in (
            "ground_contact", "loaded_contact", "ground_fx_n", "ground_fy_n", "ground_fz_n",
            "loaded_point_speed_xy_m_s",
        )]
        self.stream = self.path.open("x", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.stream, fieldnames=columns)
        self.writer.writeheader()
        self.rows = 0
        self.metadata = {
            "format": "genesis-go2-control-diagnostics-v1",
            "source": "Genesis public RigidEntity APIs; no private solver fields",
            "joint_order": list(JOINTS), "physics_dt_s": policy.c["dt"],
            "physics_steps_per_action": policy.c["nsub"],
            "force_lower_nm": self.lower.tolist(), "force_upper_nm": self.upper.tolist(),
            "foot_geom_ids": dict(zip(LEGS, self.foot_geom, strict=True)),
            "floor_geom_id": self.floor_geom,
            "control_pre_api_nm": "get_dofs_control_force() after command, BEFORE scene.step(): clipped control computed from pre-step state; not measured motor torque",
            "pd_demand_pre_estimate_nm": "kp*(target-q_pre)-kv*qd_pre; algebraic estimate, not measured effort",
            "internal_post_api_nm": "get_dofs_force() AFTER scene.step(): solver internal generalized force; not isolated motor torque; do NOT compare with motor limits",
            "contact": "Foot SPHERE against static plane only; solver contacts from latest scene.step(); invalid capacity entries masked; includes both A/B pair directions",
            "loaded_point_speed_xy_m_s": "max horizontal contact-point velocity on foot among contacts with upward force >1 N; uses post-step link twist and reported contact point; empty when not loaded; a slip indicator, not proof of solver friction failure",
            "sampling": "pre control / post state and contacts every physics step, before any episode reset",
            "performance": "Opt-in diagnostic GPU readbacks and CSV writes add evaluation overhead; ordinary replay and training do not import this module",
            "seed": policy.args.seed, "command": policy.cmd.tolist(),
            "nominal": policy.args.sim2sim_nominal, "output": str(self.path.resolve()),
            "model_sha256": hashlib.sha256(policy.args.model.read_bytes()).hexdigest(),
            "complete": False,
        }
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2) + "\n")

    def before_substep(self, target, raw_action, action, substep):
        p = self.policy
        q = array(p.robot.get_dofs_position(dofs_idx_local=p.di)).reshape(12)
        qd = array(p.robot.get_dofs_velocity(dofs_idx_local=p.di)).reshape(12)
        force = array(p.robot.get_dofs_control_force(dofs_idx_local=p.di)).reshape(12)
        error = target - q
        demand = p.kp * error - p.kv * qd
        fraction = force_fraction(force, self.lower, self.upper)
        row = {
            "policy_step": p.stepn + 1, "substep": substep + 1,
            "sim_time_s": p.stepn * .02 + (substep + 1) * p.c["dt"],
            "episode": p.episode, "episode_step": p.epstep + 1,
        }
        for i, name in enumerate(JOINTS):
            for field, values in (
                ("target_rad", target), ("q_pre_rad", q), ("qd_pre_rad_s", qd),
                ("error_pre_rad", error), ("pd_demand_pre_estimate_nm", demand),
                ("control_pre_api_nm", force), ("control_pre_limit_fraction", fraction),
                ("raw_action", raw_action), ("action", action),
            ):
                value = float(values[i])
                row[f"{name}_{field}"] = value if np.isfinite(value) else None
        return row

    def after_substep(self, row, target):
        p = self.policy
        q = array(p.robot.get_dofs_position(dofs_idx_local=p.di)).reshape(12)
        qd = array(p.robot.get_dofs_velocity(dofs_idx_local=p.di)).reshape(12)
        force = array(p.robot.get_dofs_force(dofs_idx_local=p.di)).reshape(12)
        for i, name in enumerate(JOINTS):
            for field, values in (
                ("q_post_rad", q), ("qd_post_rad_s", qd),
                ("error_post_rad", target - q), ("internal_post_api_nm", force),
            ):
                row[f"{name}_{field}"] = float(values[i])
        origins = array(p.robot.get_links_pos(links_idx_local=self.link_indices, relative=False)).reshape(4, 3)
        velocities = array(p.robot.get_links_vel(links_idx_local=self.link_indices)).reshape(4, 3)
        angular = array(p.robot.get_links_ang(links_idx_local=self.link_indices)).reshape(4, 3)
        row.update(ground_contacts(
            p.robot.get_contacts(), self.foot_geom, self.floor_geom, origins, velocities, angular,
        ))
        self.writer.writerow(row)
        self.rows += 1

    def close(self, complete=False):
        self.stream.close()
        self.metadata.update(rows=self.rows, complete=complete)
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2) + "\n")
