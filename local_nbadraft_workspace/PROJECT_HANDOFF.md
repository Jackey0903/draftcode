# NBADRAFT 新一轮协作 Handoff

## 先读这个

这是 `/Users/wuguangyu/Desktop/NBADRAFT` 项目的接手说明。用户准备开启新一轮协作，希望下一个窗口的 Agent 不要从零理解项目。

当前项目不是单纯后端 API 了。它已经演化成一个 NBA Draft / AWS Hackathon 方向的组合项目:

- 一个确定性 NBA Draft milestone 数据库与 FastAPI 答题服务。
- 一个绿黑 EVA / Matrix 风格的 10 页路演网页。
- 一套 AWS 云原生多智能体选秀作战室叙事、架构图、设计资产和实现文档。

不要把这个项目误判成已经部署到 AWS 的生产系统。当前可确认的是本地文件、静态路演页、后端代码和设计/架构文档。之前 AWS 新手抵扣金任务是另一个操作任务，和这个项目是否已部署无直接关系。

## 当前可见状态

Safari 当前打开:

`file:///Users/wuguangyu/Desktop/NBADRAFT/index.html`

页面标题:

`REDRAFT · 选秀作战室 — NBA 选秀预测作战室`

当前是 10 页路演页，右侧导航显示 `10 / 10`。最后一页主题是 `SUBMISSION LOCK / 提交锁定 / LOCKED`，交付物文案写的是:

`CDK + 作战室记录 + 答题卡(30 顺位 + 置信度)+ ≤60s 视频`

## 用户大方向

用户想做的是一个 NBA 选秀预测作战室/Agent 项目，用于黑客松或路演。核心叙事是:

- 选秀预测不是单纯排 Big Board。
- 要拆开两个问题: `他有多强` 和 `他会在哪被选`。
- 用三路信号: `天赋 Talent`、`专家 mock Expert`、`资金/赔率 Money`。
- 重点抓两轴背离: `天赋 vs 市场`、`专家 vs 资金`。
- 把分歧当成 alpha，而不是噪声。
- 系统像一个 30 队 GM 作战室，而不是一个普通模型。

路演里常用关键词:

- `QuantDraft30`
- `NBA Draft Agent`
- `选秀作战室`
- `三信号融合 + 两轴背离`
- `30 位独立人格 GM`
- `蒙特卡洛作战室`
- `实时情报 + 线移动`
- `红队 + 可审计推理`

## AWS 技术叙事

路演当前叙事强调 AWS 云原生架构:

- `Fargate`: 跑 Playwright/headless Chrome 爬虫，处理 Lambda 不适合的重任务。
- `S3`: 存 mock、赔率、新闻和情报抓取结果。
- `DynamoDB`: 存结构化数字和作战室状态。
- `Bedrock Agents`: Commissioner + 多个子 Agent。
- `Bedrock KB/RAG`: 检索散文报告和新闻情报。
- `Guardrails`: 防 prompt injection，尤其因为系统会吃外部网页内容。
- `Step Functions Distributed Map`: 并行跑 1000+ 次 Monte Carlo。
- `API Gateway / KMS / IAM / X-Ray`: 交付、安全、权限和 trace。

注意: 这是路演/架构设计叙事。除非你实际检查部署产物，否则不要说 AWS 端已经部署完成。

## 主要文件

### 路演页

- `index.src.html`: 10 页主路演源文件，优先改这里。
- `index.html`: 由 `build_fonts.py` 从 `index.src.html` 生成的自包含版本，当前 Safari 打开的就是它。
- `index.before-green-eva-redesign.html`: 绿黑 EVA 重设计前备份。
- `index.backup-8slide.html`: 旧 8 页版本备份。

改主路演时优先编辑 `index.src.html`，然后运行:

```bash
cd /Users/wuguangyu/Desktop/NBADRAFT
python3 build_fonts.py
```

`build_fonts.py` 会把得意黑和 FusionPixel12 字体子集化并 base64 内嵌，重新生成 `index.html`。

### 架构图

- `选秀作战室_架构图.src.html`: 架构图源文件。
- `选秀作战室_架构图.html`: 由 `build_fonts.py` 生成的自包含架构图。
- `选秀作战室_架构图_静态版.html`
- `选秀作战室_架构图_循环版.html`
- `diagram/draft-war-room-architecture-v3.svg`

同样优先改 `.src.html`，再跑 `python3 build_fonts.py`。

### 后端 API

- `app/main.py`: FastAPI 入口。
- `app/models.py`: SQLAlchemy 模型。
- `app/snapshot.py`: snapshot 构建。
- `app/milestones.py`: 七个 milestone 的确定性 SQL 计算。
- `app/etl.py`: Excel 数据导入。
- `tests/test_milestones.py`: 里程碑测试。
- `README.md`: 后端运行说明。
- `docker-compose.yml`: Postgres + API。

这个后端的定位是确定性答题服务，不依赖 LLM 推理。旧 handoff 主要写的是这个部分。

### 研究和设计资料

- `research/2016_pre_june_first_round_redraft.md`
- `research/2016_pre_june_first_round_redraft.csv`
- `选秀作战室_DraftWarRoom_实现文档·终版v3(1).md`
- `选秀作战室_PPT大纲.md`
- `黑客松路演PPT_design点.md`
- `绿黑黑客松视觉模板候选.md`
- `设计元素/`: 设计规范、组件、动效资产、验收规则。
- `EVA_Matrix_故障字标融合试验.html`
- `EVA_Matrix_故障字标融合试验_5秒.mp4`

## 已确认的本地事实

- 项目目录不是 git 仓库，`git status` 会报 `not a git repository`。
- Safari 当前打开的是本地 `index.html`，页面能正常显示。
- `build_fonts.py` 明确说明: 改 `index.src.html` 后跑它可幂等重建 `index.html`。
- `build_fonts.py` 同时处理 `index.src.html -> index.html` 和 `选秀作战室_架构图.src.html -> 选秀作战室_架构图.html`。

## 下一轮协作建议

如果用户没有给明确任务，先问一句他要继续哪条线，不要直接大改:

- 路演内容打磨: 更像黑客松评委听得懂的 60 秒 pitch。
- 视觉与交互: 检查 10 页页面是否有文字重叠、移动端问题、字体缺字、滚动体验问题。
- 架构图: 把 AWS 多智能体架构做成更清晰、可讲述的版本。
- 后端 API: 继续补真实数据导入、milestone 答题、测试和 Docker 验证。
- 提交包: 整理 CDK/作战室记录/答题卡/视频脚本，避免只停留在路演概念。

如果用户让你直接做，默认先检查真实文件和当前页面，再动手。不要只凭这个 handoff 改。

## 重要表达边界

- 可以说这是“本地路演页/原型/架构设计/后端服务代码”。
- 不要说它已经完整上线到 AWS，除非你查到真实部署。
- 不要把 AWS 新手抵扣金完成误当成此项目部署完成。
- 对外表达要强调“预测概率、置信度、可审计推理”，避免像下注建议。
- 公开赔率只作为预测信号和隐含概率使用，不构成下注建议。

## 快速启动

查看主路演:

```bash
open /Users/wuguangyu/Desktop/NBADRAFT/index.html
```

重建字体内嵌版:

```bash
cd /Users/wuguangyu/Desktop/NBADRAFT
python3 build_fonts.py
```

后端 Docker:

```bash
cd /Users/wuguangyu/Desktop/NBADRAFT
docker compose up --build
```

本地测试:

```bash
cd /Users/wuguangyu/Desktop/NBADRAFT
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

如果只是改路演页，通常不需要启动后端。
