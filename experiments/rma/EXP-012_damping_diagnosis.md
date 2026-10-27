# EXP-012：主动阻尼增益的单变量诊断

- 日期：2026-10-27。
- 问题：EXP-010 的随机化欠速与 nominal 的差异，能否部分由主动关节阻尼增益解释？
- 唯一变量：`env.events.pd_gains.params.kd_range`，`[0, 0] → [0.5, 0.5]`。
- 固定项：同一 EXP-010 student checkpoint 内的 teacher/adaptation、kp=35、附加质量 0 kg、摩擦 1、home reset、无噪声、零初始速度、scale=0.25、0.7/0/0 指令、MuJoCo、控制周期 0.02 s。
- 固定的被动关节 damping=0.5 与主动 kd 是不同项；本轮不调整被动阻尼。
- 方法：teacher/student × 两个 kd，共四次；每组 seed 123、1 环境 × 1000 步。仅评估，不训练。
- 分支：`feat/exp012-damping-diagnosis`，基线 `feat/exp011-payload-diagnosis`，延续研究问题 #1。

## 运行前的物理预期

位置 PD 中 `tau = kp * (target - q) - kd * q_dot`。
在同一个关节状态下，kd 从 0 增到 0.5：q_dot=+1 rad/s 时多 -0.5 N m，q_dot=-1 rad/s 时多 +0.5 N m。
它抑制关节运动，并不直接表示“前向速度一定下降”：12 个关节、接触动力学和策略反馈会共同决定机身速度。
因此本轮观察速度与波动，不把公式直接当成闭环结果。

预先沿用 EXP-011 的筛查标准：异常终止为 0；剔除每回合前 100 步后，平均 vx 偏差不超过 0.10 m/s，平面 RMSE 不超过 0.15 m/s。
同时保存全程指标和后段样本数量；少量确定性回放不是鲁棒性认证。

## 修改在哪里

唯一物理配置在 `src/unilab/conf/ppo/rma_eval/kd_0p5.yaml`：继承 nominal，只写 `kd_range: [0.5, 0.5]`。
配置测试要求完整 Hydra 合成后只差这一项。条件元数据报告实际选择的 kd，摩擦/附加质量继续检查 RMA reset 标签。
新增的 runner/analyzer 是薄入口，复用上一轮编排和逐步分析；训练默认不选择这些评估配置。

```bash
cd /home/abc/my_unilab
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/run_exp012_damping.py \
  --checkpoint runs/rma/EXP-010/20261027_160750/student_wide_speed.pt \
  --output-dir "runs/rma/EXP-012/$(date +%Y%m%d_%H%M%S)"
```

## 这轮由学习者掌握的内容

先看 YAML 的三处有效信息：继承谁、事件名、kd 数值；再看 `run_exp012_damping.py` 如何选择两个条件。
读图时依次说清：虚线是什么、teacher/student 为什么来自同一个文件、超调和欠速分别发生在哪组、结论只适用于什么条件。
最后用自己的话写三句：原先的假设是什么；数据支持到哪一步；它为什么还不能证明全部随机化差异的根因。
不是照抄本文件的结论；可以先独立写，再与记录核对。新增算法掌握要另行通过手写小例子验证，不由运行成功推断。

## 已执行结果

四组完整运行、4000 行逐步数据已保存到 [证据入口](../../results/rma/EXP-012/README.md)。
kd=0 的 nominal teacher/student 与 EXP-011 的全程速度和 RMSE 一致。
主动 kd=0.5 时，teacher 全程平均 vx=0.65628、平面 RMSE=0.09660；student 为 0.65612、0.09611。
原 kd=0 的 student 为 0.76871、0.14149。四组异常终止为 0，均在 1000 步超时；
每组后段 900 步，均通过预先沿用的筛查阈值。

学生 action RMSE vs teacher 从 0.08537 降至 0.01340，latent MSE 从 0.10131 降至 0.00386。
这些误差在不同控制条件各自形成的闭环状态分布上测量，不能当作同一观测集上的纯网络误差。
数据支持当前模型对主动 kd 敏感；尚不能证明随机化欠速的全部原因或真机最优 kd。
本轮保留训练/Genesis 默认配置，不因此直接改训练奖励、scale 或扩大速度范围。

## 下一项与学习验收

先由学习者解释 `tau = kp*(target-q)-kd*q_dot` 的符号及两条曲线，再继续物理条件诊断。
后续可编号 EXP-013：固定 kd=0.5，配对比较 0 与 5 kg，保持模型、指令及其他条件一致，检查负载效应在此增益下是否仍存在。
这是待实施方案；不把它写成已完成结果，也不立即追加长训。
