# EXP-010：扩大教师训练的前向速度覆盖

- 日期：2026-10-27。
- 状态：两组教师训练、学生训练、MuJoCo 评估、ONNX 导出、Genesis GPU 回放、TensorRT 一致性与 C++ mock 测试均已完成；结果已归档，本轮提交在独立实验分支审阅。
- 问题：EXP-009 的 student 在 MuJoCo 0.7 m/s 测试中第 801 步异常终止；同 checkpoint 的 teacher 在 1000 步内异常终止 4 次。因此高速失稳也存在于教师和训练引擎，不能只归因于 Genesis。
- 假设：增加教师训练时的高速指令覆盖，可能改善 0.7 m/s 跟踪与稳定性；需要检查低速表现是否退化。
- 唯一变量：训练指令 `env.commands.twist.ranges.lin_vel_x`，从 `[0.3, 0.6]` 扩到 `[0.3, 0.8]`。
- 固定项：奖励及其宽度、动作缩放 `0.25`、网络、学习率、观测、随机化、MuJoCo 动力学和控制周期。Genesis `physics-substeps=2` 仅用于后续冻结策略回放，本实验不改训练引擎子步。

## 配置在哪里

新任务：`go2_joystick_flat/rma_forward_wide_speed`。

对应文件：`src/unilab/conf/ppo/task/go2_joystick_flat/rma_forward_wide_speed.yaml`。
它继承 `rma_forward`，只覆盖 `lin_vel_x: [0.3, 0.8]`。不会修改原任务、旧模型或原 Genesis 环境。

动作含义仍为 `目标角度 = 默认角度 + 0.25 × action`，角度单位为 rad。
接近动作边界不等于关节力矩饱和。若后续需要研究动作缩放，应另设实验，重新训练并同步导出/部署契约，不能直接给旧模型换 scale。

## 先确认只改了一个变量

在 WSL 中执行。显式选择现有 UniLab 环境；Genesis 回放仍使用 `scripts/run_genesis_go2.sh`。

```bash
cd /home/abc/my_unilab
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/inspect_rma_task.py \
  --task go2_joystick_flat/rma_forward_wide_speed \
  --compare-with go2_joystick_flat/rma_forward \
  --expect-only env.commands.twist.ranges.lin_vel_x
```

应只输出 `[0.3, 0.6] -> [0.3, 0.8]` 这一项差异。

## 正式训练：两组分别从零开始，依次运行

两组均为种子 42、64 环境、24 步 rollout、3000 次更新（各 4,608,000 transitions），策略设备均 CPU；物理引擎均 MuJoCo。
此处固定 CPU 以避免把设备切换混入对照；性能优劣不由这组实验判断。
两组都不传 `--checkpoint`，避免把额外训练预算混入速度范围实验。
若希望另用 CUDA，两组必须同时改为 CUDA，另存记录。
单个训练种子只能提供初步证据；多个评估 seed 不等于多个独立训练 seed。

```bash
cd /home/abc/my_unilab
set -o pipefail
exp_dir="runs/rma/EXP-010/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$exp_dir"

for group in baseline wide_speed; do
  task=go2_joystick_flat/rma_forward
  if [ "$group" = wide_speed ]; then
    task=go2_joystick_flat/rma_forward_wide_speed
  fi
  env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
    scripts/train_rma.py \
    --phase teacher --task "$task" \
    --num-envs 64 --iterations 3000 --device cpu \
    --output "$exp_dir/teacher_${group}.pt" \
    --log-dir "$exp_dir/logs/$group" \
    2>&1 | tee "$exp_dir/train_${group}.log" || break
done
echo "实验目录：$exp_dir"
```

每次新建目录，旧 checkpoint 和旧日志不被覆盖。保存最后打印的目录；若重开终端，需要把 `exp_dir` 设回那个实际目录。
`--iterations 3000` 是 PPO 更新数，不是 3000 个物理步。
一个组输出失败时循环停止，不应继续假装两组都完成。

TensorBoard 指向该实验目录即可。曲线位于 `logs/<group>/<unique>/tensorboard/`，逐次指标为同级 `metrics.csv`，运行参数为 `run_config.json`。

## 两组教师训完后，在共同条件评估

沿用训练终端中的 `exp_dir`；若已重开终端，先明确设置 `exp_dir` 为实际训练目录。
`eval_dir` 单独加时间戳，复测不会覆盖日志。

```bash
set -o pipefail
: "${exp_dir:?请先设置 exp_dir 为两组训练输出的实际目录}"
eval_dir="$exp_dir/evaluations/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$eval_dir"
for group in baseline wide_speed; do
  for vx in 0.3 0.5 0.7; do
    env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
      scripts/evaluate_rma.py \
      --policy teacher --checkpoint "$exp_dir/teacher_${group}.pt" \
      --task go2_joystick_flat/rma_forward --sim2sim-nominal \
      --num-envs 1 --steps 1000 --seed 123 \
      --command "$vx" 0 0 --diagnostics \
      --trace-dir "$eval_dir/${group}_vx${vx}" \
      2>&1 | tee "$eval_dir/${group}_vx${vx}.log" || break 2
  done
done
```

此处固定指令会覆盖评估任务的采样范围，实验组也能用共同任务评估 0.7 m/s。
主要指标是异常终止次数、前向/横向速度、平面速度 RMSE 与偏航；总 reward 和速度均值不能单独代表稳定。
nominal 模式为 home reset、无噪声、固定物理参数；多个 seed 不足以覆盖初始姿态或摩擦变化。
这是初步筛选，不是鲁棒性认证。

只有新教师的高速表现改善、且 0.3/0.5 m/s 未明显退化，再进入新学生训练、ONNX 导出和 Genesis 复测。
若没有改善，再依据动作边界占比、实际关节跟踪与力矩测量选择下一个变量，而不是同时调整 scale 和奖励。

## 已完成结果

实际运行目录：`/home/abc/my_unilab/runs/rma/EXP-010/20261027_160750`。
两组教师均从零初始化，训练种子 42，各 3000 次更新和 4,608,000 transitions；学生冻结 wide_speed 教师，训练历史适应模块 3000 次更新。
以下教师 nominal 指标在 seed 123/456/789 中完全一致，每行是一次回放的数值，不能当作三次独立训练或三种不同初始条件。

| 组 | 目标速度 (m/s) | 平均 vx (m/s) | 平面速度 RMSE (m/s) | 每次异常终止 |
| --- | ---: | ---: | ---: | ---: |
| baseline | 0.3 | 0.3750 | 0.1168 | 0 |
| wide_speed | 0.3 | 0.2880 | 0.0690 | 0 |
| baseline | 0.5 | 0.5968 | 0.1852 | 0 |
| wide_speed | 0.5 | 0.4667 | 0.0911 | 0 |
| baseline | 0.7 | 0.3652 | 0.5249 | 5 |
| wide_speed | 0.7 | 0.6644 | 0.1130 | 0 |

在本轮条件下，仅扩大指令范围后，教师的高速跟踪和稳定性改善，0.3/0.5 m/s 的 RMSE 也降低。没有改变动作缩放或奖励。这是一个训练种子的对照证据，不能推断所有训练种子都有同样效果。

学生在 MuJoCo nominal 条件下的平均 vx 为 `0.2910 / 0.4699 / 0.7687 m/s`，对应平面速度 RMSE 为 `0.0777 / 0.0965 / 0.1415 m/s`，均无异常终止。0.7 m/s 有超调，不能称精确跟踪。高速 student 与 teacher 的同状态动作 RMSE 约 0.0854，只是误差线索，不足以单独证明超调根因。

保留噪声和物理随机化的 0.7 m/s 测试，seed 123/456/789 的平均 vx 为 `0.6013 / 0.6565 / 0.5838 m/s`，平面速度 RMSE 为 `0.1281 / 0.1129 / 0.1631 m/s`，均无异常终止，但存在欠速。这三份轨迹中 episode 在 985/648/462 步结束均为 `terminated=0, truncated=1`；少于 1000 步本身不能证明摔倒，非 nominal 初始回合计数可影响首次超时长度。

冻结同一 ONNX student 后，Genesis 1.3.3 GPU、substeps=2 的九次 1000 步回放无 `bad_orientation`，均为正常 `time_out`：

| 指令 (m/s) | 三次平均 vx (m/s) | 三次平面速度 RMSE 均值 (m/s) |
| ---: | ---: | ---: |
| 0.3 | 0.3109 | 0.0723 |
| 0.5 | 0.4770 | 0.0881 |
| 0.7 | 0.7137 | 0.1034 |

这是本组 nominal 跨引擎验证；不要求两引擎轨迹一致。MuJoCo 摘要采样 step 前速度，Genesis 摘要采样 step 后速度，存在一控制步端点口径差异；归档图标明此差异。

## 部署验证

- ONNX 导出记录最大动作绝对误差约 `7.15e-7`。
- TensorRT 10.13.3 构建成功；0.7 m/s MuJoCo 回放动作 RMSE `6.8488445e-8`，最大动作绝对误差 `5.0663948e-7`，异常终止 0。
- TensorRT 回放平均 vx `0.7687095 m/s`，平面速度 RMSE `0.1414868 m/s`，与 PyTorch 相符。此处超调不是 TensorRT 转换引入的明显偏差；FP16 构建选项也不保证每一层均采用 FP16。
- 10 秒 C++ mock：policy 500 ticks、PD 9998 ticks；发布/消费 500/500；PD deadline misses=3、policy misses=0、stale=1；平均/最大推理 `0.538972 / 2.30445 ms`。
- max action=1、目标角度偏移=0.25 rad、计算扭矩峰值=40.3245 N m。它们属于 mock 输入下的框架输出，不是物理机器人的力矩测量；WSL 上少量 deadline miss 不构成硬实时保证。stale 汇总没有时间戳，不能断定发生于启动阶段。

## 归档与复现

可审阅结果位于 [`results/rma/EXP-010`](../../results/rma/EXP-010/README.md)：34 次评估汇总、压缩轨迹、训练 CSV/参数、配置快照、三张图、部署原始文本、模型 SHA256。
原始 PT/ONNX/engine 和 TensorBoard events 保留本地，不提交二进制模型；`manifest.json` 中记录对应路径和哈希。

归档脚本明确选取本次各阶段的时间戳目录，不自动挑选不同轮次结果。重新生成到新目录可执行：

```bash
cd /home/abc/my_unilab
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/archive_exp010.py \
  --run-dir /home/abc/my_unilab/runs/rma/EXP-010/20261027_160750 \
  --output "/home/abc/my_unilab/results/rma/EXP-010_rebuild_$(date +%Y%m%d_%H%M%S)"
```

`source_at_archive/` 和包版本是归档时状态，不能倒推训练时源码；评估当时保存的源码哈希/任务快照单独保留。UniLab 与 Genesis 虚拟环境不同，manifest 中 UniLab 环境安装的 Genesis 1.4.5 不是本轮 Genesis 回放版本，回放日志明确为独立环境的 Genesis 1.3.3。

## 决策与后续边界

当前将 wide_speed 模型与动作缩放 0.25 固定为后续验证基线，Genesis substeps=2。下一项研究应先定义问题：例如随机负载下的高速欠速，或更长回放/指令切换下稳定性；不要把扩大训练预算、修改奖励与修改动作缩放合并到一个对照中。
目前没有真机测试，没有多训练种子复现，没有系统扰动/地形/指令切换测试，不能宣称完成 sim2real 或通用鲁棒运控。

## 实施验证

- Windows GitHub 工作副本与 `/home/abc/my_unilab` 运行副本的 Hydra 解析检查都通过；唯一差异为 `env.commands.twist.ranges.lin_vel_x`。
- WSL 中通过 `uv run --active --no-sync python -m unittest discover -s tests/rma -p <文件名>` 分别运行 `test_speed_range_config.py`（1）、`test_evaluation_diagnostics.py`（4）、`test_evaluation_trace.py`（2）、`test_core.py`（8），共 15 项通过。
- `ruff check` 对改动的两个 Python 模块和新增测试通过；`git diff --check` 通过。
- 运行新任务的 teacher 短训练：2 个环境、1 次更新、CPU，正常保存 checkpoint 和日志。它只证明训练入口可运行，不提供性能结论；短训进程限制为单 CPU 线程，不作为正式实验数据。
- 仓库全量门禁在独立 `/tmp/exp010-validation-*` 源码快照中执行，使用现有环境并关闭 uv 自动同步，避免全仓自动格式化影响用户工作树：`make check` 的 mypy 通过，pyright 报告 10 个未修改模块中的类型错误（包含现有 `unisim` 缺失的能力字段）；`make test` 在指定快照 `src` 为 `PYTHONPATH` 后，因安装的 `unisim.dr.types` 缺少 `TensorResetRandomizationPayload` 而在收集阶段失败。全量门禁未通过，不能称整个仓库验证完成，也未升级依赖来绕过问题。
- 首次全量检查日志保存在工作区 `outputs/exp010_make_check.log` 与 `outputs/exp010_make_test.log`。后续归档与发布检查另见 [验证记录](../../docs/rma/VALIDATION.md)；完整门禁未通过的限制仍然保留。
