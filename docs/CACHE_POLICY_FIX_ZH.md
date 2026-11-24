# 2026-11-24：缓存策略修复与冷读诊断

## 已修复的机制问题

旧实现每次 pin 命中均更新 age，因此 A/B/A/C 会淘汰 B。OCP HBF v0.7.0 §5.3.1(7) 的第三页淘汰第一页示例不能由该行为直接保证。本轮默认改为填入顺序 FIFO：命中不更新 age，A/B/A/C 淘汰 A。该解释对应规范示例，不代表规范完整规定了任意并发替换算法。

- `ExecutionConfiguration.cache_hit_recency=false` 为默认；true 显式恢复旧 LRU，以供敏感性分析。
- 配置摘要记录 `execution.cache_hit_recency`，不允许把不同策略的结果混为同一配置。
- 填充中和持有 lease 的槽仍受保护，只能从可淘汰槽中选择最老者。没有用提前释放响应引用换吞吐。
- `mechanism_probe` 拒绝未知策略名称；不传策略必须逐字等于显式 FIFO 输出。

## 独立判据

Python 参考机独立维护每个 bank 的两个页面，未调用 EventLab 的缓存代码。相同种子下 FIFO、LRU 各 262 个顺序阶段，逐阶段比较实际 sense 次数，共 524 个。A/B/A/C/A/B 区分填入顺序与命中次序。8 个定向运行另外检查媒体时间、bank 串并行和有限 Core Channel；5 种损坏记录必须被拒绝。

生产代码变异另行编译：只允许一个槽、在 FIFO 模式错误更新命中 age。两者都必须在 sense 次数差分处失败，编译错误不计作成功捕获。

本轮执行结果：项目 CTest 35/35、上游 CTest 500/500 通过；Linux 对整个 EventLab 库和探针启用 ASan/UBSan 后，524 阶段及定向/负向检查通过，无 sanitizer 报错。CI 也加入了这条全库 sanitizer 机制差分路径。

原始证据：`calibration/mechanism-acceptance/20261124/`。历史日期目录保留旧策略结果。通过这些检查只支持已覆盖机制，不证明外部时序、所有并发交错或 OCP 全符合。

## 尚未关闭的门槛

冷 4 KiB 曲线与论文的满利用条件尚未对齐。命令窗口、64 B 拆分、bank 供给和有限批次边界必须分别诊断；禁止改 sense 延迟使单点接近论文。FIFO 修复也不自动解释该平台：原冻结 footprint 每个 bank 只访问一个页面，没有产生替换冲突。

`performance_ready=false`、`hardware_calibrated=false`、`paper_curve_reproduced=false`。未恢复 ANNS 性能实验。
