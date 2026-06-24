# DraftCode 选秀作战室 · 前端技术规格（spec.md）

配套 `design.md`。目标产物：**单文件、自包含、零运行时依赖**的 `web/draft_room.html`，
一个**场景状态机**驱动的渐进式电影感演示，支持手动步进与 `?demo=1` 自动时间线。

---

## 1. 技术约束

- 单 HTML 文件；CSS + 原生 JS 内联；字体/头像 base64 内嵌；**不引外部 JS 库**。
- 唯一外部请求 = 球队 logo（`cdn.nba.com`，失败回退队色徽章）。可断网展示（logo 退化）。
- 不破坏数据管线：保留 `const PICKS=[…];/MS/AUDIT/RT` 字面量（`build_frontend.py` 正则替换）。
- 全程 `prefers-reduced-motion` 降级；移动端可用（≥360px）。

## 2. 场景状态机

```
states: BOOT → ONLINE → S1_TALENT → S2_MARKET → S3_FUSION → BOARD
controller: { i, go(n), next(), prev(), play(), pause() }
triggers: 点击主按钮 / 步骤导航 dots / 键盘(→ ← 空格 Home End Esc) / demo 自动定时
```

- 每个 state 是一个全屏 `<section class="scene">`，绝对定位叠放；切换用 `.active` + 进/出动画。
- 切换时：当前幕播放**退场**（白闪/擦除），目标幕播放**入场**（级联/揭示）。
- URL：`?demo=1` 启动自动时间线（见 §7）；`#board` 直达终榜（评委可跳过）。
- 顶部进度条 = 当前幕 / 总幕；左侧/底部步骤导航高亮当前幕。

## 3. 各幕规格

### BOOT（封面）
- 元素：密集 matrix canvas（opacity .8）、故障字标、竖排「作戰室」、kicker、底部合规小字、中央 `▶ ENTER` 大按钮（呼吸 + hover 故障）。
- 交互：点击/回车/空格 → `whiteFlash` + glitch + 推进 → ONLINE。

### ONLINE（启动）
- 终端日志逐行打字（`FusionPixel12`，~7 行，每行 120–220ms），含进度点。
- 完成后 HUD 显影：顶栏（LIVE/项目码/时钟）、三信号灯（talent/market/money 依次亮绿）、步骤导航。
- `开始推演` 按钮或自动 → S1。

### S1_TALENT
- 视觉：prospect 名牌**级联飞入**聚成竖向 Big Board（取前 ~14 即可，性能）。
- 分析卡（玻璃面板，右/侧）：天赋方法三行 + 一个"天赋≠顺位"的反差案例。
- 交互：hover 名牌 → tooltip（天赋分/位置）；点"下一步"或自动 → S2。

### S2_MARKET
- 视觉：左"专家 mock"列 + 右"资金赔率"列，两股**流光**汇入中轴；
  背离处（示例 2 条）迸发红/琥珀脉冲 → 弹出 `gpt-5.5 裁决` 小气泡。
- 分析卡：两轴背离释义 + de-vig 公式 chip（`-550→84.6% / +290→25.6% / p=q/Σq`）。
- 交互：切换 AXIS1/AXIS2；点背离看裁决文案。→ S3。

### S3_FUSION
- 视觉：三股信号流沿 SVG 路径**汇合**成主干（dash 流光）；
  然后 **蒙特卡洛粒子场**：N 个点高速翻动 → 收敛，右侧"draws"计数 `count-up → 1500`；
  收敛完毕，板位逐条结晶；锁定位盖下绿色 `LOCK` 钢印（轻微震颤 + 辉光）。
- 分析卡：一致锁定 / 背离深挖；公式 `confidence = marginal[slot][pick]`。→ BOARD。

### BOARD（终榜 + 球星卡）
- 30 顺位**球星卡**网格（响应式 2–3 列；前 1–2 张可做大卡）：
  定妆照 + 队徽角标 + 队色描边 + 顺位号 + 命中置信条 + (lock?) `LOCK` 标。
- 点击卡 → **FLIP/翻牌**放大为详情球星卡（modal）：
  大头像、命中率环（conic）、六维属性**雷达**（SVG）、身高/臂展/位置三栏、六条属性条、`球探评分·模型估计` 注脚、交易签标记。
- 右/下副区：里程碑 7 题答题卡（像素卡）+ 红队 8 问与可审计统计（终端日志风）。
- 顶部：`▶ 一键演示`（回放全流程）、步骤导航、`置顶/重播`。

## 4. 组件清单（实现单元）

1. `MatrixRain(canvas)` — 绿色数字雨，密度随场景（封面密、内容压暗）；reduced-motion 关闭。
2. `GlitchTitle` — EVA RGB 错位故障字标（CSS keyframes，已有配方）。
3. `SceneController` — 状态机 + 进/退场编排 + 键盘/导航/demo 定时。
4. `Transition` — 白闪震颤 / 全屏擦除 / 圆形 clip 揭示（幕间）。
5. `Stepper / HUD` — 顶栏 + 三信号灯 + 步骤导航 + 进度条。
6. `BootLog` — 打字机日志。
7. `TalentBoard` — 级联名牌 + 天赋 tooltip。
8. `SignalFlow` — 双列 + 流光 + 背离脉冲 + 裁决气泡（SVG/CSS）。
9. `MonteCarlo` — rAF 粒子收敛 + draws count-up + LOCK 钢印。
10. `StarCard`（列表项）+ `StarCardModal`（详情，FLIP）。
11. `Radar(vals,color,size)` — 六维 SVG 雷达（已有实现，移植）。
12. `Avatar(name,size)` + `LogoEl(ab,size)` — 头像（按名取 base64 照片，回退剪影）+ 队徽（CDN+回退）。
13. `Milestones` / `RedTeamAudit` — 像素卡 + 终端日志。
14. `Reveal/CountUp` — IntersectionObserver + setTimeout + scroll 三重兜底（已有，沿用）。

## 5. 数据契约（取 `origin/main` 最新；务必用这版，勿回退）

- `TEAM = { ABBR: [中文名, 颜色hex, nbaTeamId] }`（24 队，含 teamId 供 logo CDN）。
- `PICKS = [[no, ABBR, name, prob, tradeFlag], …]`（30，最新锁定/排序版；锁定位 prob=0.9）。
- `LOCKS = {1,2,3,4,6,7}`（内幕锁定顺位 → 显示 `LOCK` 而非百分比可选）。
- `MS = [[Qid, desc, answer, unit], …]`（最新：2/1/2/10/5/密歇根大学/2）。
- `AUDIT = [[n, label, colorKey], …]`（最新：30/12/0/13/13/8）。
- `RT = [问句, …]`（8）。
- `POS = { name: 'G'|'W'|'B' }`、`ATTR_SEED`、`attrFor(name,pick)` → 六维 + ht/wing（模型估计，标注）。
- `PHOTO_BY_NAME = { 中文名: 'data:image/png;base64,…' }`（按**球员名**键，与顺位解耦；新板新增 5 人补齐后并入；缺失→剪影）。
- 渲染前置 `assert PICKS.length===30`；缺图/缺属性都要优雅降级。

## 6. 动效规格

- 缓动：`cubic-bezier(.2,.85,.25,1)`（入场/位移）；线性（dash 流光）。
- 时长：幕间转场 .5–.7s；级联 stagger 40–60ms；count-up .9s；雷达 pop .6s；翻牌 .45s。
- 关键帧：`whiteFlash / evaGlitch / evaPop / dash / pulse / rpop / flip`。
- `@property --p` 驱动 conic 命中率环动画。
- 性能：单 canvas、rAF 节流；蒙特卡洛粒子 ≤ ~400 点；off-screen 幕暂停其动画。

## 7. 演示 / 录制模式

- `?demo=1`：进页即自动播全流程，节拍对齐 `design.md §4`（总 ~58s），每幕到驻留点停 1–2s 再自动转场；右上角小字 `AUTO`。
- 手动：`→/空格` 下一幕、`←` 上一幕、`Home` 回封面、`Esc` 关球星卡。
- `▶ 一键演示` 按钮 = 触发 demo 时间线（现场点一下即可走完）。
- 可暂停/重播；任意时刻可点步骤导航跳幕。

## 8. 可达性 / 降级 / 性能

- `prefers-reduced-motion`：禁雨/故障/粒子/翻牌，所有幕直接显终态，仍可步进。
- 图片 `loading="lazy"`（base64 即时）；logo `onerror` 回退；字体 `font-display:swap`。
- 键盘可达、焦点可见；modal 有 `aria-modal` + Esc + 点遮罩关闭。
- 移动端：球星卡单列、关闭内联雷达、隐藏导航文字。

## 9. 验收清单

- [ ] 封面点击 → 转场 → 作战室，流畅无白屏。
- [ ] 四步（天赋/市场/融合+MC/终榜）各有动画+分析+交互，可前进/后退。
- [ ] 终榜 30 张球星卡，真实定妆照 + 队徽 + 置信条 + LOCK；点开有雷达+属性。
- [ ] `?demo=1` 能在 ~60s 内自动走完全流程（录屏可用）。
- [ ] 数据为 main 最新版；`build_frontend.py` 仍各匹配 1 次。
- [ ] reduced-motion 下完整可用；移动端不破版。
- [ ] 单文件可直接 file:// 打开（自包含）。

## 10. 多 Agent 并行构建分工（workflow）

并行产出**独立 JS/CSS 模块字符串**（互不冲突），最后由编排合成单文件并自检：

- **A 视觉底座**：tokens/CSS、matrix rain、扫描线/颗粒/网格、玻璃面板、故障字标、转场关键帧。
- **B 场景状态机 + HUD**：SceneController、Stepper/进度、键盘/导航/`?demo=1` 时间线、BootLog。
- **C 推演幕**：S1 天赋级联、S2 双信号流+背离脉冲、S3 蒙特卡洛粒子+LOCK 钢印（含分析卡文案）。
- **D 终榜 + 球星卡**：StarCard 列表、FLIP 详情 modal、Radar、Avatar/Logo、里程碑、红队/审计。
- **E 数据+资产**：注入 main 最新 PICKS/MS/AUDIT/RT/LOCKS、TEAM+ids、POS/ATTR、PHOTO_BY_NAME（含新 5 人）、字体 base64。
- **合成/验收**：拼装单文件 → 校验 4 数据块正则、JS 无错、渲染 30 卡、demo 时间线、reduced-motion。

每模块附**最小自检**（结构计数/无语法错）；合成后做整页渲染验证与截图。
