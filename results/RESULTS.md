# 🏀 DraftCode 最终预测结果 · Final Results

> **2026 NBA 选秀** · AWS Summit Shanghai 2026「模拟球探」黑客松  
> 生成自**三信号融合管线**(天赋 · 专家 · 资金)。持签球队 = 官方 draftboard + 已确认交易;球员池 = 官方 **107** 参选人;蒙特卡洛 **1500** 次。

## 一、30 顺位预测

| # | 持签球队 | 预测球员 | 置信度 |
|--:|--|--|--:|
| 1 | Washington Wizards | AJ 迪班萨 | 75% |
| 2 | Utah Jazz | 达林 彼得森 | 54% |
| 3 | Memphis Grizzlies | 卡梅隆 布泽尔 | 51% |
| 4 | Chicago Bulls | 凯莱布 威尔逊 | 51% |
| 5 | Los Angeles Clippers | 基顿 瓦格勒 | 40% |
| 6 | Brooklyn Nets | 达柳斯 阿卡夫 | 27% |
| 7 | Sacramento Kings | 纳撒尼尔 阿门特 | 23% |
| 8 | Atlanta Hawks | 亚克塞尔 伦德伯格 | 18% |
| 9 | Dallas Mavericks | 金斯顿 弗莱明斯 | 18% |
| 10 | Milwaukee Bucks | 小拉巴伦 菲隆 | 19% |
| 11 | Golden State Warriors | 阿达伊 马拉 | 27% |
| 12 | Oklahoma City Thunder | 小莫雷兹 约翰逊 | 22% |
| 13 | Milwaukee Bucks ⟵ 字母哥交易 | 以赛亚 埃文斯 | 17% |
| 14 | Charlotte Hornets | 卡梅隆 卡尔 | 18% |
| 15 | Chicago Bulls | 杰登 昆坦斯 | 19% |
| 16 | Memphis Grizzlies | 汉内斯 施泰因巴赫 | 7% |
| 17 | Oklahoma City Thunder | 克里斯蒂安 安德森 | 10% |
| 18 | Charlotte Hornets | 马利克 托马斯 | 11% |
| 19 | Toronto Raptors | 埃布卡 奥科里 | 25% |
| 20 | San Antonio Spurs | 戴林 斯温 | 20% |
| 21 | Detroit Pistons | 克里斯 塞纳克 | 16% |
| 22 | Philadelphia 76ers | 泰勒 比洛多 | 14% |
| 23 | Atlanta Hawks | 科阿 皮特 | 20% |
| 24 | New York Knicks | 本内特 斯特茨 | 11% |
| 25 | Los Angeles Lakers | 亚历克斯 卡拉班 | 11% |
| 26 | Denver Nuggets | 马利奇 布朗 | 9% |
| 27 | Boston Celtics | 亨利 维萨尔 | 18% |
| 28 | Minnesota Timberwolves | 莱恩 康韦尔 | 20% |
| 29 | Cleveland Cavaliers | 祖比 埃吉奥福尔 | 12% |
| 30 | Dallas Mavericks | 布雷登 伯里斯 | 26% |

*置信度 = 1500 次蒙特卡洛中该球员落在该顺位的边际概率;顶部 1-4 顺位锚定去水赔率(资金信号)。*

## 二、7 道里程碑(与上面这张板自洽)

| 题号 | 问题 | 答案 |
|--|--|--|
| Q1 | 第 4–14 顺位中长臂展(臂展−赤脚身高≥5吋)球员数 | **3 人** |
| Q2 | 训练营助跑弹跳前 3 中进首轮人数 | **2 人** |
| Q3 | 首轮 30 人中中锋总数 | **2 个** |
| Q4 | 第 4–30 顺位首个中锋落点 | **11 顺位** |
| Q5 | 首轮国际球员总数 | **3 人** |
| Q6 | 贡献首轮球员最多的机构 | **密歇根大学** |
| Q7 | 训练营手掌长度前 5 中进首轮人数 | **2 人** |

## 三、关键说明

- **持签球队**对齐官方 30 队名单拼写;**字母哥交易经 web 核实为官方**(NBA.com / ESPN,密尔沃基获第 13 签)→ pick 13 = Milwaukee Bucks。
- **里程碑与最终板自洽**(如 Q4=11 = 板上首个中锋阿达伊·马拉的真实落点,非分布期望值)。
- **三信号融合**:天赋(手册)+ 专家(CBS/SI mock 共识)+ 资金(ESPN/OddsShark 赔率 de-vig 隐含概率);背离处由 gpt-5.5 裁决。
- **球员池 = 官方 107 参选人**,不预测不可能被选的人。

## 四、复现

```bash
draftcode ingest --divergence-llm  →  intel --apply  →  market --apply  →  odds --apply
  →  warroom  →  simulate  →  answer  →  audit
```
提交用答题卡:[`results/answer_card.xlsx`](answer_card.xlsx) · 可审计证据档:`outputs/audit.md`

