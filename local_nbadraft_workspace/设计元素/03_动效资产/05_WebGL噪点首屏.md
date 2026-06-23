# WebGL 噪点首屏

## 适合

高级展示页首屏、产品发布页、需要“活的材质场”的开场。

## 效果

全屏半透明噪点云/能量场缓慢流动,鼠标轻微扰动,让背景像有呼吸。

## 实现抓手

- canvas WebGL。
- fragment shader 使用 hash/noise/fBm。
- 2-3 个品牌色或主题色混合。
- 鼠标坐标作为 displacement。
- DPR 限制到 `Math.min(devicePixelRatio, 2)`。
- 离开视口停止绘制或跳过 render。

## 禁忌

- 不要覆盖正文可读性。
- 不要在低端设备无降级。
- 不要和大量粒子、视频、Three 场景同时抢 GPU。

## 降级

静态径向渐变 + 轻噪点 SVG 纹理。
