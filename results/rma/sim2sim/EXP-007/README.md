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
