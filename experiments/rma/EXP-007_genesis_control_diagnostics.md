# EXP-007：Genesis 控制与接触诊断

- 日期：2026-10-25。
- 状态：完成一次名义条件、单环境、单种子、1000 策略步的诊断回放。
- 目的：解释 EXP-006 中 Genesis 速度波动和肉眼看到的踉跄，区分足端接触、关节跟踪误差、动作边界和计算力矩限幅。
- 策略：冻结 `student_mapping_v1_500.onnx`，不训练、不改变权重、不改变策略输入。
- 原始运行目录：`/home/abc/my_unilab/runs/rma/control_diagnostics/EXP-007`。

## 固定协议

使用 `--sim2sim-nominal --control-diagnostics`，指令为前向 `0.5 m/s`、侧向 `0`、偏航角速度 `0`，seed 为 `123`，1000 个策略步。每个策略步包含两个 `0.01 s` 物理步，策略周期为 `0.02 s`。诊断只在评估时开启，额外的 GPU readback 和 CSV 写入不会进入训练路径。

记录的每个物理子步包括：目标角度、执行前后关节角度与角速度、PD 需求估计、Genesis `get_dofs_control_force()`、内部 generalized force、动作幅值、力矩限幅比例、足端接触和受力接触点水平速度。

## 结果

| 指标 | 数值 |
| --- | ---: |
| 记录的策略步 | 1000 |
| 记录的物理子步 | 2000 |
| 平均前向速度 | 0.4441 m/s |
| 前向速度 RMSE | 0.1969 m/s |
| 异常姿态终止 | 0 |
| 超时回合 | 1 |

接触点水平速度的 95 分位数为：FL `0.679`、FR `1.069`、RL `1.400`、RR `0.041` m/s。RL 与 FL 的接触点速度尖峰和速度下降事件同时出现，说明接触切换或足端滑动是值得验证的线索。

关节方面，`RR_calf` 的归一化动作多次接近 `-1`，但其计算控制力矩最大只达到限幅的 `0.317`，所以“动作接近边界”不能解释为“电机力矩饱和”。`FL_thigh` 的计算控制力矩最高达到限幅的 `0.979`，但达到 `>=0.95` 的比例只有 `0.2%`，更像短暂冲击而不是持续饱和。

## 结论边界

当前结果支持：Genesis 中存在接触模式变化、足端接触点速度尖峰和部分关节跟踪误差；这些现象与速度波动同时出现。

当前结果不支持：已经证明某个关节或某个接触事件是根因，也不支持把 Genesis 的单次回放当作鲁棒性结论。`get_dofs_control_force()` 是 API 在步进前计算并限幅的控制力，不是实测电机力矩；`get_dofs_force()` 是求解器内部 generalized force，不能直接和电机额定力矩比较。

## 复查

结果文件见 [`results/rma/sim2sim/EXP-007`](../results/rma/sim2sim/EXP-007/README.md)。核心图表：

- [`contact_and_velocity.png`](../results/rma/sim2sim/EXP-007/plots/contact_and_velocity.png)
- [`joint_tracking.png`](../results/rma/sim2sim/EXP-007/plots/joint_tracking.png)
- [`action_and_control.png`](../results/rma/sim2sim/EXP-007/plots/action_and_control.png)

离线分析命令：

```bash
cd /home/abc/my_unilab
uv run --no-sync python scripts/analyze_genesis_control.py \
  runs/rma/control_diagnostics/EXP-007/genesis_seed123.csv
```

下一步保持模型、奖励、动作缩放和控制参数不变，补采 MuJoCo 同口径的接触与控制诊断，再决定是否进行单变量实验。
