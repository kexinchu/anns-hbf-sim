# 外部数值对齐审查（2026-11-23）

结论：目前有规范参数与部分架构行为的一致性证据，**尚无论文整条曲线复现或 HBF 硬件预测误差证据**。本次只运行 CPU 上的确定性诊断微轨迹，没有恢复 ANNS 性能实验，也未修改生产模型默认参数。

## 来源与证据等级

| 外部来源 | 可用参照 | 不能据此宣称 |
|---|---|---|
| [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/)，表 2/4，§5.1.2.1–3 | 速率、模块上限、页/命令单位等规范参数 | 实际产品吞吐、NAND sense 延迟或 P99 已测量 |
| [Characterizing and Exploiting Dense Retrieval on High Bandwidth Flash](https://research.ece.cornell.edu/retrieve/camera-ready/retrieve26-final50.pdf)，表 II、§IV、图 3(b) | 与 ANNS 最相关；16 通道×4 die×16 bank，4 KiB 页，2.72 μs nominal sense；冷随机 256 B 的页利用率 6.25% | 2.72 μs 是硅实测；只匹配该输入就证明模型正确 |
| [FlashLab HBFSim 论文](https://arxiv.org/html/2610.23503v1)，§3.5、表 1 | GPU 算子与完整请求的留出验证方法；HBF read=4 μs 是明确的假设 | GPU 校准误差可用于证明 HBF 时序准确 |
| [SlugLab HBFSim](https://github.com/SlugLab/HBFSim) 的公开校准说明 | 区分 wall time / modeled time；披露 SSD 软件路径与拟合点 | SSD 路径等于 HBF；拟合点吻合等于留出集验证 |

来源固化：
- OCP PDF SHA256：`307531eb8053f00cbeccbc907ddff0a9c4fe6f9d0066a077ce33b0ac99312da3`。
- 检索论文 PDF SHA256：`9daf8a1e790a44ee2babaa3fd4853ee65c990e275b01338159aca7b5c5d6b4a9`。
- FlashLab 论文固定为 arXiv v1；不能假设本地旧 pin 等于论文完整工件。
- 本地 FlashLab pin：`8ab183cc511770649c084eb58b048aabfc60afbc`；SlugLab pin：`696cc8418e2d2375cdfd249ca5833dfd97e1e0f2`。本次未更新 donor。

## 已运行的对齐与发现

### 1. OCP 带宽口径有分歧，不能偷偷选有利的一组

| 档位 | 表 4（GB/s） | §5.1.2 的每模块×最大模块数 | 当前代码的配置值 | 相对表 4 |
|---|---:|---:|---:|---:|
| SG1 | 384 | 48×8=384 | 384 | 0% |
| SG2 | 1536 | 94×16=1504 | 1504 | −2.0833% |
| SG3 | 3072 | 188×16=3008 | 3008 | −2.0833% |

测试调用实际 `ucie_speed_profile()`，不是用脚本自己生成“模拟器结果”。这些是配置上限，不是实测吞吐。当前实现明确采用分节数值；论文采用表 4。该差异分类为 `SOURCE_CONFLICT`，不把它误报成硬件预测误差，也不自动修成 96/192 GB/s。

### 2. 当前默认 sense 与论文差 27.2 倍

实际 EventLab 默认是 100000 ps = 100 ns。检索论文表 II 是 2.72 μs，正文有约 2.7 μs 的舍入表述，测试固定采用表 II。FlashLab 论文采用 4 μs，但模型拓扑也不同，不能直接比较端到端 QPS。

在三个独立 fixture 中分别使用默认 100 ns、检索论文 2720 ns、FlashLab 假设 4000 ns，并记录真实 `sense-issue` / `sense-finish` 事件。每个 fixture 四种访问：单次冷 256 B、同页两个 256 B、不同 bank 两个冷页、同 bank 两个冷页。共 **12 个运行场景**。

结果：事件间隔分别为 100/2720/4000 ns；单次冷 256 B 的 sense 数是 1、页利用率 6.25%；同页复用只 sense 一次；不同 bank 的 sense 重叠；同 bank 串行。这确认参数单位、传递路径和局部架构行为，**不是对这些延迟数值的独立物理验证**。

原生 DeviceDriver 不支持直接 256 B burst read，因此使用 HostDriver 将 256 B 请求拆成四个 64 B 命令；保留真实组装与页缓存行为。初始化写入 16 KiB 后开始计时；所有读检查 expected_content，确认逻辑完成及资源回收。初版 fixture 请求 read_burst 被明确拒绝，随后改用这一受支持路径；也纠正了动态提交的绝对 release time，未放宽运行时检查。

该微轨迹只用 1 通道、1 die、2 banks，Core Channel 保持理想模型，以隔离 sense 行为。**它没有复现论文的 512 GiB、1024 banks 配置或图 3 的吞吐曲线**。`elapsed_ps` 包含本 fixture 的其它开销，不应与论文未知计时边界直接比较。

### 3. 不能用带宽拟合点循环证明 sense 正确

论文明确说明 sense 为匹配 SG2 带宽而设定。独立算术检查：1024 banks×4096 B/2.72 μs≈1542.02 GB/s，接近 1536 GB/s。这个理想媒体供给上界不包含队列、核心总线、响应传输和依赖限制；它不是本模拟器测出的带宽，也不能作为独立验证集。

### 4. 其它模拟器不是自动成立的 ground truth

FlashLab 论文把 GPU 校准与 HBF 假设分开，值得沿用；不能借用其 A100/H200 误差数字评价本项目。其本地 pin 的 `evidence/external/assets/README.md` 还明确把 Ramulator2 共享检查限定为字节计数、MQSim 限定为直接页 I/O；这不验证 HBM/HBF 时序。本项目已经复用 HBXim 的部分模块，同源实现之间相等也不能算完全独立证据。

## 下一层验证的预先约束

1. 保留 OCP 表 4 和分节两套具名口径，分别报告；未澄清前不混成一个“标准精确值”。
2. 建立与检索论文相同几何与地址映射的专用 profile，冻结默认、论文和保守替代时序。禁止为每条曲线分别调 sense。
3. 用冷/热、256 B/4 KiB、独立/依赖、单 bank/跨 bank、不同队列深度进行相同输入的跨引擎比较。分别计 useful bytes、sense bytes、core bytes 和 wire bytes。
4. 必须获得论文轨迹/工件及计时口径，或明确仅复现自行定义的等价微基准。没有精确原始数据时保留“未复现”，不能从图片读近似值后宣称 0% 误差。
5. 架构计数和完成状态要求精确一致；时间误差按每个请求报告绝对误差、相对误差、分位数及最大误差。未取得独立参考前，不任意宣布某个百分比已经通过。
6. 最终物理校准仍需真实设备的留出测量；A6000 只能校验 GDDR6/CUDA 路径，不能承担 HBM/HBF 的证据角色。

## 复现与原始结果

```sh
cmake -S . -B build
cmake --build build --target external_alignment_probe -j4
python3 tests/external_alignment.py build/external_alignment_probe results/external-alignment
```

原始结果位于 `run-20261123/`。测试 PASS 表示本审查的确定性检查通过，并不表示外部校准通过；JSON 始终保留 `hardware_calibrated=false`、`paper_curve_reproduced=false`、`performance_ready=false`。

保留的 `fixture-failure-20261123/` 是测试适配器计数口径错误：`logical_success` 按 64 B fragment 计数，初版误按父请求计数。修正为检查每个父请求的完成状态，未改动运行时；最终结果单列于 `run-20261123/`。
