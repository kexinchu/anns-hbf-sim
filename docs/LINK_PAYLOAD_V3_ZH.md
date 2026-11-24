# 链路有效载荷模型 v3：证据、假设与验收边界

v3 是可选的聚合有效载荷模型；默认仍为 `service-v2`。配置键是
`execution.ucie.accounting=payload-v3`。不修改 v2 协议、历史数据或其解释。
它不是逐 flit 的 OCP/UCIe 实现，也不构成硬件校准通过。

## 为什么另立模型

[OCP HBF v0.7 §5.1.2.2](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/)
给出 SG2 单模块原始 128 GB/s、系统 94 GB/s。Table 2 的效率含 AXI；
若把已经折算后的有效带宽当作服务字节预算，再向每个 64B 有效载荷加 16B，
就可能再次扣除同类开销。规范没有支持“每个响应恰好另耗 16B”的依据。
旧 v2 的 16B 是服务等价量，不能改称真实包头。
正文的 system bandwidth 是否对所有请求尺寸、读写组合都等同于应用有效载荷带宽，
规范摘录没有充分界定。因此 v3 是有来源支持的另一种聚合解释，不是已被证明唯一正确的线级模型。

| 项目 | service-v2（保留） | payload-v3（新增） | 证据等级 |
|---|---|---|---|
| 非空数据传输 | ceil((payload+control)×1000/B_eff) ps | ceil(payload×1000/B_eff) ps | v3 是有效带宽抽象的实现选择 |
| 无数据控制传输 | ceil(control×1000/B_eff) ps | ceil(control×1000/B_raw) ps | 控制量 16B 是假设，不是规范包格式 |
| SG2 B_eff / B_raw | 94 / 128 GB/s | 94 / 128 GB/s | OCP §5.1.2.2 |
| 固定方向延迟 | 100ps | 100ps | 未校准假设 |
| 通道/方向资源 | 各通道各方向单一共享服务队列 | 相同 | 聚合模型假设；不是完整 PHY 仲裁 |

因此 SG2 64B 响应从 852ps 改为 681ps；16B 控制请求从 171ps 改为 125ps。
改变响应控制配置 16→32B 不应改变 v3 非空数据响应的服务时间；v2 仍改变。
该不变量由实际 DeviceDriver 的请求/响应事件测试，而不只验证公式函数。

Table 4 的 1.536TB/s 除以 16 隐含 96GB/s，与正文 94GB/s 尚未统一。
v3 不为了命中 1.536TB/s 而改用 96 或拟合额外常数。
整数 ps 下本模型 16 通道 64B 响应的理想服务上限为
16×64×1000/681≈1503.67GB/s；这是模型解析上限，不是实测。
控制包占用、重试流量和混合读写的实际效率仍需外部证据。

## 页面周转与独立验证

冻结协议：`calibration/turnover-v3/protocol.json` 及 SHA256。
12MiB / 24MiB 初始化工作集，在 1024 个 bank 上分别覆盖 3 / 6 页，
均超过每 bank 两个缓冲槽；总缓冲容量 8MiB。
连续执行四轮，轮次之间不清缓存、不排空队列。初始写入不纳入读计时。
独立访问 QD128；依赖访问 QD1；MOCS4096；4KiB 通道条带、FIFO。
顺序 256B 会读全页；随机 256B 每页只取一个父请求，二者有效页面利用率不能混同。

独立 Python 两槽 FIFO 参考机仅保存页号队列，不导入模拟器缓存代码。
在单 bank 的定向命中序列和固定种子随机序列上比较每次 sense 的页号、
身份、配对时刻及依赖提交关系；包括区分 FIFO/LRU 的重复命中序列。
这证明所声明 FIFO 行为的一致性，不证明真实设备采用 FIFO。
负向测试改变完成页号、身份、时间，以及非法 QD/模式/地址。

长轨迹审计检查所有请求、closed-loop 提交关系、每 bank sense 不重叠、
每次 sense 时长及所有 bank 实际跨页周转。稳态与长度检查采用冻结的 5% 门槛；
不满足时保留非稳态标记，不能把命令正确完成当作稳态成立。

## 与论文对齐及拟合隔离

[HEAVEN/RETRIEVE 论文](https://research.ece.cornell.edu/retrieve/camera-ready/retrieve26-final50.pdf)
Table II 的 16×4×16、4KiB、双缓冲和 2.72us 名义 sense 参数用于结构对照。
2.72us 本身是论文拟合参数，不能拿同一个饱和点当独立验证。
本轮未拟合任何参数；固定种子验证轨迹与所有失败观察均保存。
论文的精确地址序列、到达协议和测量窗口尚缺，不能宣称完整曲线复现。
本轮 QD128 长工作集用于周转与稳定性诊断，不替代 v2 的完整 QD 扫描，
也不能当作 v3 饱和带宽或 ANNS 性能结论。

校准门保持关闭：`hardware_calibrated=false`、`paper_curve_reproduced=false`、
`performance_ready=false`。A6000/GDDR6 不提供 HBM/HBF 时序真实性证据。

## 已完成的长轨迹观察

12MiB 顺序流中，v3 的后三窗口有效吞吐分别为 256B **12.03357GB/s**、
4KiB **189.69076GB/s**；相应 v2 为 **12.03034**、**188.93949GB/s**。
日志的最大同时 sense bank 数分别是 **8** 和 **128**。
父请求 QD128 对连续 256B 地址只覆盖 8 个 4KiB 页，不能等同于 128 个独立页，
更不能等同于全部 1024 bank 饱和。名义 sense 带宽量级
8×4096/2.72us≈12.047GB/s、128×4096/2.72us≈192.753GB/s
与这些观察相容；这是内部量纲/并发检查，不是独立硬件验证。

v2/v3 的随机 256B、随机 4KiB 共四条轨迹都没有满足冻结的 5% 稳态判据。
保留所有窗口，不挑选平稳片段，也不据此拟合 sense 或修改门槛。
24MiB 原批次触发宿主累计分片保护上限而失败，原始错误和部分输出保留；
`input-limit-amendment.json` 单独声明上限从 1048576 改为 2097152。
这只放宽累计输入数量保护，不更改 QD/MOCS 或设备资源；小轨迹两版完整事件摘要一致。


## 复现与测试

- `cmake -S . -B build -DANNS_FCFS_INDEX=CHECK -DANNS_DEVICE_INDEX=CHECK`，构建后 `ctest --test-dir build --output-on-failure`。
- `python3 tests/turnover_v3.py build/turnover_probe <new-output-dir>` 跑冻结 12 点；当前 probe 已显式提高累计输入保护上限。
- 本次原批次的输入限制失败保存在 `calibration/turnover-v3/20261124/results/`；仅两项重试位于 `retry-input-limit/`。
- `python3 scripts/audit_turnover_v3.py calibration/turnover-v3/20261124` 从输入和原始事件重算本次摘要，不调用模拟器。
- `python3 scripts/plot_turnover_v3.py calibration/turnover-v3/20261124` 生成全部窗口曲线。

41 项根项目 CHECK 测试、500 项上游回归通过。四组 v2 回归的请求输出与事件摘要
和已发布二进制逐字节一致。新增读链路 12 组/1536 命令与 3 个负向控制、
写/ACK 12 组与 24 个计时破坏、控制溢出/非法模式/配置往返，以及 FIFO 逐次差分。
这些证据证明实现满足声明的模型；它们不把声明的时序假设升级为外部实测。

Linux 上对完整 EventLab 库及读/写/周转探针启用 ASan+UBSan，四项检查通过。
本地 Apple 工具链因 libc++ 的 sanitizer annotation 符号缺失无法链接，该次不计作通过；
Linux 检查提供独立的平台验证。离线长轨迹审计另拒绝六种损坏（提交时刻、请求身份、
sense 时刻、字节数、sense 总数、丢请求）。

最终归档包含 **12 个有效用例、2 个保留的初次失败**：8/12 满足冻结稳态判据，
4/12 随机曲线不满足。24MiB 的 256B / 4KiB 顺序流后三窗口分别仍为
12.03356972 / 189.69076044 GB/s，与 12MiB 对应值相同，两个工作集翻倍检查通过。
这只覆盖所冻结的四轮连续流和窗口，不证明任意工作负载长期平稳。
所有有效轨迹经本地离线审计重验；原始输入、事件、退出状态、二进制哈希与 SHA256 清单
位于 `calibration/turnover-v3/20261124/`，完整窗口图为 `window-curves.png`。
