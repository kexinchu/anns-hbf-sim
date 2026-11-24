# QD1024 大窗口执行超时修复与曲线对齐边界

## 根因与修复

固定 1024 个 4KiB 冷请求、QD1024、每通道 MOCS4096，原版最终正常完成，但本次执行耗时 439.276 秒，超过旧诊断 300 秒预算。DeviceDriver 的已插桩 self time 为约 435 秒；不是模拟设备死锁，也不是模拟时间达到 deadline。

原推进路径在每个事件上多次扫描整通道事务 ID 集，再到全局 map 查找事务。大窗口显著放大这项程序开销。新增的有序阶段目录保存指向原事务的非拥有指针：

- Ingress、Accepted、Egress 按原 attempt ID 顺序访问；没有改变准入顺序、候选排序、事件 phase、计时或信用归还时刻。
- 所有原有 live eligibility、等待、终端错误、cache pin 和物理映射检查保留。没有把等待请求当成可永久跳过的请求。
- 阶段迁移同步更新目录，反馈清理时移除指针，事务仍由原 `std::map` 拥有。
- `prior_sense` 使用 Accepted 目录；Ready probe 已返回的物理地址只在同一调用内复用，Blocked 仍走原来的 inspect。不缓存跨事件的映射或就绪状态。
- `ANNS_DEVICE_INDEX=OFF` 保留原扫描实现；`CHECK` 对照原事务集合逐项检查阶段目录，并逐次比较原 `prior_sense` 谓词。在资源排空检查时也核验全部六个阶段，避免漏掉反馈目录残留。

## 保持了什么

原版与最终优化版同一输入均退出 0：

| 项目 | 原版 | 优化版 |
|---|---:|---:|
| 程序墙钟秒，本次带 profile 观测 | 439.276 | 213.545 |
| 模拟完成时间 ps | 6,210,163 | 6,210,163 |
| 完成逻辑请求 / sense 次数 | 1024 / 1024 | 1024 / 1024 |
| 设备事件数 | 526,336 | 526,336 |
| 活跃 bank 峰值 | 1024 | 1024 |

全部 1024 条请求提交/完成记录及汇总逐字相同；所有 DeviceTrace 字段按原事件顺序计算的 FNV-1a 64-bit 指纹亦相同。指纹是回归检测手段，不是形式化证明；该结论同时由原谓词在线差分、独立机制参考和恢复测试支撑。

这些墙钟值来自一次开发环境运行，包含调度/其他构建负载，不能当成稳健的加速比估计。这里只证明最终版本在原 300 秒预算内完成；**HBF 模拟吞吐与时延没有因程序优化变化**。

## 验证与反例

- ON 与 CHECK 路径各 36 项完整项目回归全部通过；最终源码的上游 500 项回归全部通过。
- 独立原扫描二进制对照冷/热、大窗口、依赖链和小窗口请求，逐字比较结果与事件指纹。
- CHECK 使用未优化扫描构造目录参考，而不是由目录反推期待值。
- 三个生产实现变异必须被拒绝：跳过 Ingress 索引迁移、遗留 Feedback 指针、忽略先前 sense 约束。编译失败不算拒绝成功。
- Linux 整个 EventLab 库与探针启用 ASan/UBSan，并开启阶段 oracle：缓存参考 524 阶段及定向检查；完整 Driver reset 36 个调度和 2 个负向变异；外部旧包/重放 18 个读写调度和 4 个负向变异。

原始输出、profile、退出状态和差分结果在 `calibration/large-window-fix/20261124/`。`subprofile.json` 是仅设备侧临时插桩：split=admit、prepare=try_cache、register_input=prior_sense、admit_input=execute_media、reclaim=queue_responses、pump=start_response。仅用于定位程序热点；其额外时钟读取有开销，不能与主 profile 相加或当成硬件时延。

## 冻结协议后，哪些对齐仍然不成立

新协议：[protocol-v2.json](../calibration/paper-curves/protocol-v2.json)，附 SHA256；修改协议必须显式更新版本/冻结记录。固定 MOCS4096 为主配置、256 为资源对照；固定 closed-loop 补充到达、QD 网格、有限批次起止、64B 拆分、缓存和链路参数。没有修改旧协议及历史原始数据。

旧探针的 256B “sequential” 每次跨 4KiB 页。新探针显式支持 byte-addresses，真正连续访问为 `i*256`，跨页访问为 `i*4096`。独立测试分别要求 64 和 1024 次 sense，即 100% 和 6.25% 页效率。这个区分是曲线口径修正，不是缓存策略带来的收益。

[检索论文](https://research.ece.cornell.edu/retrieve/camera-ready/retrieve26-final50.pdf) 的 Table II 提供拓扑和 nominal sense；Fig.3(b) 给六类吞吐/页效率结果，**不是公开的 QD 全曲线**。论文正文未给对应命令窗口、确切到达/QD、样本数/footprint、冷/热准备和原始数值数据，当前不能宣称与其完整工况逐项相同。没有找到可核验的配套原始 trace/code；搜索未找到不等于证明不存在。

另一个必须显式保留的差异：当前链路是 16×94=1504 GB/s 的 service-byte 预算，每个 64B 返回额外记 16B control。仅由当前模型配置推导，持续有用载荷上限为 1504×64/80=1203.2 GB/s；这是模型上界，不是硬件实测，也不是论文 1536 GB/s user bandwidth 的同一口径。不能暗改 overhead/sense 来拟合图线。有限 4MiB 冷批次还包含启动与排空，不能当作满利用稳态。

因此：超时和地址序列口径已处理；论文完整曲线精确对齐、链路 user/service-byte 口径以及硬件校准仍未关闭。没有将这些有限批次诊断作为拟合数据再充当独立验证。`performance_ready=false`、`hardware_calibrated=false`、`paper_curve_reproduced=false`，ANNS 性能实验继续关闭。

后续链路计费核对与冻结v2完整网格见 [LINK_BANDWIDTH_AUDIT_ZH.md](LINK_BANDWIDTH_AUDIT_ZH.md)。旧报告与数据保持原口径；没有以新曲线替换历史失败记录。
