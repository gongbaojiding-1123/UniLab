# EXP-014：受载条件的目标/实际角度诊断

日期：2026-10-28。分支 `feat/exp014-joint-tracking-diagnosis`，基线 `feat/exp013-payload-at-fixed-kd`，延续研究问题 #1。

问题：EXP-013 的受载欠速是否伴随关节目标/实际响应差距变化？
保持同一模型、同一四组物理条件与协议，只增加观测记录；不改奖励、scale、增益或训练范围。
新增 `diagnose_rma_control.py --eval-condition`，对齐初始 episode counter、reset 标签和历史清空；逐步标签取动作前的 privileged 值。
输出权威目标缓冲、步前/步后关节角、速度、动作、重排残差；边界估算 PD 项按来源标记。

## 如何运行与查看

```bash
cd /home/abc/my_unilab
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/run_exp014_control.py \
  --checkpoint runs/rma/EXP-010/20261027_160750/student_wide_speed.pt \
  --output-dir "runs/rma/EXP-014/$(date +%Y%m%d_%H%M%S)"
```

本轮已执行，不必重复。图和完整逐步数据见 [证据入口](../../results/rma/EXP-014/README.md)。
对应实际运行目录为 `runs/rma/EXP-014/joint_tracking_20261028_1310`，每组在独立的 `eval_*` 子目录。

## 验证和结果

- 四组 × 1000 步，48000 行关节记录；四组 transitions 与 EXP-013 全字段逐行一致，证明本次记录没有改变原回放轨迹。
- 映射残差全部为 0，物理标签正确，四组无异常终止、1000 步超时。每关节去启动段各 900 行。
- 负载后 teacher/student 的全部 12 关节目标/步后实际角度 RMSE 都增大；RR_calf 增幅最大，分别约 0.08355/0.07706 rad。
- 这不是固定参考目标的开环执行器试验；闭环目标/速度/接触也改变。不能仅凭该差距证明力矩饱和、驱动故障或打滑。

## 发现的接口语义限制

冒烟检验发现公共 `get_actuator_gains()` 返回基础模型 kd=0，与 reset 配置 kd=0.5 不同。
经已安装后端源码确认，它不提供每环境 reset 字段的权威实时读回。
保留原始读数，另以 `gain_source` 显式标记用于估算的配置增益。没有改动依赖或通过私有接口绕开后端合同。
配置差异引发的轨迹差异仍成立；实际参数读回与扭矩测量应另立后端合同任务，不扩大本轮诊断。

## 学习任务与后续

先看学生两张图的 `RR_calf_joint`，指出横轴、两条线含义和 rad 单位；再用指标定量比较，避免只看线条粗细。
目标与实际角度不一致是观察，增益不足是待检验假设；动作接近边界也不是扭矩饱和的测量。
后续先用更短时间窗口查看目标变化/响应相位及接触时段，再决定是否需要对齐固定输入试验或教师训练对照。
当前没有足够证据直接改 kp、scale 或奖励；不把师生性能差异自动判为 adaptation 代码错误。
