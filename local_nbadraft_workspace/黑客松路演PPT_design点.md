# 黑客松路演 PPT design 点

基准方向: 在 `EVA_Matrix_故障字标融合试验.html` 的基础上,继续发展成一套绿黑色、强技术感、适合黑客松路演的演示视觉系统。

## 1. 视觉世界

一句话: **NBA 选秀夜的数据作战室被系统接管。**

关键词:

- 黑绿数据雨
- EVA 式巨大章节字
- 故障发光项目字标
- 玻璃控制台
- 点阵数字
- 选秀板 / agent trace / confidence lock

拒绝:

- 不做普通黑底霓虹绿模板。
- 不做满屏卡片式 SaaS dashboard。
- 不堆 AI 网络图、粒子宇宙、假黑客入侵文案。
- 不让绿色覆盖所有标题、边框、按钮和背景。

## 2. 字体系统

### Display 大字

用途:

- `REDRAFT`
- 章节大标题
- 核心命题页的 2-4 个大字
- 封面主视觉

建议字体:

- `DeyiHei`
- `得意黑`
- 兜底: `SmileySans-Oblique`, `PingFang SC`, `Microsoft YaHei`, sans-serif

使用规则:

- 字号要大,宁可少字也不要小。
- 可以配合 `故障发光字标`。
- 不用于正文和长解释。

### Pixel / Mono 小号技术字

用途:

- 状态 chip
- `READY / LOCKED / ONLINE`
- `GM AGENTS 30`
- pick number
- confidence 数字
- trace log
- 页码、角标、技术标签

建议字体:

- 先用你本机那款像素风字体
- 临时兜底: `OCR-A BT`, `OCR-B 10 BT`, `ui-monospace`, `Menlo`, `Monaco`, monospace

使用规则:

- 小号、高字距、全大写最合适。
- 只承载状态和数据,不要拿它写大段中文。
- 数字可以轻微 glow,但不能糊。

### Body 正文

用途:

- 副标题
- 每页一句解释
- 图注
- 演示说明

建议字体:

- `PingFang SC`, `Microsoft YaHei`, `Inter`, `SF Pro Display`, Arial, sans-serif

使用规则:

- 正文必须足够亮,不要用低透明灰糊掉。
- 每页正文尽量只保留 1-3 行。
- 需要技术感时用 pixel/mono 做标签,正文仍用系统字体。

### EVA 竖排中文

用途:

- 封面或章节接管页的短句,例如 `回到選秀夜`、`數據背離`、`作戰室啟動`。

建议:

- 可以使用 Display 字体,也可以保留明朝/宋体的 EVA 感。
- 如果要统一三字体系统,优先用得意黑或系统宋体兜底。

## 3. 色彩系统

### 主色

- 深黑: `#000402`
- 黑绿背景: `#020805`
- 主绿: `#00ff66` / `#37ff8b`
- 亮白: `#f4fff8`

### 辅助色

- 青色错位: `#62f2ff`
- 红色错位: `#ff4473`
- 琥珀高亮: `#f1c96b`
- 次级文字: `#8caf9b`

### 色彩职责

- 绿色: 系统激活、数据锁定、置信通过、当前状态。
- 白色: 主标题、EVA 接管文字、最重要信息。
- 青/红: 故障错位,只短促出现。
- 琥珀: 核心指标占位、风险、未确定结论。
- 暗绿线框: 控制台边框、流程路径、选秀板分隔线。

## 4. 核心视觉资产清单

### 必选

1. `EVA式数据雨故障章标题`
   - 用途: 封面、重大章节切换、最后收束。
   - 频率: 全套最多 1-2 次。
   - 文件: `设计元素/03_动效资产/20_EVA式数据雨故障章标题.md`

2. `Matrix数据雨背景`
   - 用途: 封面背景、历史回放、系统启动。
   - 频率: 只在封面/章节页明显出现;内容页降低到很暗。
   - 文件: `设计元素/03_动效资产/19_Matrix数据雨背景.md`

3. `故障发光字标`
   - 用途: `REDRAFT`、章节短词、关键命题。
   - 频率: 只给主字标,不要给正文。
   - 文件: `设计元素/03_动效资产/18_故障发光字标.md`

4. `暗色发光展示系统`
   - 用途: 全套底层视觉语言。
   - 要点: 发光少而准,绿色有职责。
   - 文件: `设计元素/02_视觉元素/01_暗色发光展示系统.md`

5. `玻璃控制台系统`
   - 用途: agent war room、选秀板、数据面板。
   - 要点: 固定 2-3 种玻璃面板,不要每页乱写透明度。
   - 文件: `设计元素/02_视觉元素/02_玻璃控制台系统.md`

6. `点阵数字`
   - 用途: 置信度、模拟次数、pick number、页码。
   - 文件: `设计元素/04_界面组件/06_点阵数字.md`

### 推荐

7. `命题强调块`
   - 用途: 解释核心矛盾,例如“天赋 ≠ 顺位”。
   - 文件: `设计元素/02_视觉元素/04_命题强调块.md`

8. `流程路线`
   - 用途: Talent Signal -> Market Signal -> GM Agent -> Monte Carlo -> Audit。
   - 文件: `设计元素/02_视觉元素/05_流程路线.md`

9. `顶部状态Chip`
   - 用途: `SCOUT READY / MARKET LOCKED / GM ONLINE / SIM RUNNING`。
   - 文件: `设计元素/04_界面组件/02_顶部状态Chip.md`

10. `反馈闭环`
    - 用途: 如果做可点击 demo,所有按钮必须有反馈。
    - 文件: `设计元素/04_界面组件/07_反馈闭环.md`

### 谨慎使用

11. `视频展示容器`
    - 用途: 如果嵌入录屏或 demo 视频。
    - 原则: 视频舞台要大,不要缩成小卡片。

12. `交互原型嵌入`
    - 用途: 真要展示可点 demo 时使用。
    - 原则: 一屏只展示一个真实原型。

## 5. 动效清单

### 高冲击动效

1. `EVA式数据雨故障章标题`
   - 用在封面或大章节。
   - 动效节奏: 数据雨 -> 白闪 -> REDRAFT 弹出 -> 竖排中文接管 -> 震颤停止。

2. `章节炸场_弹出白闪震颤`
   - 用在“问题转折”或“系统启动”。
   - 一套最多 1-2 次。

3. `全屏擦除Wipe`
   - 用在从“故事页”切换到“作战室界面”。
   - 不要每次翻页都 wipe。

### 常规入场动效

4. `内容级联入场`
   - 所有普通内容页默认使用。
   - 阅读顺序: 标题 -> 标签 -> 主图/卡片 -> 底部结论。

5. `像素显影`
   - 用在选秀板更新、球员卡切换、年份回放、指标出现。
   - 适合做数据从缓存里显影的感觉。

6. `卡片悬浮微动`
   - 用在 GM agent 面板、流程节点、选秀板行 hover。
   - 只做 1-3px 的轻上浮。

### 交互动效

7. `触摸涟漪`
   - 用在 chip、按钮、选秀板行点击。
   - 颜色用主题绿,透明度低一点。

8. `按压下沉`
   - 所有可点控件都可以加。
   - 位移 1px 即可。

## 6. PPT 页面家族建议

### Slide 1 封面

视觉:

- `EVA式数据雨故障章标题`
- `Matrix数据雨背景`
- `故障发光字标`

内容:

- `REDRAFT`
- `让模型回到选秀夜`
- 一句短主张

### Slide 2 问题页

视觉:

- `命题强调块`
- 暗色发光底

内容:

- “同一张选秀板,混合了两个问题”
- “他会在哪被选?”
- “他真正值不值得?”

### Slide 3 方法页

视觉:

- `流程路线`
- 连接线绘出

内容:

- Talent Signal
- Market Signal
- GM Agent
- Monte Carlo
- Audit

### Slide 4 作战室页

视觉:

- `玻璃控制台系统`
- `顶部状态Chip`
- 选秀板
- `点阵数字`

内容:

- 30 GM online
- 1000 simulations
- confidence board

### Slide 5 背离页

视觉:

- 左右 split
- 红/绿差异线
- `像素显影`

内容:

- Talent rank vs Market rank
- gap 被触发成 agent 推理

### Slide 6 Agent trace 页

视觉:

- pixel / mono log
- 少量 Matrix 暗纹
- 内容级联入场

内容:

- commissioner trace
- scout review
- gm fit
- red-team challenge

### Slide 7 架构页

视觉:

- `流程路线`
- 玻璃节点
- 绿色路径线

内容:

- Fargate
- Bedrock Agents
- Step Functions
- API / Result

### Slide 8 收束页

视觉:

- 回到 `REDRAFT` 故障发光字标
- 背景数据雨减弱
- 可用一次轻微白闪,不要再强震颤

内容:

- “Prediction is not a list. It is a war room.”
- 提交状态 / demo 链接 / repo

## 7. 统一 CSS 变量建议

```css
:root {
  --bg: #000402;
  --bg-panel: rgba(3, 16, 8, .78);
  --text: #f4fff8;
  --muted: #8caf9b;
  --green: #37ff8b;
  --green-hot: #00ff66;
  --amber: #f1c96b;
  --cyan-shift: #62f2ff;
  --red-shift: #ff4473;
  --line: rgba(55, 255, 139, .22);
  --display-font: "DeyiHei", "得意黑", "SmileySans-Oblique", "PingFang SC", sans-serif;
  --pixel-font: "OCR-A BT", "OCR-B 10 BT", ui-monospace, Menlo, Monaco, monospace;
  --body-font: Inter, "SF Pro Display", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}
```

## 8. 使用纪律

- 强接管页只给封面和大章节。
- 内容页必须回到可读性,不要每页都震颤、白闪、数据雨满屏。
- 每页只有一个主版式。
- 绿色只表示状态和路径,不要当墙纸。
- Pixel 字体只用于状态、编号、日志、数字和短字标; 已归档字体为 `FusionPixel12`。
- 正文不要低透明,保证评委远看也能读。
- 所有动效必须能关掉或降级。

## 9. 目前先选定的 design 点清单

- [x] 绿黑 Matrix 数据雨背景
- [x] REDRAFT 故障发光字标
- [x] EVA 式白闪弹出 + 竖排巨大中文
- [x] 得意黑作为 Display 字体
- [x] `FusionPixel12` 像素字体作为状态/短字标字体
- [x] 系统黑体作为正文
- [x] 玻璃控制台面板
- [x] 顶部状态 chip
- [x] 点阵数字 / confidence 数字
- [x] 流程路线
- [x] 内容级联入场
- [x] 像素显影
- [x] 全屏 wipe
- [x] 触摸涟漪 + 按压下沉

## 10. 待确认

- 最终是否把 `FusionPixel12` 继续只用于封面竖排短字标,还是扩展到状态 chip / 编号 / 日志。
- 最终 PPT 是单文件 HTML、Reveal.js,还是继续改当前 `index.html`。
- 竖排中文使用简体还是繁体风格。
