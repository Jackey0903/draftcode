<div align="center">

# 🏀 DraftCode · 选秀作战室

**一座融合「天赋 · 专家 · 资金」三路信号、能自我推演上千次的 NBA 选秀预测 Agent**

*我们没有训练一个预测模型，而是重建了一座拥有 30 位独立人格 GM 的选秀作战室——它追踪钱的流向，把信号间的背离变成 alpha，并为每个顺位给出带置信度、可解释、可审计的预测。*

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-gpt--5.5-10a37f)
![Engine](https://img.shields.io/badge/Monte%20Carlo-1500%20draws-f4a93b)
![AWS](https://img.shields.io/badge/AWS-Serverless%20%2B%20SAM-FF9900?logo=amazonaws&logoColor=white)
![Tests](https://img.shields.io/badge/tests-75%20passing-brightgreen)
![Lint](https://img.shields.io/badge/lint-ruff-261230)
![Deps](https://img.shields.io/badge/core%20deps-zero-success)

<sub>AWS Summit Shanghai 2026 · 「模拟球探」24h 黑客松 · 评分：代码 30% / 路演 30% / 预测 40%</sub>

</div>

---

## 目录

1. [这是什么](#what)
2. [系统架构](#arch)
3. [五大创新点](#edges)
4. [核心原理](#core)
5. [快速开始](#quickstart)
6. [最终预测](#result)
7. [Agent 一览](#agents)
8. [AWS 云原生工程](#aws)
9. [技术栈](#stack)
10. [仓库结构](#repo)
11. [合规与诚实说明](#ethics)

---

<a id="what"></a>

## 📌 这是什么

DraftCode 把 2026 NBA 选秀预测当成一场**博弈**，而非一道有标准答案的题：

- **不为「整张名单全对」优化**（概率 ≈ 0），而为**每个顺位的期望得分**优化。
- **以市场为锚、天赋为调整项**；市场再分两层——**专家（mock）+ 资金（赔率）**。
- 在**信号背离处**用 gpt-5.5 深度推理破平局——分歧，就是 alpha。

**最终产物**：一张可提交的**答题卡**（30 顺位 + 7 里程碑，每项带置信度）、一座**可审计**的作战室记录、一套**全 Serverless** 的 AWS 蓝图。

---

<a id="arch"></a>

## 🏛 系统架构

<div align="center">

<img src="docs/architecture.png" alt="DraftCode 系统架构 — 三路信号融合 → 蒙特卡洛 → 答题卡，跑在 AWS Serverless 底座上" width="100%">

<sub>矢量源 · <a href="docs/architecture.svg">docs/architecture.svg</a></sub>

</div>

> **端到端一张图**：数据采集 → 三路信号（天赋 / 专家 / 资金）→ 融合 + 两轴背离（gpt-5.5，LLM-once）→ 30 GM 偏好 → 蒙特卡洛 ×1500（Step Functions Distributed Map 并行）→ 30 顺位 + 置信度 / 7 里程碑 / 答题卡 / 审计，全部跑在 AWS Serverless 底座上。

<details>
<summary>数据流 · Mermaid 可编辑版</summary>

```mermaid
flowchart TD
    T["🧬 天赋信号<br/>手册速率指标 / 体测"]:::sig
    E["📋 专家信号<br/>多源 mock 共识"]:::sig
    M["💰 资金信号<br/>赔率 de-vig 隐含概率"]:::sig
    T & E & M --> F{"三信号融合 + 两轴背离<br/>gpt-5.5 在分歧处破平局"}
    F --> P["30 GM 偏好函数<br/>w·(天赋+需求+人格+专家+资金)"]
    P --> MC["蒙特卡洛 ×1500<br/>顶部顺位锚定去水赔率"]
    MC --> B["🎯 匈牙利指派<br/>30 顺位 + 边际概率(置信度)"]
    MC --> Q["📐 7 里程碑<br/>与最终板自洽"]
    B & Q --> A["📋 答题卡 answer_card.xlsx"]
    B & Q --> AU["🔍 审计追踪 audit.json/md"]
    classDef sig fill:#141c30,stroke:#f4a93b,color:#eef2fb;
```

</details>

---

<a id="edges"></a>

## ✨ 五大创新点

| | 创新点 | 一句话 |
|:--:|--|--|
| 🥇 | **三信号融合 + 两轴背离** | 天赋 × 专家 × 资金三路融合；轴① 天赋 vs 市场、轴② 专家 vs 资金背离触发 gpt-5.5 裁决。**钱是最快的情报。** |
| 🥈 | **30 位独立人格 GM** | 每队一个带「决策 DNA」的 GM Agent（顺位 / 缺口 / 人格 / 时间线）；一份模板，运行时注入 30 套人格。 |
| 🥉 | **蒙特卡洛作战室** | 自我推演 1500 次 → 每顺位概率分布 = 诚实置信度；**顶部以去水赔率为采样锚**；同批模拟顺手答 7 道里程碑。 |
| 🏅 | **实时情报 + 资金线移动** | 锁定前扫描新闻与赔率漂移，抓最后 48h 变化并重跑（字母哥交易已落地验证）。 |
| 🎖 | **红队 + 全程可审计** | 魔鬼代言人 Agent 挑战共识；每个预测产出可复现的证据档（数据 / 解释 / 背离 / 赔率来源）。 |

---

<a id="core"></a>

## 🧠 核心原理

**LLM-once 解耦** —— gpt-5.5 只在「产 30 GM 偏好函数」与「裁决信号背离」时各跑一次；蒙特卡洛是纯算力采样，1500 次轻松跑完。**昂贵推理与廉价采样彻底解耦**，是成本与速度的关键。

**资金信号 · 赔率 de-vig**（v3 新核心，公开赔率仅作预测信号，不构成下注建议）：

```text
美式赔率 → 隐含概率:  -X → X/(X+100)   |   +X → 100/(X+100)
去水 de-vig (比例法):  p_i = q_i / Σq_j      (同一顺位市场, 消抽水使 Σp = 1)
跨书共识:             多书同一(顺位, 球员)取均值, 按顺位归一
```

**三处接入引擎**：

1. **偏好叠加** `w_money · odds_signal`
2. **蒙特卡洛顶部置信度锚定市场** `(1-λ)·softmax + λ·odds`（λ 随顺位衰减）
3. **轴② 背离**（专家 mock vs 资金 odds）`|gap| ≥ 8` 触发 gpt-5.5 裁决

> 实测真实赔率（ESPN + OddsShark，gpt-5.5 解析 + de-vig）：当日顶部专家与资金高度同向，轴② 触发 0 次（= 高置信锁定），裁决器仅在二者分歧时出手。
>
> **向后兼容**：任一信号源缺失时优雅降级；不跑 `odds` 时全链路与纯天赋 + 专家路径**逐字节一致**。

---

<a id="quickstart"></a>

## 🚀 快速开始

```bash
make install      # 安装 (uv, 零第三方核心依赖)
make test         # 75 tests
make simulate     # 蒙特卡洛 Draft Twin (样例数据)
```

<details>
<summary>完整选秀预测流程（真实 2026 数据，需 gpt-5.5 网关）</summary>

```bash
# 设置 gpt-5.5 网关 (本地 Codex 反代, 或远程 EC2 网关)
export DRAFTCODE_LLM_BASE_URL=http://<gateway>:8787  DRAFTCODE_LLM_API_KEY=<key>

draftcode ingest  --source data/raw/official --out data/processed --divergence-llm   # ① 官方 107 参选人 + 轴① 背离
draftcode intel   --news-text "<交易新闻>" --apply                                    # ② 实时情报换签
draftcode market  --mock-file CBS=… --mock-file SI=… --apply                          # ③ 专家共识 (mock)
draftcode odds    --odds-file ESPN=… --odds-file OS=… --apply                         # ④ 资金信号 (赔率 de-vig) + 轴② 背离
draftcode warroom --data-dir data/processed --output-dir outputs/llm                  # ⑤ 30 GM 偏好 (gpt-5.5)
draftcode simulate --data-dir data/processed --output outputs/twin.json --draws 1500  # ⑥ 蒙特卡洛 + 赔率锚
draftcode answer  --data-dir data/processed --out outputs/answer_card.xlsx            # ⑦ 答题卡
draftcode audit                                                                       # ⑧ 合并预测+解释+背离+GM+红队 → 证据档
```

</details>

> **前端**：`web/draft_room.html` 是一份**自包含单文件**的六幕渐进式作战室（封面 → 上线 → 天赋 → 市场 → 融合 → 终榜球星卡）；浏览器直接打开，加 `?demo=1` 自动演示。

---

<a id="result"></a>

## 📊 最终预测

官方板 + 已确认交易（完整 30 顺位见 `outputs/answer_card.xlsx`）。

<table>
<tr><td valign="top">

| # | 球队 | 球员 |
|--:|--|--|
| 1 | Washington Wizards | AJ 迪班萨 |
| 2 | Utah Jazz | 达林 彼得森 |
| 3 | Memphis Grizzlies | 卡梅隆 布泽尔 |
| 4 | Chicago Bulls | 凯莱布 威尔逊 |
| 5 | Los Angeles Clippers | 基顿 瓦格勒 |
| 6 | Brooklyn Nets | 迈克尔 布朗 |
| 7 | Sacramento Kings | 达柳斯 阿卡夫 |
| 13 | **Milwaukee Bucks** ⟵ 字母哥交易 | 小拉巴伦 菲隆 |

</td><td valign="top">

**7 里程碑**（与左侧板自洽）

| 题 | 答案 |
|--|--|
| Q1 长臂展 (4–14 顺位) | 2 人 |
| Q2 助跑弹跳前 3 入首轮 | 1 人 |
| Q3 首轮中锋总数 | 2 个 |
| Q4 首个中锋落点 | 第 10 顺位 |
| Q5 国际球员总数 | 5 人 |
| Q6 贡献最多机构 | 密歇根大学 |
| Q7 手掌长度前 5 入首轮 | 2 人 |

</td></tr>
</table>

> 持签球队对齐官方 30 队名单；**字母哥交易经核实为官方**（NBA.com / ESPN，密尔沃基获第 13 签）。

---

<a id="agents"></a>

## 🤖 Agent 一览

| Agent | 命令 | 职责 | 产物 |
|--|--|--|--|
| 官方归一化 | `ingest` | 107 参选人 + 体测/手册 + 轴① 背离 (gpt-5.5) | `prospects.csv` |
| 实时情报 | `intel` | 新闻 → 换签/缺口 (gpt-5.5)，字母哥案例验证 | `draft_order.csv` |
| 专家市场 | `market` | 多源 mock → 共识 (中英文名匹配) | `mock_signals.csv` |
| 资金赔率 | `odds` | 赔率 → de-vig 隐含概率 + 轴② 背离 | `odds_signals.csv` |
| 30 GM 作战室 | `warroom` | 30 队人格偏好 + 解释 + 红队 (LLM-once) | `outputs/llm/*.json` |
| 蒙特卡洛孪生 | `simulate` | 1500 次采样 + 赔率锚 + 匈牙利指派 | `twin.json` |
| 答题卡 / 审计 | `answer` / `audit` | 提交卡 + 可复现证据档 | `answer_card.xlsx` · `audit.md` |

> 所有吃外部内容的抓取都在**引擎外**（WebFetch / 爬虫 / 人工注入文本）；引擎只做结构化、聚合、应用、审计——干净、确定、可复现。

---

<a id="aws"></a>

## ☁️ AWS 云原生工程

全 Serverless（零 EC2 业务逻辑）+ Serverless 容器 + IaC + 全链路安全 + Well-Architected。

<details>
<summary>架构映射 / Scenario Swarm / 部署命令</summary>

| 层 | 服务 |
|--|--|
| 采集（容器） | EventBridge + **Fargate**（headless 爬虫，含赔率）+ ECR |
| 存储 | S3 (KMS) · DynamoDB 台账 (KMS) |
| 编排 / 模拟 | **Step Functions Distributed Map**（1000+ 蒙特卡洛并行） |
| 计算 | Lambda 容器镜像 |
| 输出 | API Gateway + Lambda |
| 安全 | KMS CMK · Secrets Manager · 最小权限 IAM · Bedrock Guardrails（条件） |
| IaC | AWS SAM (`infra/template.yaml`，`sam validate --lint` 通过) |

**Scenario Swarm**（Distributed Map 并行蒙特卡洛）：

```text
PrepareRun → N 个分片 payload → Distributed Map (action=simulate_shard)
  → 各分片写 runs/<run_id>/shards/<i>.json → Aggregate 合并 → twin.json + DynamoDB
```

每分片独立随机流 `seed + shard_index * 1000003`；单分片（index 0）与本地 `run()` **逐字节等价**。

**部署**：

```bash
make sam-deploy STACK_NAME=draftcode AWS_REGION=us-east-1 DATA_S3_PREFIX=processed
make upload-data S3_BUCKET=<bucket> DATA_S3_PREFIX=processed
aws stepfunctions start-execution --state-machine-arn <PredictionWorkflowArn> --region us-east-1
```

</details>

---

<a id="stack"></a>

## 🛠️ 技术栈

- **语言 / 工具**：`Python 3.11` · `uv` · `Typer` / `Rich` CLI
- **依赖**：核心引擎**零第三方依赖**（`openpyxl` 仅在 official / answer 层）
- **LLM**：`gpt-5.5`，经本地 Codex 反代 / EC2 OpenAI 兼容网关（**非 Bedrock**——账号地区受限的真实约束）
- **算法**：赔率 de-vig · softmax 温度采样 · 蒙特卡洛 · **匈牙利指派** · 置信度加权融合

---

<a id="repo"></a>

## 📁 仓库结构

<details>
<summary>展开</summary>

```text
src/draftcode/
  official.py     官方数据归一化 + 轴① 背离        odds.py        赔率聚合 Agent (de-vig)
  intel.py        实时情报 Agent                  market.py      专家共识 Agent
  divergence.py   gpt-5.5 两轴背离裁决            preference.py  三信号偏好函数
  simulate.py     蒙特卡洛 Draft Twin (+赔率锚)    warroom.py     30 GM 编排
  answer.py       答题卡 writer                  audit.py       可审计追踪合并器
  llm_client.py   gpt-5.5 客户端                 cli.py         命令行入口
infra/template.yaml         AWS SAM 蓝图
web/draft_room.html         六幕渐进式作战室前端 (自包含单文件, ?demo=1 演示)
scripts/build_frontend.py   前端数据生成器 (twin + audit → 刷新数据块)
design.md · spec.md         前端设计稿 / 技术规格
docs/architecture.{png,svg} 系统架构图
docs/                       架构 / 创新策略 / AWS 计分 / Agent 设计
```

</details>

---

<a id="ethics"></a>

## ⚖️ 合规与诚实说明

- 公开赔率**仅作预测信号（隐含概率）**使用，不构成、不提供任何下注建议——标准概率预测方法。
- 交易 / 赔率 / mock 等第三方新闻**真假自行核验**（字母哥交易已 web 核实 = 官方）。
- gpt-5.5 采样跨 run 有波动，**缓存即任一次提交的唯一真值**；文档结果均按实测如实标注。
- 球员池严格 = 官方 107 参选人名单；不预测不可能被选的人。

<div align="center"><sub>Built for AWS Summit Shanghai 2026 · 模拟球探</sub></div>
