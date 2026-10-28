# Go2 RMA Locomotion Lab

基于 UniLab 的 Go2 强化学习运动控制实验：教师 PPO、历史观测适应、模型导出与 C++ 模拟部署。

> 更新：2026-10-28。EXP-010 已归档；EXP-011—013 已完成负载/主动阻尼筛查，尚未消除受载欠速。
> 全部记录见 [实验索引 EXP-000—014](../../experiments/rma/README.md)。目前仅一个训练种子，没有真机或硬实时验证。

## 这个项目解决什么问题

目标是研究如何让四足机器人按速度指令运动，以及如何通过历史观测估计摩擦、负载相关的隐变量。
早期“原地踏步”问题经过控制映射修复和后续训练已有进展，失败记录仍保留，避免只展示成功结果。

**不知道下一步做什么时，先看 [项目工作流与当前步骤](PROJECT_WORKFLOW.md)。**
当前已完成 [EXP-013 固定 kd 负载诊断](../../experiments/rma/EXP-013_payload_at_fixed_kd.md)，保留 `[0.3, 0.8]` 训练范围；先读曲线并复盘，不按历史教程重复长训。
受载关节目标/实际角度图已生成，见 [EXP-014](../../results/rma/EXP-014/README.md)。
项目目的、视觉边界和自己应掌握的内容见 [学习目标](LEARNING_GOALS.md)。

```mermaid
flowchart LR
    P["训练特权参数：摩擦、负载"] --> E["教师 Encoder"]
    E --> Z["隐变量 z：8 维"]
    H["过去 50 步观测：50 × 49"] --> A["学生 Adaptation MLP"]
    A --> ZH["估计隐变量 z_hat：8 维"]
    O["当前观测：49 维"] --> ACT["共享 Actor"]
    Z --> ACT
    ZH --> ACT
    ACT --> U["12 维动作"]
```

教师评估使用真实特权参数，学生使用历史估计隐变量；两条路径是分别选择的。
部署图只保留 Adaptation + Actor，教师 Encoder 与 Critic 不进入部署图。

本分支在 UniLab fork 中加入增量实验层，保留 `unilab` 导入，不修改上游项目的归属。
训练脚本使用项目内的独立 PPO 实现，不是官方 RSL-RL 的训练入口。

## 当前结果：EXP-010

唯一训练变量为指令范围 `[0.3, 0.6] → [0.3, 0.8]`；scale=0.25、奖励和预算固定。
两组教师分别从头训练，均为训练 seed 42，64 环境、3000 次更新。

| 0.7 m/s 指令下的组别 | 平均 vx (m/s) | 平面速度 RMSE (m/s) | 异常终止 |
| --- | ---: | ---: | ---: |
| baseline 教师，MuJoCo nominal | 0.3652 | 0.5249 | 5 |
| wide_speed 教师，MuJoCo nominal | 0.6644 | 0.1130 | 0 |
| wide_speed 学生，MuJoCo nominal | 0.7687 | 0.1415 | 0 |
| wide_speed 学生，Genesis nominal，三次均值 | 0.7137 | 0.1034 | 三次均为 0 |

教师的三个 nominal eval seed 数值完全相同，不能当作三个独立训练或不同初始条件。
学生在 MuJoCo 高速超调；随机化三次样本又存在欠速，不能只用表中名义条件宣称全面鲁棒。
0.3/0.5 m/s、训练曲线、逐步轨迹和模型哈希见 [归档](../../results/rma/EXP-010/README.md)。

TensorRT 与 PyTorch 同状态动作 RMSE 约 `6.85e-8`；10 秒 C++ 测试属于 mock，仍有 3 次 PD deadline miss。
完整结果和局限见 [EXP-010](../../experiments/rma/EXP-010_forward_speed_coverage.md)。

## 历史结果：早期失败基线

所有评估固定机体系指令 `(0.5, 0, 0)`，每个种子使用 8 个环境、每环境 1000 个控制步。

| 模型 | 评估种子 | 平均前向速度 (m/s) | 前向 RMSE (m/s) | 提前终止次数 |
|---|---:|---:|---:|---:|
| 原始教师 | 123 | -0.006058 | 0.510957 | 0 |
| 原始教师 | 456 | -0.011667 | 0.517436 | 1 |
| 原始教师 | 789 | -0.004922 | 0.511072 | 1 |
| 前进配置教师 v1 | 123 | 0.015686 | 0.489772 | 2 |
| 前进配置教师 v1 | 456 | 0.013730 | 0.490668 | 0 |
| 前进配置教师 v1 | 789 | 0.012254 | 0.491959 | 0 |

前进配置 v1 已完成 3000 次更新、4,608,000 次环境转移，初始化种子为 42。
三个评估种子不是三个独立训练种子，表格不构成跨训练种子的显著性结论。
不同配置使用不同奖励权重，因此不能直接用总奖励比较任务效果。
提前终止次数不是经独立检测标注的跌倒率。

![固定前进指令评估](../../results/rma/figures/velocity_comparison.png)

![前进配置教师训练曲线](../../results/rma/figures/forward_v1_training.png)

原始数值、训练记录及分析见 [results](../../results/rma/) 和 [实验记录](../../experiments/rma/)。
以上历史曲线展示训练奖励；后续评估已加入逐步速度、动作和奖励分项，见 EXP-002 及 EXP-010。

## 代码结构

```text
rsl_rl/unilab_rma/   教师/学生网络、PPO、GAE、历史缓冲与 UniLab 适配
scripts/             训练、评估、导出与结果汇总
legged_gym/          Go2 接口常量，并非重新实现 legged_gym
src/unilab/...       RMA 事件与任务配置；原有 UniLab 框架保持上游归属
deploy_cpp/          TensorRT 接口、双缓冲与 50/1000Hz mock 控制框架
tests/rma/           算法与接口测试
experiments/         问题、假设、对照设计与结论
results/             精选 JSON、CSV、配置记录与图表
docs/                使用说明、接口契约与复现边界
```

## 复现与依赖

完整说明见 [复现指南](REPRODUCING.md) 和 [验证记录](VALIDATION.md)。
逐步记录、画图与 Issue/PR 的分工见 [实验操作指南](EXPERIMENT_WORKFLOW.md)。

实测数据基于本地 UniLab 1.3.3 工作副本。MuJoCo 评估与 Genesis 独立回放使用不同环境；版本和设备以各次日志为准。
本 fork 基线为 UniLab 1.3.4，基线 commit 与关键文件差异见 [provenance.json](../../results/rma/provenance.json)。
原始运行副本未携带 Git 历史，且部分配置/运行时文件与 fork 不同；因此不能把旧实测冒充为当前分支端到端验证。
不建议为了运行本仓库直接升级已经验证过的仿真环境。

核心测试与结果图表可以独立运行；真实 Go2 训练仍需要完整 UniLab、依赖与机器人资产。
在匹配的环境中执行：

```bash
cd /path/to/this/UniLab
uv run --no-sync python -m unittest discover -s tests/rma -p 'test_*.py'
```

评估已存在的前进配置教师：

```bash
uv run --no-sync python scripts/evaluate_rma.py \
  --policy teacher --checkpoint runs/rma/teacher_forward_v1.pt \
  --task go2_joystick_flat/rma_forward \
  --num-envs 8 --steps 1000 --seed 123 \
  --command 0.5 0 0 --diagnostics
```

在上述命令追加 `--render` 可看画面，追加 `--render-speed 0.5` 可慢放。
训练默认不打开可视化。实验模型权重和已安装运行环境不包含在本仓库中。
以上是已有完整 1.3.3 运行环境的评估入口；1.3.4 环境接入必须单独完成兼容性验证。

## 接下来如何改进

1. 固定 EXP-010 的模型、scale=0.25 与 Genesis substeps=2，保留全部旧结果。
2. EXP-011—014 的负载、主动阻尼与关节记录已完成。先读角度差距和增益来源限制，再补短窗口/接触证据，不盲调增益或重新长训。
3. 若研究泛化，增加独立初始条件、指令切换或物理条件测试；若研究训练稳定性，增加独立训练种子。
4. 全仓门禁仍受现有依赖/类型问题阻塞，保持审阅状态，不把局部测试当作全仓通过。

本仓库当前不是自动课程调度器；现有 `rma_forward` 是静态前进任务配置。
当前阶段见 [工作流](PROJECT_WORKFLOW.md)，历史诊断方案见 [EXP-002](../../experiments/rma/EXP-002_diagnosis_plan.md)。

## 来源与贡献范围

UniLab 是上游仿真与任务框架；本项目贡献范围为 RMA 增量实现、实验配置、诊断、导出/模拟部署及实验分析。
上游来源、许可证与本地源码快照的限制见 [来源说明](THIRD_PARTY_NOTICES.md)。
AI 工具参与了代码和文档辅助；已验证范围和未验证项以测试记录及实验数据为准。
