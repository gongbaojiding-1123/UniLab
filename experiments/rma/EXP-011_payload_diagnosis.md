# EXP-011：高速欠速的固定负载诊断

- 日期：2026-10-27。
- 起点：[EXP-010](EXP-010_forward_speed_coverage.md) student 在 0.7 m/s 名义条件下平均约 0.769 m/s，随机化样本约 0.584–0.656 m/s。
- 问题：只增加附加负载，是否足以重现欠速？教师与学生是否同样退化？
- 状态：六次串行回放与分析已完成，结果归档。本实验没有训练新模型。
- 工作分支：`feat/exp011-payload-diagnosis`，基线 `feat/exp010-speed-coverage-archive`，关联研究问题 #1。

## 为什么暂不继续扩大速度区间

0.7 m/s 已在训练范围 `[0.3, 0.8]` 内。名义条件能达到且可能超过指令，不同物理条件下才欠速，不能据此认定速度覆盖不足。
继续提高上限会同时改变训练分布和目标速度附近的采样比例，固定预算下不保证改善 0.7 m/s。
只有未来目标确实高于 0.8 m/s，或证据支持覆盖不足时，才单独开展更宽速度范围实验。

## 控制变量与比较方法

使用同一 `student_wide_speed.pt` 内保存的冻结 teacher 和 adaptation，分别选择 `--policy teacher/student`，避免误选不同版本的教师。
测试附加质量 0 / 2.5 / 5 kg，三种固定负载都在训练随机化 `[0, 5] kg` 范围内，端点属于有意的压力筛查。
其余均固定：home reset、零初始速度、摩擦系数 1、kp=35、kd=0、无观测噪声、scale=0.25、指令 `[0.7,0,0]`、MuJoCo、0.02 s 控制周期。
沿用训练的附加质量事件 `recompute_inertia=false`；本实验不同时改变惯量建模。

采用 1 个确定性 seed 123、每组 1 环境 × 1000 步，共六次串行回放。
这里不把重复的 nominal seed 当作不同负载样本；六次是三个负载条件下的两种策略，不是六次独立训练。

预先使用以下筛查标准：无异常终止；去除每回合前 100 步后，平均 vx 与 0.7 的偏差不超过 0.10 m/s，平面速度 RMSE 不超过 0.15 m/s。
同时保留全程指标；若后段样本很少或为空，不认定通过。这些阈值是本实验的筛查规则，不是行业通用标准。
比较负载增加前后的变化，不仅比较哪条曲线更靠近目标：名义条件的超调也可能被负载暂时抵消。

## 如何运行

在 WSL 的现有 UniLab 环境中执行，新目录保护旧结果；无可视化，串行子进程限定 CPU 数学线程为 1。

```bash
cd /home/abc/my_unilab
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/run_exp011_payload.py \
  --checkpoint runs/rma/EXP-010/20261027_160750/student_wide_speed.pt \
  --output-dir "runs/rma/EXP-011/$(date +%Y%m%d_%H%M%S)"
```

脚本依次评估并生成 `analysis_*/metrics.csv`、`summary.json`、`payload_velocity.png`，无需另外运行绘图命令。
独立重画时执行 `scripts/analyze_rma_payload.py --input-dir <实际运行目录>`，分析同样新建目录，不覆盖。

单组调试示例：

```bash
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/evaluate_rma.py \
  --checkpoint runs/rma/EXP-010/20261027_160750/student_wide_speed.pt \
  --policy student --task go2_joystick_flat/rma_forward \
  --eval-condition payload_2p5 --command 0.7 0 0 \
  --num-envs 1 --steps 1000 --seed 123 --diagnostics \
  --trace-dir runs/rma/EXP-011/manual
```

`--eval-condition` 仅影响显式选择的评估；训练 CLI 不选择该配置组。旧 `--sim2sim-nominal` 对应相同的零负载配置，两种开关不能同时使用。
YAML 所有物理条件由 Hydra owner 配置合成；不直接访问私有仿真 API 修改动力学。
评估初始与重置后检查实际 RMA 标签，CSV 记录动作前的摩擦和负载，防止把重置后的标签写到前一回合。

## 结果如何决定下一步

- 两种策略都随负载明显变慢：负载敏感性是线索，继续检查教师任务能力、关节跟踪和控制需求；低 latent MSE 不会替代教师能力。
- 教师保持速度而学生明显退化：优先研究历史适应误差、历史窗口启动段和训练覆盖，不先改变执行器动作缩放。
- 固定负载不足以重现随机化欠速：下一项单变量测试转向增益、摩擦或初始状态，按顺序选择一个；不能把多个变量一起打开后再指定其中一个为根因。

本轮不证明真机负载性能，不重新训练，不修改奖励、scale 或训练速度范围，不将动作接近 ±1 等同于力矩饱和。

## 已完成结果

原始会话：`/home/abc/my_unilab/runs/rma/EXP-011/payload_screen_20261027_2232`。
分析目录：`analysis_j_hjl3zw`；[证据入口](../../results/rma/EXP-011/README.md)。
checkpoint SHA256：`28785b298e5071d109ace124dc1c3388e2324fb8c5fda29087cfb829049ce5c5`，与 EXP-010 相同。

| 附加负载 | 策略 | 全程平均 vx | 全程平面 RMSE | 后 900 步平均 vx | 后 900 步平面 RMSE | 异常终止 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0 kg | teacher | 0.6644 | 0.1130 | 0.6743 | 0.0978 | 0 |
| 0 kg | student | 0.7687 | 0.1415 | 0.7846 | 0.1316 | 0 |
| 2.5 kg | teacher | 0.6398 | 0.1337 | 0.6468 | 0.1197 | 0 |
| 2.5 kg | student | 0.7338 | 0.1559 | 0.7504 | 0.1474 | 0 |
| 5 kg | teacher | 0.6219 | 0.1571 | 0.6390 | 0.1282 | 0 |
| 5 kg | student | 0.6291 | 0.1399 | 0.6416 | 0.1213 | 0 |

每次共 1000 行，末尾均为 `truncated=1`；移除各回合前 100 步后每组保留 900 行。
六组均满足预定的后段筛查阈值，但并非精确跟踪或鲁棒性认证。全程质量变化仍造成明显速度漂移。
新 YAML 零负载回放重现 EXP-010 teacher/student 的速度与平面 RMSE，差异小于 `2e-8`，未发现条件配置迁移改变基准行为。

## 本轮解释与决策

学生全程平均速度随 0 → 5 kg 从 0.7687 降为 0.6291 m/s（下降约 0.140），教师从 0.6644 降为 0.6219 m/s（下降约 0.042）。
5 kg 时二者接近，student 相对同状态 teacher 的动作 RMSE 约 0.0426，比零负载的 0.0854 更小；隐变量 MSE 也更小。
因此不能把高速欠速简单解释为“学生不会模仿教师”，也不能用更低 latent MSE 证明速度更准确。
同一 teacher 在重负载下也欠速，任务能力与物理条件均需要关注；这不是仅靠 adaptation 误差能够解释的现象。

固定负载单独就能产生欠速线索，但 EXP-010 随机化还包含摩擦、初始状态、增益和噪声，尚未证明负载解释全部随机化差异。
下一项优先检查 **PD 增益条件**：当前 nominal 使用 kd=0，训练随机化 kd 为 [0.45, 0.55]（与被动关节阻尼是不同项）。
可在零负载、相同初始状态下只改变 kd，验证其是否带来额外速度变化；本轮没有执行该后续实验。
训练速度范围保持 `[0.3, 0.8]`，动作缩放保持 0.25，不开展没有新证据支持的更宽速度长训。

## 实施与验证边界

配置对照测试确认 payload_2p5 / payload_5 相对 nominal 仅修改 `env.events.rma_base_load.params.mass_distribution_params`。
评估 trace 新增两列真实 RMA 标签；终止转移记录动作前标签，reset 后重新验证新标签。
GitHub 工作副本原来的评估器已有 `--sim2sim-nominal`，而构建函数未接收此参数；本轮把 WSL 已有 nominal 功能归入同一 YAML 配置组，补齐该接口，并保留无条件选择时的训练路径。
运行副本只替换构建函数和新增诊断文件，旧文件备份于 `runs/rma/EXP-011/code_sync_20261027_223012`，没有同步完整 fork 或升级依赖。
实测仍来自现有 UniLab 1.3.3 运行环境；全 fork 1.3.4 兼容性仍受既有门禁问题限制。
