# 链路计费核对与冻结 v2 曲线边界

## 原始来源和口径

2026-11-24 重新核对 [OCP HBF v0.7.0 官方 PDF](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/)：

| 来源 | 数值与含义 | 是否能直接作为本模型的 payload 带宽 |
|---|---|---|
| p16 Table 2 | SG3 示例：4096 GB/s 原始带宽，AXI link 层效率 75%，3072 GB/s 有效带宽 | 已含效率，不能再次无依据扣相同开销 |
| p16 Table 4 | SG2 最大用户带宽 1.536 TB/s | 是规范汇总值，不是本文有限批次实测 |
| p32 §5.1.2.2 | 每模块 raw 128 GB/s、system 94 GB/s，最多 16 模块 | 94 已不是 raw；16×94=1504，与汇总1536不相等 |
| [检索论文](https://research.ece.cornell.edu/retrieve/camera-ready/retrieve26-final50.pdf) Fig.3 caption、§IV | 使用 1.536 TB/s；nominal sense 按满 bank 利用时吞吐选定 | 拟合条件不能再次充当独立验证 |

规范正文给出的 94 与汇总隐含的 96 GB/s 相差 2.0833%；本次查阅的条款没有解释该差异。不能擅自认定为舍入、排版错误或另一层已知开销。

## 参数证据分层

| 项目 | 当前取值 | 证据等级 / 限制 |
|---|---|---|
| 比较拓扑 | 512GiB、16通道×4die×16bank、4KiB页、每bank双缓冲 | 论文Table II的比较配置；OCP上限不等于每台设备的实际配置 |
| 地址布局 | 先通道、再bank、die；256页/块、512块/bank | 前述分布有论文/OCP示例支持；具体块分解与固定4KiB条带属于本协议选择 |
| sense | 2.72us | 论文nominal输入，源论文做过吞吐一致性拟合；不是测得的产品延迟 |
| 缓存顺序、Core路径 | FIFO、ideal Core | 当前模型选择/已测试实现；论文数值结果不足以确认其所有调度细节 |
| 读拆分 | 每64B一个命令，无burst-read | 当前DeviceDriver支持子集；不能证明论文的命令组装完全一致 |
| 缓冲与固定延迟 | ingress16/16KiB、egress8/512B；固定100ps，cache-access100ps | 模型假设，无独立物理校准 |
| MOCS、parent QD、到达、工作集 | 见冻结v2 | 本地对照协议；论文未给可匹配完整定义 |
| 冷/热定义与随机种子 | 初始化后冷、全预读后热；8301/2718 | 本地验证协议；两seed范围不是统计置信区间 |

## 实际代码做了什么

`UcieExecutionConfiguration::serialization` 对 **service-equivalent bytes** 计算 `ceil(bytes*1000/rate)` ps。`DeviceDriver::try_submit` 对无数据读命令计16B请求服务量；`start_response` 对成功64B读计64+16=80B返回服务量。请求和响应方向、不同物理channel各自占用序列化资源；固定100ps延迟不继续占用带宽。正常路径不执行逐 flit 打包、CRC、retry 或 SYNC 流量，因此这些曲线不能声称反映了真实 wire efficiency。

16B在头文件中明确标注为模型服务量，不是规范包长。用已经有效化的94GB/s再计这项成本，会进一步降低64B payload速率；**它可能重复计入部分协议效率，目前没有独立证据能标定重叠部分**。正确处理是标明模型边界，保留冻结数据，不是改为128、96或删除16B直到曲线贴近目标。

- 连续算术 payload 上界：`16*94*64/80=1203.2 GB/s`。
- 每命令整数ps取整：`ceil(80000/94)=852 ps`，对应上界 `16*64000/852≈1201.878 GB/s`。
- 这些只是当前正常成功读模型的服务上界。队列、缓存、启动/排空还会降速；不是硬件测量。

仅作口径算术检查：若把94GB/s当payload预算，64B序列化为681ps；若用Table4隐含的96，则为667ps。若把128GB/s raw直接配80B服务量，则是625ps，对应1638.4GB/s payload上限，反而超过Table4。三者不是本轮执行的替代配置；这说明不能靠换一个除数解决wire模型缺失。

新增 `link_accounting_probe` 在真实 HostDriver→DeviceDriver 路径上覆盖3档速率、16/32B返回服务量、0/100ps固定延迟、两个物理channel。Python参考直接从整数公式验证handoff→arrival、response-issue→delivered、同channel不重叠与跨channel重叠；12配置、1536读命令，以及3个损坏计费对照。它证明实现遵守声明的成本模型，**不能证明这个成本模型等于物理HBF链路**。

## 冻结网格与拟合隔离

继续使用原封不动的 `protocol-v2.json` 和SHA256：256B/4KiB，冷/热，连续/随机/依赖随机，QD 1/16/128/1024，MOCS4096主配置/256对照，种子8301/2718，共192点。依赖访问保留四个配置QD实际运行，验证有效QD恒为1的结果不变；未用复用结果代替执行。

每点保存输入、每请求提交/完成时间、事件指纹、退出状态及程序墙钟；独立检查补充到达时刻、计数、唯一ID、sense数量、页效率、每channel服务下界、P99 nearest-rank。热访问sense=0时页效率未定义，不能画成0或100%。曲线是有限1024请求批次，初始化/预热不计入计时，启动/排空计入；不是稳态最大带宽。

还需区分已初始化4MiB与实际触达范围：1024个连续256B请求只触达256KiB/64页，而256B随机跨页触达4MiB/1024页；按本映射分别涉及64和1024个bank。它们有相同用户字节数，但不是相同活跃bank/触达footprint的对照。4KiB连续与随机都触达1024页。不得将两种256B模式的吞吐差全部归因于页效率。

本网格每个活跃bank最多触达一页，未施加双缓冲替换压力。它覆盖冷激活与预热命中，不能替代长工作集/容量冲突、read retry、refresh或错误恢复流量下的带宽验证；那些机制测试与本次正常读曲线是不同证据。

本轮没有拟合参数，两种子均为验证输入；同一次确定性仿真的种子范围不是置信区间。paper nominal sense只是继承输入；它不是独立实测依据。若以后引入payload-budget模型或显式wire模型，应另建版本和拟合数据清单，禁止回写v2或把已查看的验证点作为未见验证集。

## 仍然不能宣称完成的事项

论文Fig.3(b)给出六类结果，不提供完整QD曲线及对应命令窗口、到达过程、footprint和冷/热准备。当前只比较可核验的结构和定性机制；不从图片制造精确原始数据，不把1536的规格上限当成每点实测。论文精确复现还需要匹配的工作负载定义/数值数据；物理校准还需要独立设备证据。

`performance_ready=false`、`hardware_calibrated=false`、`paper_curve_reproduced=false`。本轮仅运行CPU组件验证与校准诊断；ANNS性能实验仍关闭。

## 复现入口

```sh
python3 bootstrap.py
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DANNS_DEVICE_INDEX=ON
cmake --build build --target large_window_probe link_accounting_probe -j 4
python3 tests/link_accounting_contract.py build/link_accounting_probe /tmp/link-accounting
python3 tests/paper_curves_v2.py build/large_window_probe /tmp/frozen-v2 --workers 4
python3 tests/audit_paper_curves_v2.py /tmp/frozen-v2
python3 scripts/plot_paper_curves_v2.py /tmp/frozen-v2
```

输出目录必须不存在，避免静默复用或覆盖旧结果。每点900秒是CPU程序执行预算，不是模拟请求deadline或P99门槛；并行workers只加速独立进程，不改变各点模拟到达方式。若超时/断言失败则保留无效点并不生成成功总判定。大网格不加入短时CI，CI只跑机制和验证器回归；全网格须显式运行并离线审计。


## 本轮最终结果

[192点原始证据与曲线](../calibration/paper-curves/v2-20261124/README.md)全部成功并经离线逐请求复核；ON/CHECK各38项回归通过。链路计费12配置/1536读命令与3个负向对照通过，曲线验证器另拒绝5种损坏记录；上次提交的GitHub CI已核实成功。

必须保留一个未对齐现象：QD1024/MOCS4096下，冷256B顺序与随机均为89.211GB/s，尽管页效率分别为100%和6.25%。该短批次各bank最多一页，不能复现长流式页面周转；冷4KiB也只有675.394GB/s。热4KiB达到1201.716GB/s，与本模型服务上界一致。这里有机制一致性证据，但没有完整论文曲线复现或硬件校准证据。

另一个不能隐藏的现象：256B热态低QD下随机访问快于连续访问。由冻结4KiB条带映射直接计算，初始QD16的连续访问只覆盖1个channel，随机种子分别覆盖10/11个。此处地址并行度不同；记录见 `initial-window-mapping.json`。这不是“顺序访问应总是更快”的验证，也不能据此调参修正曲线。
