# TrajFix-baselines

用于 TrajFix 相关研究的 SWE-bench 实验底座：固定 HarnessFix 官方仓库版本，调用其中的 mini-swe-agent，在 Docker 中修复真实任务，再用 SWE-bench 官方评测器验收。

**已完成一个真实任务的端到端验证；尚未复现 TrajFix，也尚未运行完整的 HarnessFix 自动诊断与修改闭环。**

## 已验证结果

2026-11-26，SWE-bench Verified 的 `astropy__astropy-12907`：

| 运行 | F2P 通过 | P2P 通过 | Resolved |
|---|---:|---:|---|
| 不修改源码的对照补丁 | 0/2 | 13/13 | false |
| 官方 gold patch | 2/2 | 13/13 | true |
| 模型独立生成的补丁 | 2/2 | 13/13 | true |

模型为 `openai/deepseek-v4-pro`，17 次调用、145.15 秒，提交 504 字节补丁。模型输入没有包含 gold patch 或评测 test patch；最终补丁在新容器中通过官方验收。这是单题运行验证，不能作为完整数据集成功率。

- [验证汇总](examples/verified_run/summary.json)
- [模型补丁](examples/verified_run/model.patch)
- [官方模型评测报告](examples/verified_run/model.report.json)
- [依赖与来源记录](provenance.json)

## 环境

已验证：Linux x86_64、Python 3.10.14、mini-swe-agent 2.2.7、SWE-bench 4.1.0、Docker 29.10.1。SWE-bench 版本固定为 4.1.0，以匹配此处下载的数据格式；不要直接替换为 5.x。

模型使用 OpenAI-compatible API，本机不需要 GPU。任务容器限制为 4 CPU / 16 GiB 内存，禁用容器网络。当前单题镜像逻辑大小约 2.9 GB；VFS 存储需要额外的镜像层和容器副本空间。

本仓库的 Docker 启动脚本针对具备运行嵌套 Docker 权限的 Linux 服务器：使用独立 Unix socket、VFS、无 bridge，不修改已有宿主 Docker。普通受限容器可能没有启动 daemon 所需的权限。运行环境和 Docker 数据位于 `/tmp`，清理或重启后可能需要重建。

## 安装

```bash
git clone https://github.com/yanyi74/TrajFix-baselines.git
cd TrajFix-baselines
bash scripts/bootstrap.sh
source scripts/env.sh
```

`bootstrap.sh` 自动下载 [HarnessFix 官方源码](https://github.com/HarnessFix/HarnessFix)，固定提交 `9167a0b9a58748c73b56c3ee04fdc3437ba0c56e`，应用本仓库的 dry-run 补丁，创建独立 Python 环境并安装依赖。上游代码遵循各自的许可，未复制到本仓库；本地改动保存在 `patches/`。

## 下载题目数据

```bash
mkdir -p data
curl -fsSL 'https://datasets-server.huggingface.co/rows?dataset=princeton-nlp%2FSWE-bench_Verified&config=default&split=test&offset=0&length=3' -o data/verified_rows.json
python scripts/prepare_smoke_data.py data/verified_rows.json
```

脚本检查字段是否完整，生成三条互斥的 smoke 子集和单题 `data/smoke_instance.json`。这些样例来自公开 test split，只用于连通检查；目录名 dev / val / heldout 是本地 smoke 分组，不是数据集官方 split，更不能据此作为正式训练或调参划分。

每条记录的 `repo + base_commit` 指向修复前仓库；`problem_statement` 是模型题目；`patch`、`test_patch`、`FAIL_TO_PASS`、`PASS_TO_PASS` 留给验证与评测使用。Agent 只接收问题描述，并通过工具读取容器内的 `/testbed`。

## 配置模型

```bash
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY、OPENAI_BASE_URL、TRAJFIX_SMOKE_MODEL
python scripts/model_probe.py
```

模型名称格式为 `openai/<网关中的模型名>`。也可用 `TRAJFIX_CREDENTIALS_FILE` 指向已有 dotenv 文件，支持 `AIHUB_API_KEY` 和 `AIHUB_BASE_URL`。凭据不提交到 Git，不传入题目容器，也不写入模型序列化配置。

`model_probe.py` 会发起一次真实模型调用。正式 smoke 最多 20 次调用、15 分钟；未知模型的费用计量可能不可用，不能把代码中的 cost limit 当作可靠的实际扣费硬限额。

## 启动 Docker 与单题运行

在一个独立终端中：

```bash
bash scripts/start_docker.sh
```

脚本会下载 Docker 静态二进制，并保持前台监督 daemon；如果 daemon 已运行则直接返回。另一个终端中：

```bash
cd TrajFix-baselines
source scripts/env.sh
docker pull swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest
python scripts/preflight.py
python scripts/evaluate_smoke.py gold
python scripts/evaluate_smoke.py noop
python scripts/live_rollout.py
python scripts/evaluate_smoke.py model
```

`live_rollout.py` 当前固定运行第一道 Astropy 题目及对应镜像，不是通用批量运行器。官方镜像在 base_commit 上有环境准备提交；脚本核对父提交，以及除 pyproject.toml 和文件权限之外的源码内容一致性。

评测脚本使用官方 SWE-bench 评测器，只设置容器网络和资源限制，不修改测试或评分逻辑。默认生成唯一 run_id，避免变更补丁后误用旧缓存；可以用 `--run-id` 自行指定。

运行输出保存到本地 `results/`，不默认提交到 Git。`results/live_rollout/` 包含完整轨迹、模型补丁和预测记录；评测结果在各次 run_id 目录。重复模型运行会覆盖 live_rollout 输出，做多轮实验前请归档。rollout 自身的 `benchmark_verified=false` 表示生成补丁时尚未评测；最终以对应官方 `report.json` 的 `resolved` 字段为准。

## 离线检查与 HarnessFix pipeline

```bash
source scripts/env.sh
python scripts/smoke_offline.py
bash scripts/run_smoke_pipeline.sh dry-run
```

离线检查使用 scripted 小型加法缺陷，验证执行、轨迹保存和 HTIR 转换，不调用模型，不代表 SWE-bench 成绩。dry-run 验证多阶段命令组织；补丁修复了上游 dry-run 读取尚不存在的评测报告的问题，真实模式仍要求报告存在。

完整 HarnessFix pipeline 还需配置上游 `vendor/HarnessFix/.env` 和 `task_agent/model_registry.json`，以及 `TRAJFIX_MODEL` / `TRAJFIX_ANALYSIS_MODEL`，然后运行 `bash scripts/run_smoke_pipeline.sh run`。它会额外调用诊断与修改模型，当前尚未验证完整闭环。`preflight.py` 的 `ready_for_live_smoke` 与 `ready_for_real_run` 分别表示单题入口和完整 pipeline 的配置检查，不是最终成功保证。

## 与 TrajFix 的关系

本项目起点是阅读 TrajFix: Correcting Failed Trajectories to Scale Verifiable Software-Engineering Data。研究记录中尚未找到可确认的作者官方实现，因此先搭建其 related work 中的 HarnessFix 及 SWE-bench 底座。

TrajFix 关注借助 gold patch 诊断失败轨迹、重放前缀、纠正步骤并续跑；HarnessFix 关注诊断失败后修改 harness。二者不是相同算法。当前已有可运行的基础 agent、模型轨迹与独立测试验收，后续才能加入从头重采样、harness 修改、轨迹纠正等方法对照。

Verified test 样例只用于本次连通演示。后续训练数据生产应使用独立训练任务池，并保持评测集不参与训练和调参。
