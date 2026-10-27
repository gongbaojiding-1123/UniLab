# EXP-009：冻结旧策略的速度范围验证

- 日期：2026-10-27。
- 状态：已有 9 次 Genesis GPU、3 次 MuJoCo student、1 次 MuJoCo teacher 回放，现补录归档，不重新训练。
- 问题：EXP-008 的 substeps=2 在 0.5 m/s 有改善，能否推广到 0.3 和 0.7 m/s？
- 改变项：评估指令 vx；不更改训练权重、奖励、动作缩放或控制周期。
- 固定项：`student_mapping_v1_500` 旧策略、nominal home reset、无噪声、摩擦 1、无额外负载、scale=0.25、策略周期 0.02 s；Genesis 物理步 0.01 s、每动作两步、solver substeps=2。

## 原始会话与归档

原始根目录 `/home/abc/my_unilab/runs/rma/sim2sim/` 下：

- `EXP-009_gpu/20261027_145453`：Genesis 1.3.3，独立 Python 3.11 环境，GPU 物理 + ONNX Runtime CPU 策略。
- `EXP-009_mujoco/20261027_152218`：旧 student，seed 123，三个速度。
- `EXP-009_teacher_check/check_1793086177724`：对应旧 teacher，seed 123，0.7 m/s。

精选证据见 [结果入口](../../results/rma/sim2sim/EXP-009/README.md)。
CPU/Genesis 1.4.5 的重试不混入本次 GPU 数据，避免把版本和设备变化当成重复样本。
Genesis 历史日志未记录模型 SHA256，也没有训练时 Git revision；当前模型哈希不能补造历史版本证明。

## 结果

每次回放为 1 环境、1000 策略步。RMSE 为 `sqrt(mean((vx-command)^2 + vy^2))`，由逐步 CSV 重算。

| 引擎 / 策略 | 指令 | 评估 seed | 平均 vx (m/s) | 平面 RMSE (m/s) | 异常终止 |
| --- | ---: | --- | ---: | ---: | ---: |
| Genesis student | 0.3 | 123 / 456 / 789 | 0.3613 / 0.3117 / 0.3136 | 0.1187 / 0.1387 / 0.1400 | 0 / 0 / 0 |
| Genesis student | 0.5 | 123 / 456 / 789 | 0.5013 / 0.5013 / 0.5236 | 0.1822 / 0.1822 / 0.1117 | 0 / 0 / 0 |
| Genesis student | 0.7 | 123 / 456 / 789 | 0.4969 / 0.6178 / 0.6311 | 0.4049 / 0.2409 / 0.1927 | 3 / 1 / 0 |
| MuJoCo student | 0.3 | 123 | 0.3776 | 0.1095 | 0 |
| MuJoCo student | 0.5 | 123 | 0.5514 | 0.1138 | 0 |
| MuJoCo student | 0.7 | 123 | 0.6291 | 0.2207 | 1 |
| MuJoCo teacher | 0.7 | 123 | 0.6158 | 0.3541 | 4 |

Genesis 异常计数来自 `reset_reason=bad_orientation`；MuJoCo 来自 `terminated=1`，不将 timeout 当作跌倒。
MuJoCo student 0.7 m/s 的异常发生于第 801 个转移。均值接近指令不代表速度曲线平稳，0.5 m/s Genesis 的 RMSE 仍有波动。
两端摘要分别取 step 前、step 后速度，存在端点采样差异；不能将曲线逐点相等作为通过标准。

## 结论与下一步

旧策略在 0.7 m/s 的失稳不仅存在于 Genesis，也存在于训练引擎中的旧 teacher。
这支持先检查训练分布，而不是立即调整 Genesis、动作缩放或添加多个奖励项。
它没有证明训练速度范围是唯一原因，也不能把不同引擎的终止计数当作完全相同的跌倒检测器。

因此进入 [EXP-010](EXP-010_forward_speed_coverage.md)：仅扩大训练前向指令范围，固定 scale=0.25 和其他训练参数；两组从头训练、用共同协议评估。
