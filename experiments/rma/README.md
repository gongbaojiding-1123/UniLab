# Go2 RMA 实验索引

更新：2026-10-28。编号表示研究过程，不表示每个编号都产生新模型。
先读本页，再打开对应实验记录；每次评估的大文件保留在本地 `runs/rma/`，精选证据放在 `results/rma/`。

| 编号 | 问题 / 变量 | 已有记录与结论 |
| --- | --- | --- |
| [EXP-000](EXP-000_teacher_full_baseline.md) | 原始教师基线 | 保存旧模型与失败基线，供回溯 |
| [EXP-001](EXP-001_forward_v1.md) | 前进任务配置 | 原地踏步，未完成指令跟踪 |
| [EXP-002](EXP-002_diagnosis_plan.md) | 逐步速度、动作和奖励诊断 | 建立 trace 与分析流程，保留诊断方案及证据 |
| [EXP-003](EXP-003_no_pose_penalty.md) | 去除站姿惩罚 | 没有实质改善；不把 reward 变化等同于会走路 |
| [EXP-004](EXP-004_control_mapping.md) | 控制目标写入映射 | 修复后非零目标映射检查与短回放残差为零 |
| [EXP-005](EXP-005_tracking_width.md) | 跟踪奖励宽度 std | 保存单变量实验方案和修改教程；正式结论以实际评估证据为准 |
| [EXP-006](EXP-006_sim2sim_nominal.md) | MuJoCo → Genesis 名义条件迁移 | 冻结策略可以运行，仍有速度波动 |
| [EXP-007](EXP-007_genesis_control_diagnostics.md) | 控制与接触诊断 | 接触变化与速度下降相关，未证明唯一根因 |
| [EXP-008](EXP-008_genesis_solver_substeps.md) | Genesis substeps 1 → 2 | 三组配对与五 seed 确认，支持固定为 2 |
| [EXP-009](EXP-009_speed_generalization.md) | 旧策略 0.3 / 0.5 / 0.7 m/s 扫描 | 高速异常也出现在 MuJoCo 教师，不能仅归因于跨引擎 |
| [EXP-010](EXP-010_forward_speed_coverage.md) | 训练指令范围 [0.3, 0.6] → [0.3, 0.8] | 一训练种子下教师改善；学生、跨引擎、导出和 mock 均有记录 |
| [EXP-011](EXP-011_payload_diagnosis.md) | 冻结 teacher/student，固定负载 0 / 2.5 / 5 kg | 仅评估负载敏感性，不扩大训练速度范围；指标与结论见记录 |
| [EXP-012](EXP-012_damping_diagnosis.md) | 冻结模型，主动 kd 0 → 0.5 | 零负载下学生超调与平面 RMSE 降低；一个确定性条件筛查 |
| [EXP-013](EXP-013_payload_at_fixed_kd.md) | 固定 kd=0.5，附加质量 0 → 5 kg | 教师和学生均欠速加重；四组无异常终止，需继续诊断执行跟踪 |
| [EXP-014](EXP-014_joint_tracking.md) | 同 EXP-013 四组，新增关节目标/实际记录 | 48000 行关节信号；负载后角度差距增大，尚未证明唯一机制 |

## 当前完成到哪里

EXP-010 已完成本轮归档，见 [结果入口](../../results/rma/EXP-010/README.md)。
本轮唯一训练变量为速度指令范围，动作缩放仍为 0.25，Genesis 子步仍为 2。
不需要为了补图片或补文档重跑长训。

当前结果只支持已测试的名义条件和少量随机化样本，不能声称多训练种子复现、真机部署或硬实时通过。
EXP-011 已选择固定负载诊断，先定位随机化高速欠速；训练速度范围保持 `[0.3, 0.8]`。
六组回放现已完成；5 kg 时 teacher/student 都欠速，见 [证据入口](../../results/rma/EXP-011/README.md)。
EXP-012 的四组阻尼回放已完成，见 [曲线与逐步证据](../../results/rma/EXP-012/README.md)。
EXP-013 的固定 kd 负载对照也已完成，见 [本轮证据](../../results/rma/EXP-013/README.md)。5 kg 时两策略仍欠速，先复盘并诊断受载执行跟踪，不直接开始更宽速度长训。
学习目标和验收方式见 [从运行到理解](../../docs/rma/LEARNING_GOALS.md)。
EXP-014 的配对关节诊断已完成，直接打开 [目标/实际角度图](../../results/rma/EXP-014/README.md)，无需再跑一次生成图片。
操作顺序见 [项目工作流](../../docs/rma/PROJECT_WORKFLOW.md)。

## 如何在 GitHub 找到记录

网页文件列表只显示当前选择的分支。文件推送到实验分支后，不会自动出现在 `main`。
可从本页进入全部记录；PR 用于审阅代码与证据，合并后才进入目标分支。
本轮后续分支的基线为 `docs/exp007-genesis-control-diagnostics`；早期代码另在 PR #2 审阅。
两者都不能当作已合并到 `main`。
