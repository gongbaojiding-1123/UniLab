# 项目导航：现在做什么，完成后做什么

更新日期：2026-10-28。所有 shell 命令在 WSL Ubuntu 执行，运行工作目录为
`/home/abc/my_unilab`；不要覆盖虚拟环境或全部同步 fork。
训练/评估显式使用现有 UniLab 环境；Genesis 使用独立环境的 `scripts/run_genesis_go2.sh`。

## 当前步骤：读 EXP-014 关节目标/实际角度图

1. 已完成 EXP-010 两组教师、学生、ONNX、Genesis 回放、TensorRT 与 C++ mock；无需重复长训。
2. 从 [实验索引](../../experiments/rma/README.md) 查看全部编号；从 [EXP-010 归档](../../results/rma/EXP-010/README.md) 看曲线和逐步数据。
3. EXP-010 在 PR #3 审阅。EXP-011 本地分支为 `feat/exp011-payload-diagnosis`，基线为 `feat/exp010-speed-coverage-archive`。网页只显示所选分支，推送不等于合并到 `main`。
4. 保留 scale=0.25、Genesis substeps=2、当前模型和原始运行目录。
5. [EXP-011](../../experiments/rma/EXP-011_payload_diagnosis.md) 已比较同一 checkpoint 的 teacher/student，在 0 / 2.5 / 5 kg 下各回放一次。六次无异常终止，5 kg 时两者均欠速；先看已生成图表，再独立检查 PD 增益条件，暂不扩大训练区间。
6. [EXP-012](../../experiments/rma/EXP-012_damping_diagnosis.md) 现已完成零负载下 kd=0/0.5 的四组回放：[看曲线与指标](../../results/rma/EXP-012/README.md)。学生全程平面 RMSE 从 0.14149 降到 0.09611，尚不能据此直接选择真机参数。
7. [EXP-013](../../experiments/rma/EXP-013_payload_at_fixed_kd.md) 已固定 kd=0.5，对比 0/5 kg：负载组 teacher/student 全程平均 vx=0.60930/0.61697，均无异常终止，均比零负载欠速更明显。
8. [EXP-014](../../experiments/rma/EXP-014_joint_tracking.md) 已对齐关节诊断入口的条件/reset，并完成四组记录。直接打开 [目标与实际图](../../results/rma/EXP-014/README.md)，四组轨迹与 EXP-013 全字段逐行一致。先看 RR_calf、明确角度差距不是扭矩饱和证明，再决定后续验证。参照 [学习验收](LEARNING_GOALS.md)。

EXP-010 只有训练 seed 42；nominal eval seed 不等于独立训练或独立物理条件。
没有真机或硬实时验证；完整门禁的已知阻塞见 [验证记录](VALIDATION.md)。

## 下面是 2026-10-23 的历史操作示例

以下保留早期诊断与训练命令用于追溯，**不是当前待执行任务**。不要直接重复已有模型的训练。

### 当时停在哪一步

EXP-003 已训练 3000 次更新，并完成三个评估种子。平均前向速度约 0.013 m/s，
没有完成 0.5 m/s 的指令跟踪。三组评估数据和三类图均已产生。
**目标写入现已修复并验证，下一步从头训练修复后的 std=0.5 基线。**
随后再比较只收紧 std 的实验组；完整操作与修改教程见
[EXP-004 控制修复](../../experiments/rma/EXP-004_control_mapping.md) 与
[EXP-005 跟踪宽度](../../experiments/rma/EXP-005_tracking_width.md)。
不要重新执行已有正式训练来生成图片，也不要同时改动作缩放、奖励和训练预算。

短诊断（1 环境 × 500 步）实测目录：
`/home/abc/my_unilab/runs/rma/control_diagnostics/EXP-003/eval_2ffou4yp`。
目标映射残差最大约 0.47117 rad；前左/前右大腿目标与实际角度 RMSE 约 0.364/0.305 rad。
修复前，1.3.3 快速路径误差 0.0300000 rad、控制诊断残差 0.47117 rad。
修复后，12 个非零关节目标 × 2 环境（含部分重置）的映射检查最大误差 0；
500 步策略诊断映射残差 0。修复代码已备份，未触碰旧模型。
单变量配置对照已解析，且两组各 1 次更新的入口冒烟通过；
正式修复后基线与 std 实验尚未训练。细节及修改教学见 EXP-004/EXP-005。

## 历史命令示例

### 1. 看已有三类图：不运行仿真，不训练

以下循环已执行，重复执行只重新生成这些图片。每个种子三张，共九张：

```bash
cd /home/abc/my_unilab
for trace in runs/rma/evaluations/EXP-003/20261023_151848/seed*/eval_*; do
  uv run --no-sync python scripts/plot_evaluation_trace.py "$trace" || break
done
cd /home/abc/my_unilab/runs/rma/evaluations/EXP-003/20261023_151848/seed123/eval_kwg2tw0_/plots
explorer.exe .
```

查看完后执行 `cd /home/abc/my_unilab` 回到项目根目录。

| 图 | 要回答的问题 | 当前不能推出的结论 |
|---|---|---|
| velocity_tracking.png | 实际 vx 是否接近 0.5，vy/wz 是否偏离？ | 速度小不直接证明训练预算不足 |
| action_distribution.png | 12 个动作是否变化、偏置、频繁到边界？ | 动作到边界不等于扭矩饱和 |
| reward_components.png | 各加权奖励分项是否与任务行为一致？ | 改奖励后总 reward 更高不一定走得更好 |

### 2. 看控制图：已运行，可按需复现

```bash
cd /home/abc/my_unilab
uv run --no-sync python scripts/diagnose_rma_control.py \
  --checkpoint runs/rma/teacher_forward_no_pose_v1.pt \
  --task go2_joystick_flat/rma_forward_no_pose \
  --steps 500 --seed 123 --command 0.5 0 0 \
  --output-dir runs/rma/control_diagnostics/EXP-003
```

每次生成新的 `eval_<unique>`，不改权重。终端给出准确目录。
看 `control_tracking.png`：蓝线为实际写入的目标，橙线为一步后的关节角度；
`control_signals.csv` 保存逐关节信号，`control_summary.json` 保存误差。
`mapping_residual_rad` 比较按语义关节重排后的实际缓冲与 processed target 减 encoder bias，
应接近浮点数值误差。先消除映射残差，再解释姿态跟踪误差。
`pd_demand_estimate_nm` 仅为控制边界处的代数估计，未包含物理子步或被动阻尼，
当前公开 backend API 没有实测执行器扭矩，不能据此宣称扭矩饱和。

### 3. 下一项工程任务：控制路径修复与回归

更新：修复和验收已完成，备份、源码差异与运行命令见 EXP-004。
需要复查时执行 `uv run --no-sync python scripts/check_rma_mapping.py`。
这会写入测试用控制缓冲但不推进物理仿真，并在每个检查后恢复缓冲。

## 完整工作流：每次只进入当前满足条件的一行

| 阶段 | 做什么 | 完成标准与下一步 |
|---|---|---|
| 0 环境与接口 | 冒烟训练、形状与 reset 测试；确认运行源码版本、资产、dt、动作顺序 | 能运行且控制语义正确，才进入正式训练 |
| 1 教师基线 | 固定任务、种子和预算，从头 PPO，保存独立输出 | 得到模型和训练日志；进入定量评估 |
| 2 固定评估 | 同一模型、0.5/0/0、三个种子、8 环境 × 1000 步，保存 trace | 每种子有 summary/CSV/config；进入离线绘图 |
| 3 看图与诊断 | 速度、动作、奖励三图；必要时目标与实际角度图 | 本轮映射修复已验证；现在进入修复后的新基线训练 |
| 4 单变量实验 | 写假设、只改一个变量；新文件名、从头训练、同协议评估 | 记录改善或无改善；控制修复应独立编号，不能混入奖励消融 |
| 5 好教师 → 学生 | 冻结教师与 Actor，用历史估计隐变量 | 学生任务指标接近合格教师，检查 latent/action 误差；低 MSE 单独不足 |
| 6 ONNX | Adaptation + Actor 导出，验证数值误差 | 图结构、IO、顺序、历史重置和数值检查通过 |
| 7 TensorRT/C++ 闭环 | 先对齐推理输出，再用相同观测与关节映射控制仿真 | 数值、任务表现、延迟和过期指令处理逐项验收；mock 通过不等于闭环通过 |
| 8 跨引擎 Sim2Sim | 保持 IO/控制合同，换物理后端独立评估 | 报告差异和泛化结果；之后另行准备真机 |

### 阶段 1/4：未来新实验训练模板（现在不要执行长训）

映射修复验收后，先用相同基础任务建立新的控制修复基线；下面设置保持已有预算，
不是速度或温度保证。模型名 `teacher_mapping_v1.pt` 必须尚不存在。

```bash
cd /home/abc/my_unilab
uv run --no-sync python scripts/train_rma.py \
  --phase teacher --task go2_joystick_flat/rma_forward \
  --output runs/rma/teacher_mapping_v1.pt \
  --num-envs 64 --iterations 3000 --device cuda
```

不传 `--checkpoint` 表示新初始化。传入只加载权重，不恢复 optimizer/RNG，不能称精确续训。
新输出不能覆盖旧模型。训练日志自动在 `teacher_mapping_v1_logs/<unique>/`：
`metrics.csv`、`run_config.json`、`tensorboard/`。训练不开可视化。
另一个终端可开 TensorBoard，若已有服务直接访问它，换端口只用于确实需要的新服务：

```bash
cd /home/abc/my_unilab
uv run --no-sync python -m tensorboard.main \
  --logdir /home/abc/my_unilab/runs/rma --host 127.0.0.1 --port 6007
```

浏览器打开 `http://127.0.0.1:6007`。训练 reward 曲线用于看优化过程；
实验结论以固定评估的实际速度/误差等任务指标为准。

### 阶段 2：训练完成后的标准评估模板

模型和任务要对应；用同一任务比较不同模型时明确区分训练环境与评估环境。

```bash
cd /home/abc/my_unilab
for seed in 123 456 789; do
  uv run --no-sync python scripts/evaluate_rma.py \
    --policy teacher --checkpoint runs/rma/teacher_mapping_v1.pt \
    --task go2_joystick_flat/rma_forward \
    --num-envs 8 --steps 1000 --seed "$seed" \
    --command 0.5 0 0 --diagnostics \
    --trace-dir "runs/rma/evaluations/mapping_v1/seed${seed}" || break
done
```

之后对终端输出的每个 trace.directory 执行画图脚本。要肉眼看已有模型时单独执行：

```bash
uv run --no-sync python scripts/evaluate_rma.py \
  --policy teacher --checkpoint runs/rma/teacher_forward_no_pose_v1.pt \
  --task go2_joystick_flat/rma_forward_no_pose \
  --num-envs 1 --steps 500 --seed 123 --command 0.5 0 0 \
  --render --render-speed 0.5
```

这只是播放当前失败模型，不能修复它。

### 阶段 5—8：先满足前置条件

学生/导出命令和 TensorRT/C++ 说明见 [复现指南](REPRODUCING.md)、
[RMA 主页](README.md) 及 `deploy_cpp/` 中的实现。当前已有冒烟链路记录，
无需反复导出失败策略。先获得合格教师，再以新学生输出名训练并固定评估。
选择迭代数必须依据学生任务指标，不以一次 latent MSE 下降决定完成。

## 每次实验结束后写四句话

在 `experiments/rma/EXP-xxx.md` 中写：问题是什么；唯一改变是什么；
固定协议下测到什么；证据支持什么、下一步只检查什么。
本地 runs 保存完整大数据；results 保存可复查的小摘要与精选图；
Issue #1 记录问题的新证据并链接实验；PR #2 审查代码和验证结果，
不必在两处粘贴相同日志。

上述 47 项测试为 2026-10-23 的历史检查，不代表本轮最终 head 的测试数量。
当前验证以 VALIDATION.md 为准；测试通过也不等于真机部署通过。
