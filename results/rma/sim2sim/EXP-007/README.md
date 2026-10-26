# EXP-007 精选诊断数据

对应实验记录：[`EXP-007_genesis_control_diagnostics.md`](../../../../experiments/rma/EXP-007_genesis_control_diagnostics.md)。本目录保存 Genesis 名义条件回放的可复查证据。

| 文件 | 用途 |
| --- | --- |
| `summary.json` | 速度、关节、接触和低速事件摘要 |
| `genesis_control_metadata.json` | 诊断格式、采样协议、模型哈希和限幅定义 |
| `plots/contact_and_velocity.png` | 速度、姿态、接触和足端接触点速度 |
| `plots/joint_tracking.png` | 目标角度与实际角度 |
| `plots/action_and_control.png` | 动作幅值、计算控制力矩限幅比例和角度误差 |
| `traces/genesis.csv.gz` | 1000 个策略步的主回放数据 |
| `traces/genesis_control.csv.gz` | 2000 个物理子步的控制/接触 sidecar |
| `comparison.json` | MuJoCo 与 Genesis 的同协议速度摘要 |

MuJoCo 控制诊断见 [`mujoco_control/`](mujoco_control/)，包括动作到目标角度的映射残差、关节跟踪误差和 PD 代数估计。它不包含孤立的实测电机力矩。

## MuJoCo 对照

MuJoCo 的同协议 trace 位于 [`mujoco/`](mujoco/)，包括 `summary.json`、`run_config.json`、逐步数据和三张快速检查图。当前单次回放的前向速度为：MuJoCo `0.5514 m/s`、Genesis `0.4441 m/s`；速度 RMSE 为 MuJoCo `0.1138 m/s`、Genesis `0.1969 m/s`。这说明 Genesis 的本次轨迹跟踪误差更大，但 MuJoCo 还没有加入与 Genesis 完全同口径的执行器/接触 sidecar，因此不能据此定位根因。

解压数据只用于离线检查；完整未压缩 CSV 保留在 WSL 原始运行目录，不提交训练权重、ONNX、TensorRT engine 或训练日志。

诊断是 opt-in 的，运行命令为：

```bash
cd /home/abc/my_unilab
scripts/run_genesis_go2.sh \
  --sim2sim-nominal \
  --control-diagnostics \
  --steps 1000 \
  --seed 123 \
  --command 0.5 0 0 \
  --output runs/rma/control_diagnostics/EXP-007/genesis_seed123.csv
```

诊断数据来自 Genesis 公共 API。接触点速度是滑动线索，动作接近边界与力矩饱和分别统计，不能单独作为因果证明。
