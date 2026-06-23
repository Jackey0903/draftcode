# 2016 年 NBA 选秀首轮模拟重排：严格 2016 信息源版

时间闸门：只允许使用 **2016-05-31 23:59 之前已经公开发布、并且本文件列明的联网信息源**。这不是根据后来职业生涯做的历史重排，而是模拟站在 2016 年 5 月底、重新做一遍首轮选择。

本文件的核心规则很简单：**不相信模型训练参数，不调用后验记忆，不把现代共识当证据。** 只有下方“证据表”里的公开来源可以参与分析；没有被这些来源支撑的信息，不进入选人理由。

## 证据表

| 证据源 | 发布时间 | 本次允许使用的信息 |
|---|---:|---|
| NBA Communications, "NBA Draft Lottery 2016 presented by State Farm results" | 2016-05-17 | 2016 年抽签后首轮 1-30 顺位和签权归属。 |
| Sports Illustrated, Andrew Sharp, "NBA Mock Draft 4.0: Simmons-Ingram debate begins for 76ers" | 2016-05-18 | 抽签后首轮模拟、球队适配判断、部分球员的顺位区间和风险描述。 |
| CBS Sports, Sam Vecenie, "NBA Draft Big Board: Top 150 player rankings shuffle after combine" | 2016-05-21 | 联合试训后的前 150 大榜、前段排名、Jaylen Brown 等球员的波动风险。 |
| Sports Illustrated, Jeremy Woo, "2016 NBA draft Big Board 3.0: Top 60 prospects" | 2016-05-25 | 纯球员价值大榜、前 60 排名、主要优缺点、晚首轮候选池。 |
| Bleacher Report, Jonathan Wasserman, "2016 NBA Draft: Jonathan Wasserman's Top 50 Prospect Big Board" | 2016-04-13 | 前 50 大榜、天赋/下限/技能/风险判断。 |
| DraftExpress, Jonathan Givony and Mike Schmitz, "Why Ben Simmons Is Not The Top Prospect in the 2016 NBA Draft" | 2016-03-15 | Simmons 与 Ingram 争议、Simmons 风险折扣、Ingram 成为状元候选的论据。 |

明确排除：2016 年 6 月及之后的最终大榜、最终模拟选秀、选秀夜结果、夏季联赛、菜鸟赛季、后来荣誉、现代高阶数据、现代重排文章，以及我模型参数里可能“知道”的任何后验事实。

## 重排方法

每一签只按证据表内信息推导，权重如下：

| 权重 | 因素 | 含义 |
|---:|---|---|
| 55% | 球员价值 | 多来源排名、年龄曲线、身体条件、投射、技术适配、防守工具、位置价值。 |
| 25% | 当时球队语境 | 只采用证据源里能看到的球队需求、签位逻辑、可容忍风险。 |
| 20% | 风险控制 | 伤病、投篮转换、角色不确定性、运动能力/对抗问题、海外留队或培养周期。 |

## 首轮模拟结果

| 签位 | 2016-05-17 签权球队 | 模拟选择 | 证据化理由 |
|---:|---|---|---|
| 1 | Philadelphia 76ers | Brandon Ingram, F, Duke | DraftExpress 在 3 月已经把 Simmons 的状元稳定性打上问号；SI 5 月 25 日大榜把 Ingram 放到第 1。证据源显示 Ingram 的投射、尺寸、年龄曲线和适配难度更干净，所以状元给 Ingram。 |
| 2 | Los Angeles Lakers | Ben Simmons, F, LSU | Simmons 仍是证据表里公认的最高天赋层球员之一。即使 DraftExpress 下调了他的确定性，SI、CBS、B/R 都仍把他放在最顶端区间，第二顺位不能再往下掉。 |
| 3 | Boston Celtics, from Brooklyn | Jamal Murray, G, Kentucky | SI Mock 4.0 在第 3 顺位就把 Murray 给到 Boston；SI Big Board 3.0 也把他排第 4，并强调投射、年轻和后场双能性。 |
| 4 | Phoenix Suns | Dragan Bender, F/C, Maccabi Tel Aviv | CBS、B/R 和 SI 都把 Bender 放在前 3-4 档。他的 7 尺身材、投射、传球和移动能力在证据源中被视为现代前场高上限模板。 |
| 5 | Minnesota Timberwolves | Jaylen Brown, G/F, California | CBS 将 Brown 排第 5，SI Big Board 把他列第 8，并承认其运动能力与上限。由于 5 顺位仍处在高上限区间，这里接受他的技能波动风险。 |
| 6 | New Orleans Pelicans | Buddy Hield, G, Oklahoma | SI Mock 4.0 明确写到 New Orleans 需要投射；B/R 把 Hield 排第 4，SI Big Board 排第 7。按 2016 信息源，他是最清晰的即战投手。 |
| 7 | Denver Nuggets, from New York | Marquese Chriss, F, Washington | SI Big Board 将 Chriss 排第 10，SI Mock 4.0 也提示他可能在 6 月前继续上升。Denver 有多个首轮签，适合押一个高波动高上限前场。 |
| 8 | Sacramento Kings | Kris Dunn, G, Providence | CBS 把 Dunn 排第 4，SI Big Board 排第 6，B/R 排第 5。证据源一致认为他是本届最好的控卫候选之一，防守和持球能立刻进入高顺位讨论。 |
| 9 | Toronto Raptors, from Denver via New York | Domantas Sabonis, F/C, Gonzaga | CBS 将 Sabonis 排第 11，B/R 排第 9，SI Mock 4.0 认为他会比实际预期更低但能帮助好球队。这里取他的篮板、手感和稳定性。 |
| 10 | Milwaukee Bucks | Jakob Poeltl, C, Utah | SI Mock 4.0 明确把 Poeltl 与 Milwaukee 的中锋需求联系起来；SI Big Board 排第 9，认为他是最成熟的真中锋。 |
| 11 | Orlando Magic | Timothe Luwawu, G/F, Mega Leks | SI Big Board 把 Luwawu 排第 11，CBS 排第 14。作为 6 尺 7 的国际侧翼，他的尺寸、防守和投射框架在这个位置成立。 |
| 12 | Utah Jazz | Denzel Valentine, G/F, Michigan State | CBS 把 Valentine 排第 10，SI Mock 4.0 把他放第 12。证据源强调他的成熟、投射、传球和即战力，因此适合这一档。 |
| 13 | Phoenix Suns, from Washington | Henry Ellenson, F/C, Marquette | SI Big Board 把 Ellenson 排第 5，CBS 排第 9。虽然防守横移是风险，但他在证据源中有尺寸、持球和投射触感。 |
| 14 | Chicago Bulls | Deyonta Davis, F/C, Michigan State | CBS 排第 12，SI Big Board 排第 12，B/R 对他的篮板、盖帽和机动性给出首轮价值判断。第 14 顺位选择防守型年轻前场。 |
| 15 | Denver Nuggets, from Houston | Furkan Korkmaz, G, Anadolu Efes | CBS 排第 19，SI Mock 4.0 将他放在 Denver 的第 19 顺位并提到留欧培养逻辑。Denver 多签位情况下可接受海外投射后卫。 |
| 16 | Boston Celtics, from Dallas | Skal Labissiere, F/C, Kentucky | CBS 排第 13，B/R 排第 20，SI Mock 4.0 仍把他放进前 10 区间讨论。风险很大，但 Boston 多签位，适合保留一次天赋押注。 |
| 17 | Memphis Grizzlies | Wade Baldwin IV, G, Vanderbilt | CBS 排第 17，SI Mock 4.0 把他作为 20 顺位附近的长臂后卫候选。第 17 顺位选防守、尺寸和后场深度。 |
| 18 | Detroit Pistons | Taurean Prince, F, Baylor | CBS 排第 22，SI Mock 4.0 把 Prince 放第 16。证据源将他视作更成熟的锋线角色球员，适合中后段首轮。 |
| 19 | Denver Nuggets, from Portland | Dejounte Murray, G, Washington | SI Mock 4.0 将 Dejounte Murray 放到第 26，并强调他的尺寸和突破；CBS/SI 后段名单也支持他作为首轮边缘上限选择。 |
| 20 | Indiana Pacers | Demetrius Jackson, G, Notre Dame | CBS 排第 18，SI Mock 4.0 把他放第 15。证据源支持他作为速度、力量和后场轮换价值兼具的首轮球员。 |
| 21 | Atlanta Hawks | Damian Jones, C, Vanderbilt | SI Mock 4.0 把 Jones 放第 21，并把他与 Atlanta 前场不确定性联系起来。按这份信息源，他是 20 顺位附近的工具型中锋选择。 |
| 22 | Charlotte Hornets | Malik Beasley, G, Florida State | B/R 把 Beasley 排第 13，CBS 排第 20，SI Mock 4.0 把他放第 22。证据源支持他的年轻、得分和投射潜力。 |
| 23 | Boston Celtics | Ante Zizic, C, Cibona Zagreb | SI Big Board 排第 22，CBS 排第 23，SI Mock 4.0 把他放给 Boston 并说明可作为海外内线储备。 |
| 24 | Philadelphia 76ers, from Miami via Cleveland | DeAndre Bembry, G/F, Saint Joseph's | SI Big Board 排第 26，CBS 排第 21，SI Mock 4.0 把他放第 24。证据源强调他的全面性、球场感知和侧翼连接能力。 |
| 25 | Los Angeles Clippers | Brice Johnson, F, North Carolina | SI Mock 4.0 把 Johnson 放第 25，SI Big Board 后段也把他列为首轮边缘。对争胜球队来说，他的大学产量和前场活力更容易兑现。 |
| 26 | Philadelphia 76ers, from Oklahoma City via Denver and Cleveland | Juan Hernangomez, F, Estudiantes | SI Big Board 排第 27，SI Mock 4.0 也排第 27。作为年轻欧洲前锋，他提供投射、活力和延后加入球队的灵活性。 |
| 27 | Toronto Raptors | Cheick Diallo, F/C, Kansas | SI Mock 4.0 把 Diallo 放第 28，并提到联合试训后的身体工具价值。这里按证据源把他作为晚首轮防守内线项目。 |
| 28 | Phoenix Suns, from Cleveland via Boston | Ivica Zubac, C, Mega Leks | SI Big Board 排第 29，CBS 排第 25。证据源支持他的体型、内线手感、青年国际赛产量和可储备价值。 |
| 29 | San Antonio Spurs | Malcolm Brogdon, G, Virginia | CBS 排第 27，SI Big Board 排第 34，SI Mock 4.0 在第 29 顺位直接把他描述成聪明球队会偷到的成熟 3D 后卫。 |
| 30 | Golden State Warriors | Caris LeVert, G/F, Michigan | SI Big Board 排第 32，SI Mock 4.0 把他放第 30，并明确指出伤病折扣。Golden State 在第 30 顺位可以承受医疗风险，换取持球、传球和投射感。 |

## 首轮边缘池

以下球员在证据源中进入过首轮或首轮边缘讨论，但本次没有进入前 30：

Thon Maker、Tyler Ulis、A.J. Hammons、Patrick McCaw、Stephen Zimmerman、Pascal Siakam、Chinanu Onuaku、Zhou Qi、Malachi Richardson、Ben Bentil、Gary Payton II。

特别说明：Pascal Siakam 没有被现代结果抬进乐透。本次只允许使用 2016 年 6 月前证据源；这些来源最多支持他进入晚首轮讨论，不能支持事后式大幅上调。

## 来源链接

- NBA Communications, 2016-05-17: https://pr.nba.com/nba-draft-lottery-2016-presented-state-farm-results/
- Sports Illustrated Mock 4.0, 2016-05-18: https://www.si.com/nba/2016/05/18/nba-mock-draft-76ers-lakers-ben-simmons-brandon-ingram
- CBS Sports Big Board, 2016-05-21: https://www.cbssports.com/nba/news/nba-draft-big-board-top-150-player-rankings-shuffle-after-combine/
- Sports Illustrated Big Board 3.0, 2016-05-25: https://www.si.com/nba/2016/05/25/nba-draft-big-board-mock-draft-76ers-lakers-ben-simmons-brandon-ingram
- Bleacher Report Big Board, 2016-04-13: https://bleacherreport.com/articles/2626665-2016-nba-draft-jonathan-wassermans-top-50-prospect-big-board
- DraftExpress Simmons/Ingram 分析, 2016-03-15: https://www.draftexpress.com/article/Why-Ben-Simmons-Is-Not-The-Top-Prospect-in-the-2016-NBA-Draft-5390/

## 审计结论

- 首轮结果正好 30 个签位。
- 签位顺序和签权归属来自 NBA 官方 2016-05-17 信息源。
- 所有可用证据源发布时间均早于 2016-06-01。
- 本文件不以模型训练参数、后验记忆、现代排名、职业生涯表现或 2016 年 6 月后资料作为证据。
