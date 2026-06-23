# EVA 式数据雨故障章标题

## 适合

黑客松路演开场、重大章节切换、系统启动、历史数据回放、需要“屏幕被接管”的强记忆点页面。

## 效果

把 `Matrix数据雨背景` 的信息流、`故障发光字标` 的绿光错位、EVA 章标题的超大字弹出/白闪/震颤组合起来。画面像系统从数据瀑布中锁定项目名,随后用巨型竖排中文接管屏幕。

## 视觉构成

- 背景: 黑底绿色 Matrix 数据雨,字符集项目化。
- 主字标: 超大 `REDRAFT` 或项目名,白字 + 绿色发光 + 青红错位。
- EVA 结构: 右侧或角落放巨型竖排中文短句,例如 `回到選秀夜`。
- 接管瞬间: 白闪 0.4-0.5 秒 + 文字从 blur/scale/rotate 状态弹出。
- 稳定态: 抖动停止,只保留轻微发光和背景数据雨。

## 实现抓手

```css
.wordmark {
  color: #f4fff8;
  text-shadow:
    0 0 18px rgba(0, 255, 102, .62),
    0 0 58px rgba(0, 255, 102, .26),
    3px 0 rgba(255, 68, 115, .72),
    -3px 0 rgba(98, 242, 255, .5);
  animation: eva-glitch-pop .68s cubic-bezier(.18,.85,.25,1) forwards;
}

.hanzi {
  writing-mode: vertical-rl;
  text-orientation: upright;
  font-family: "Hiragino Mincho ProN", "Songti SC", "STSong", "MingLiU", serif;
  animation: eva-glitch-pop .62s cubic-bezier(.18,.85,.25,1) .28s forwards;
}

@keyframes eva-glitch-pop {
  0%   { opacity: 0; transform: scale(1.55) rotate(-1.3deg); filter: blur(16px); }
  48%  { opacity: 1; transform: scale(.9) translateX(-3px) rotate(.3deg); filter: blur(0) hue-rotate(20deg); }
  58%  { transform: scale(1.06) translateX(4px) rotate(-.2deg); }
  68%  { transform: scale(.98) translateX(-1px); }
  100% { opacity: 1; transform: scale(1) translateX(0) rotate(0); filter: blur(0); }
}
```

## 动效节奏

1. 数据雨先存在,营造系统读取感。
2. 白闪接管屏幕。
3. 主字标弹出并短促 glitch。
4. 竖排中文延迟 0.2 秒登场。
5. 全屏震颤只持续 1 秒以内,随后恢复稳定可读。

## 使用方式

- 一套演示最多使用 1-2 次,用在开场或大章节。
- 文字必须极短: 项目名 + 一句竖排命题即可。
- 绿色负责系统激活,白色负责 EVA 式强对比,青红只负责故障错位。
- 背景字符要暗,不要盖住主字。

## 可搭配

- `Matrix数据雨背景`
- `故障发光字标`
- `章节炸场_弹出白闪震颤`
- `像素显影`
- `全屏擦除Wipe`

## 禁忌

- 不要把正文页也做成这种强接管效果。
- 不要持续高频震颤。
- 不要直接使用受版权保护的标志、角色、专有图形。
- 不要把“EVA感”理解成堆红黑警示贴纸;核心是巨大字、强切换、白闪、震颤和竖排排版。

## 验收

第一眼有“屏幕被系统接管”的冲击,第二眼项目名和章节命题仍清晰可读。动画结束后画面应稳定,可以截图作为封面。
