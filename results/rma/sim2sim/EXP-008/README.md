# EXP-008 结果

对应实验记录：[`EXP-008_genesis_solver_substeps.md`](../../../../experiments/rma/EXP-008_genesis_solver_substeps.md)。此实验比较 Genesis 单个 0.01 s 物理步内部使用 1 或 2 个求解器子步，策略周期仍为 0.02 s。

| 文件 | 用途 |
| --- | --- |
| `comparison.json` | 配对 seed 的均值和误差统计 |
| `summary_seed123.json` | 子步 2 的 seed 123 接触/控制诊断 |
| `control_metadata.json` | 诊断口径、限幅说明和模型哈希 |
| `traces/substeps1_seed*.csv.gz` | 子步 1 的三个基线 trace |
| `traces/substeps2_seed*.csv.gz` | 子步 2 的三个对照 trace |
| `plots/` | 子步 2 seed 123 的速度/接触、关节跟踪、动作/控制图 |

Genesis GPU 在 `qpos0` 初始姿态处输出的关节限位警告也出现在这次运行中；脚本随后明确应用 home keyframe 并执行零速度 reset。该提示记录为运行环境信息，不作为结果过滤依据。

命令行可选 `--physics-substeps N`；默认仍为 1。它只改变 Genesis solver 在每个物理步内部的子步数，不改变策略调用周期。

诊断图：

- [`contact_and_velocity.png`](plots/contact_and_velocity.png)
- [`joint_tracking.png`](plots/joint_tracking.png)
- [`action_and_control.png`](plots/action_and_control.png)
