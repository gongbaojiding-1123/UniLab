# RMA 分支验证记录

## 2026-10-27：EXP-012 主动阻尼单变量诊断

新增 `rma_eval/kd_0p5.yaml` 与三个薄入口，复用 EXP-011 的串行评估、分析和归档逻辑。
训练默认、权重、scale 与 Genesis 配置保持原值。增量同步前以父提交 AST 对比运行源码，
备份位于 `runs/rma/EXP-012/code_sync_20261027_230217`。

```bash
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  -m unittest discover -s tests/rma -p 'test_*.py'
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  scripts/run_exp012_damping.py \
  --checkpoint runs/rma/EXP-010/20261027_160750/student_wide_speed.pt \
  --output-dir runs/rma/EXP-012/damping_screen_20261027_2304
```

- 59 项 RMA unittest 一次运行全部通过（114.487 s）；含完整 Hydra 解析仅 kd_range 改变的检查。
- 真实运行 10 步冒烟及四组 1000 步评估通过。4000 行实际摩擦/质量标签、报告 RMSE、超时/异常终止及后段阈值核对通过。
- nominal 两组重现 EXP-011；76 份归档输入 SHA256 和文档链接核对通过，图已查看。权重哈希不变。
- 全仓门禁在临时完整源码副本 `/tmp/exp012-validation-RaCVqw` 执行，复用现有 venv，禁止同步依赖。Ruff 在副本重排 6 个已有文件并自动修正 3 项后通过，未回写这些无关更改；本轮 Python 文件单独 Ruff 检查通过。Mypy 通过；`make check` 被既有 Pyright 10 个错误、1 个警告阻塞；`make test` 在收集时因 `TensorResetRandomizationPayload` 缺失失败。
- 具体日志：工作区 `outputs/exp012_make_check.log`、`outputs/exp012_make_test.log`。本轮未创建或合并 PR，不宣称全仓或真机通过。

设计与结果见 [EXP-012](../../experiments/rma/EXP-012_damping_diagnosis.md)，可复查证据见 [归档](../../results/rma/EXP-012/README.md)。

## 2026-10-27：EXP-011 固定负载诊断

新增 Hydra `rma_eval` 条件组、`--eval-condition`、真实摩擦/负载 trace 列及串行诊断/分析脚本。
训练默认不选择该配置组；没有新增训练、安装依赖或修改模型参数。

验证命令（GitHub 工作副本，现有 WSL UniLab 环境）：

```bash
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  -m unittest discover -s tests/rma -p 'test_*.py'
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  -m unittest discover -s tests/rma -p test_rendering.py -k controlled_payload
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync ruff check \
  scripts/train_rma.py scripts/evaluate_rma.py scripts/run_exp011_payload.py \
  scripts/analyze_rma_payload.py scripts/archive_exp011.py \
  rsl_rl/unilab_rma/evaluation_conditions.py rsl_rl/unilab_rma/evaluation_trace.py \
  tests/rma/test_evaluation_conditions.py tests/rma/test_evaluation_trace.py tests/rma/test_rendering.py
```

- 全套 57 项 RMA 测试通过；随后新增的受控参数 CLI 回归测试单独运行 1 项通过。Ruff 和 diff 空白检查通过。
- 单变量解析测试确认仅质量分布改变；默认训练随机化、速度范围和动作缩放保持原值；兼容旧 nominal 开关。
- 在原 1.3.3 运行环境中完成 10 步冒烟及六组正式 1000 步回放。六组均无异常终止，全部 6000 行的实际摩擦和负载标签检查通过。
- 逐步 RMSE 与原报告一致；零负载 teacher/student 重现 EXP-010 指标，误差小于 `2e-8`。
- 新归档 95 份输入的 SHA256、相关文档链接与筛查阈值检查通过。图已人工查看。仅一个固定 seed，结论不扩展到所有负载/摩擦/初始状态。
- WSL 源码按文件/函数增量同步，原件和哈希备份于 `runs/rma/EXP-011/code_sync_20261027_223012`；保留原 UniLab/Genesis 环境。

全仓 `make check` 与 `make test` 在 `/tmp/exp011-validation-*` 的独立源码副本执行，设置
`UV_PROJECT_ENVIRONMENT=/home/abc/unilab--/.venv UV_NO_SYNC=1` 与副本 `src/rsl_rl/scripts` 的 PYTHONPATH。
Mypy 通过；Pyright 仍有 10 个既有框架类型错误。全仓测试仍因已安装 UniSim 缺失 `TensorResetRandomizationPayload` 在收集阶段失败。
日志：工作区 `outputs/exp011_make_check.log`、`outputs/exp011_make_test.log`。这些阻塞未通过升级环境或修改原训练框架绕过。
本轮没有合并 PR，也不宣称整个 fork 的 1.3.4 运行兼容性通过。

## 2026-10-27：EXP-008 确认与 EXP-009/010 归档

本轮新增 EXP-009 历史速度扫描、EXP-010 单变量配置和归档、实验总索引，并更新入口页与当前步骤。
PR 基线为 `docs/exp007-genesis-control-diagnostics`，不修改上游框架或现有运行环境。

在 GitHub 工作副本目录中使用现有环境：

```bash
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync python \
  -m unittest discover -s tests/rma -p 'test_*.py'
env VIRTUAL_ENV=/home/abc/unilab--/.venv uv run --active --no-sync ruff check \
  scripts/archive_exp009.py scripts/archive_exp010.py \
  rsl_rl/unilab_rma/evaluation_diagnostics.py rsl_rl/unilab_rma/evaluation_trace.py \
  tests/rma/test_speed_range_config.py
git diff --check
```

- 53 项 RMA 测试通过。归档工作没有启动新的正式训练或物理回放。
- EXP-009 共 13 次、EXP-010 共 34 次完整评估；逐步重算的 RMSE 与原报告一致。
- 353 份已复制/压缩输入的 SHA256 验证通过；实验入口和相关页面的 58 个相对链接检查通过。
- `.gitattributes` 对两个新证据目录禁止行尾转换；历史空白保留，不进行 whitespace 修复。Ruff 也排除这两个冻结证据目录，避免 `make check` 自动改写其哈希。
- PT、ONNX、TensorRT engine、资产和完整 TensorBoard events 没有加入 Git；EXP-010 的模型路径和哈希记录在 manifest 中。
- EXP-009 历史 Genesis 日志未保存模型哈希，不用归档时的文件伪造训练时证明。

全仓 `make test-all` 在 `/tmp/exp010-publication-validation-*` 的完整源码副本中执行：
`UV_PROJECT_ENVIRONMENT=/home/abc/unilab--/.venv UV_NO_SYNC=1 make test-all`，并设置副本的 `src/rsl_rl/scripts` 为 PYTHONPATH。
自动格式化仅作用于临时副本，未改写归档证据；mypy 通过，Pyright 仍报告 10 项未修改框架模块的错误，包含现有 `unisim` 缺失的能力字段和可选值检查。
由于前置类型检查失败，后续全仓测试未运行，不能报告成全仓通过。
完整本地日志为工作区 `outputs/exp010_publication_make_test_all.log`。
PR 保持 Draft，未执行合并，也未升级依赖或改写原训练目录来消除门禁错误。

以下保留早期验证，不能将其中的“尚未训练/尚未回放”当作 2026-10-27 的当前状态。

## 2026-10-23：历史验证

本轮新增：47 项 RMA unittest 通过；已有 EXP-003 三组 CSV 成功生成九张图。
1 环境 × 500 步新增控制诊断与原评估器的 transitions.csv 逐字节一致。
独立无步进写入检查确认当前 1.3.3 快速路径目标映射错误，普通路径误差为零。
EXP-004 定点修复后 24 个非零目标映射检查和 500 步真实诊断均为零映射误差；
EXP-005 两组各 1 次更新 CPU 冒烟通过，正式训练尚未进行。最终 `make test-all` 再次运行：ruff/mypy 通过，
仍被未修改框架文件中的 10 个 Pyright 错误、3 个警告阻塞。

## 已通过

- 导入本地 RMA 增量层及精选实验数据；数据汇总严格匹配 6 份 JSON 和 3000 行训练 CSV。
- `uv run --no-sync python scripts/report_rma.py`：生成汇总 CSV 与两张静态图；图表已人工查看。
- `uv run --no-sync python -m unittest discover -s tests/rma -p 'test_*.py'`：41 项通过，包含追踪开关不改变动作、终止状态对齐、控制映射、单变量配置及旧模型防覆盖检查。
- `cmake -S deploy_cpp -B build/rma -DCMAKE_BUILD_TYPE=Release`：配置成功。
- `cmake --build build/rma -j2`：构建成功。
- `ctest --test-dir build/rma --output-on-failure`：3/3 通过（并发一致性、mock 控制和 12 个非零 one-hot 动作的执行器映射）。
- `make check` 中的 ruff format/check、`mypy src/unilab`：通过。

核心测试与报告脚本使用现有 WSL Python 环境。C++ 为 GNU 11.4.0、CMake 生成的 Release 构建。
没有追加 Go2 长训，没有更改用户运行目录的原模型或基线仿真配置。
新增独立任务 `rma_forward_no_pose`，只关闭默认站姿偏离惩罚；Hydra 完整解析对比只差这一项。
在原 1.3.3 运行目录中完成 2 环境 × 24 步 × 1 次更新的 CPU 训练冒烟测试，checkpoint 与日志保存成功。
随后 2 环境 × 3 步追踪评估成功；惩罚分项为 0，新任务 YAML 已存入快照，原基线模型 SHA256 不变。
随后用户已完成正式 3000 次更新与三个种子评估，未发现实质前进改善，见 EXP-003 记录。

原 1.3.3 运行目录中已执行一次真实追踪评估：`teacher_forward_v1.pt`、种子 123、8 环境 × 1000 步，
生成 8000 行 CSV、独立 JSON 与三张图。全程速度/RMSE 与此前该模型同种子的报告一致。
逐行验证分项 rate 之和乘 0.02 与实际 reward 的最大误差约 `7.98e-09`。
完整压缩 CSV、摘要、配置记录及图见 `results/rma/diagnostics/EXP-002/seed123/`。
这只验证 1.3.3 中的新增评估入口，不等于 1.3.4 真实训练完成兼容。

使用旧学生权重重新导出 ONNX，12 组输入数值检查通过，最大误差 `2.682209e-07`。
导出元数据已区分策略关节顺序与场景执行器存储顺序；C++ 输出边界已按映射散射。
ONNX 权重图本身未加排列；尚未用真实机器人或 TensorRT 机器人闭环验证本次修正。

## 完整门禁尚未通过

在本 fork 1.3.4 源码上，复用了已有 1.3.3 的 WSL 环境运行完整门禁：

```bash
UV_PROJECT_ENVIRONMENT=/home/abc/my_unilab/.venv UV_NO_SYNC=1 make check
UV_PROJECT_ENVIRONMENT=/home/abc/my_unilab/.venv UV_NO_SYNC=1 make test-all
```

Pyright 报告上游现有框架文件的 10 项错误和 3 项警告，包括缺失的 packed-reset/capability API、
未解析导入与可选值检查。报错位置没有被本次改动修改。
依赖/源码版本不一致是已观察到的限制，尚未证明这是所有错误的唯一原因。
`make test-all` 因前置类型检查未通过而未到达后续全仓测试阶段，不能报告成全仓测试通过。
未为通过门禁而升级正在使用的训练环境或更改上游框架代码。

若创建 PR，应保持 Draft；本地核心验证不替代完整门禁和当前 head 的远端 CI。
1.3.4 分支下的真实 Go2 训练、旧 checkpoint 行为兼容、TensorRT/真机与跨引擎测试未在本次执行。

## 历史数据边界

发布的运动指标是已有本地 1.3.3 运行副本产生的结果，不是当前 1.3.4 分支重跑的结果。
`results/rma/forward_v1/config_snapshot` 是训练完成后从仍在使用的工作副本采集的配置，
并非训练开始时自动保存的不可变快照；不能据此补造完整历史溯源。
发布副本的 `base.yaml` 仅清除了行尾空白，未修改 YAML 参数；原运行文件的哈希另有记录。
原运行配置、CSV 与来源 SHA256 记录见 `results/rma/provenance.json`；
checkpoint SHA256 见 `results/rma/forward_v1/checkpoint_metadata.json`。
