# Matrix 数据雨背景

## 适合

黑客松开场、数据重放、历史回测、系统启动、赛博控制台背景。尤其适合表达“模型回到过去的数据现场”或“信息流正在被系统读取”。

## 效果

深黑底上多列绿色字符自上而下流动,像瀑布一样不断刷新。字符可以混合数字、字母、顺位、球队缩写和少量中文关键词,让它从普通 Matrix 致敬变成项目自己的数据雨。

## 实现抓手

```js
const chars = "01DRAFTGMLOCKSIM市场天赋顺位";
const colWidth = 18;
const drops = Array.from({ length: Math.ceil(width / colWidth) }, () => Math.random() * -height);

function drawMatrixRain(ctx, width, height) {
  ctx.fillStyle = "rgba(0, 4, 2, .16)";
  ctx.fillRect(0, 0, width, height);
  ctx.font = "15px ui-monospace, Menlo, monospace";

  for (let i = 0; i < drops.length; i++) {
    const x = i * colWidth;
    const y = drops[i];
    const hot = Math.random() > .985;
    ctx.fillStyle = hot ? "#effff5" : "rgba(0, 255, 102, .72)";
    ctx.fillText(chars[Math.floor(Math.random() * chars.length)], x, y);
    drops[i] += 18 + Math.random() * 7;
    if (drops[i] > height + 40 && Math.random() > .975) drops[i] = Math.random() * -160;
  }
}
```

## 使用方式

- 放在封面或章节页背景,不要每一页都铺满。
- 字符密度要留出正文阅读区,核心内容背后降低透明度。
- 字符集要项目化: 例如 `DRAFT / GM / LOCK / SIM / 顺位 / 天赋 / 市场`。
- 画面中央可以暗一点,四周字符更明显,避免抢标题。
- 低端设备可降级为静态绿色字符纹理或极低帧率 canvas。

## 可搭配

- `故障发光字标`
- `WebGL噪点首屏`
- `全屏擦除Wipe`
- `像素显影`
- `章节冲击页`

## 禁忌

- 不要写“入侵”“破解”等与项目无关的假黑客语义。
- 不要让字符雨覆盖正文可读性。
- 不要颜色太亮到满屏泛绿。
- 不要和大量粒子、视频、Three 场景同时抢 GPU。

## 验收

第一眼能感到“数据瀑布流”,但第二眼仍然读得清主标题和关键信息。关掉动画后页面仍要成立。
