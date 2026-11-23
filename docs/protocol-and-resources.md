# 独立协议参考机与有限资源闭环

本轮仅做正确性测试；性能实验关闭。所有固定时延/带宽均为测试参数。

## 独立性与逐命令差分

`tests/protocol_diff.py`使用Python字典实现规范子集，**不导入donor、不读取donor状态、不用donor生成预期答案**。`src/protocol_probe.cpp`仅把输入转换成后端公共API，输出每一步的接受状态、outstanding数、可交付响应及data token。独立参考输出与实际输出逐项比较，原始输入/预期/实际/错误保存在结果目录。

输入W/R为64B命令，P为显式成功介质完成，D为Host接受已就绪响应，T为显式推进至组装期限。P/D/T是测试控制动作，不伪装为OCP命令。Q复用同一AXI ID，通过适配器显式映射到read_group。底层read_group不是完整AXI层，不能因这个测试宣称已实现全部AXI-ID语义。

| 条款（OCP v0.7） | 本轮测试 | 仍未覆盖 |
|---|---|---|
| §5.3.1(1,4) | 64B访问及未对齐输入拒绝 | read burst，真实AXI逐拍 |
| §5.3.1(5) | 同ID显式组序，D后后继可完成 | 全AXI ID字段映射；有序Pending读仍不支持 |
| §5.3.1(7–8) | 两个冷页后重读第一页无需sense | 任意替换策略、缓存与故障混合轨迹 |
| §5.4.1 | 64片组装、不完整P不得成功ACK、完整P后每命令一次响应 | 精确deadline竞争、全写序错误、故障重放 |
| §5.4.3 | Pending已收片转发、缺片0xA、不回退旧介质 | 与重映射/恢复组合 |
| Table12/13 | invalid address、unwritten、overlap及成功响应 | 未宣告支持的ECC/其他状态 |
| §5.9.2 | MOCS配置契约；满256时背压、交付后恢复 | 完整寄存器及链路credit层 |

种子固定为0–15，随机改变片段顺序和读地址。每条轨迹含相同边界场景，不能把种子数当作独立覆盖条款数。负向测试故意篡改credit、status和成功返回data，检查器必须报告差异。

## 有限Core Channel

实现为构建时overlay：`scripts/prepare_eventlab.py`复制固定版本源码到构建目录，以精确唯一锚点修改；不修改vendor。新增配置可在effective INI中保存和回读：

- `execution.core_bytes_per_ns`：0为旧理想模式；正数为有限共享链路。
- `execution.core_propagation_ps`：序列化后的传播时延。
- 通道归属沿用 `(host channel, topology.core_channel(die))`。

读：sense结束后，才把4KiB页加入Core链路；链路完成后cache才可见、读才能完成。
写：完整页传输后开始program延迟；erase不携带4KiB数据。
共享同一链路的传输FIFO且半双工；不同链路独立。每个bank仅一个在途介质操作，因此等候Core传输的页数受bank数限制；没有新增无限制请求FIFO。传播阶段不占链路带宽。

**模型选择**：4KiB页搬运、半双工、bank持有至传输完成。OCP不是这些参数的硬件校准来源。未建模额外共享Die端口、链路packet/control开销或电气接口；不能声称完整Core实现。现有`StatBankOperation`及`sense-finish`覆盖bank持有区间，包含传输等待，不应解释为纯NAND sense时间；使用独立Core观察回调区分ready/start/end。

解析式：单冷页额外时间 `ceil(4096*1000 / bytes_per_ns) + propagation_ps`。测试32B/ns+1000ps得到129000ps；另以4B/ns检查共享链路串行、独立链路重叠。它们是解析一致性用例，不是吞吐实验。

## 在线HBM并发

`src/online_hbm.hpp`保留HBXim的地址映射、单burst时序/refresh状态；新的在线适配器将父访问拆成burst，使用有限全局resident预算（闭环1024 bursts）以及每pseudo-channel FIFO。每PC最多一个burst在途，不同PC可并行。提交满额原子失败，不接受部分请求；每个父访问只有一个完成通知，最后一个burst真正完成后才释放数据依赖。

只有在当前事件时刻才能向HBXim提交burst；没有使用整页阻塞pump预先完成所有依赖。已提交burst非抢占；下一burst在真实完成事件才提交。此约束避免未知外部输入被未来服务吞掉，也牺牲PC内部bank并行。

**尚未实现完整HBM FR-FCFS/多bank MLP。** 本适配器是明确的并发子模型，不能称完整GPU HBM调度器。HBXim内部一个burst的命令序列仍按非抢占方式完成；后续若要研究bank级调度，需要可暂停的逐命令接口及独立HBM参考验证。

闭环通过`anns_loop_concurrent`启用有限Core和并发HBM，旧`anns_loop`保留串行对照。两者使用同一CPU IVF/rerank与输入。GPU仍是合成计算资源，实际数据仍来自sidecar；不据此报告硬件Recall/QPS/P99。

## 审稿验收

本轮能回答“实现是否满足所声明子模型的不变量”，不能回答“模型是否准确预测目标硬件”。

- 独立参考是部分规范的可执行解释；未覆盖条款不记PASS。随机测试不是穷尽证明。
- 数据token差分不能证明全部字节传输；闭环额外验证实际CPU字节和top-k，但尚未穿过GPU。
- 显式组序、半双工、bank持有、单burst/PC都需要公开；不笼统称为保守上界或下界，因为排队偏差可双向。
- 独立Die端口、真实GPU迁移、HBM更细并行、错误恢复和硬件/保留集校准仍是性能资格阻断项。
- 不恢复BIGANN吞吐前沿，不把本轮模拟时间写成实测。

规范来源：https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/


## Timeout differential extension

The independent model now tracks partial-generation expiration separately from
block erase preparation. Timeout emits status 5 for received write commands;
credits remain held until delivery. Retry discards old fragments. A pending erase
may backpressure a non-forwarded read in the declared backend adapter policy.
Completing the original erase permits reads and does not erase again for each
retry. This is a model-policy comparison, not a claim that OCP requires exactly
this admission timing. The first two new traces exposed missing erase lifetime
state in the oracle; failing traces remain in the local audit evidence. No test
was removed to obtain agreement. Exact deadline races remain unverified.
