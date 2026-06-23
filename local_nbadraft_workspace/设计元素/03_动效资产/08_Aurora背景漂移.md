# Aurora 背景漂移

## 适合

深色玻璃界面、控制台、仪表盘、音乐/地图/HMI 背景。

## 效果

多个大尺寸 radial-gradient blob 缓慢漂移、模糊、混合,形成有深度的背景光场。

## 实现抓手

- `.aurora` 容器覆盖背景。
- 3 个以上大圆 blob。
- `filter: blur(...) saturate(...) hue-rotate(...)`。
- 每个 blob 使用长周期 `alternate` keyframes。
- `mix-blend-mode: screen`。

## 禁忌

- 不要让 aurora 抢正文对比。
- 不要周期太快。
- 不要用太多色相,容易脏。
