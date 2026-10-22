# 验证记录

三平台构建与同机验证：2026-10-21；交付整理、真实 ARM64 Linux↔Windows 有线网络验证：2026-10-22。基线：vSomeIP 3.6.4 / Boost 1.83.0；三平台 C++17，Release。

| 范围 | 已有证据 |
|---|---|
| Linux x64 | GCC 11.4 SDK、独立示例编译通过；SDK 换目录后重新编译、文件摘要验证通过。 |
| ARM64 Linux | GCC 9.2.1 SDK、同一示例交叉编译通过；SDK 换目录后编译与文件摘要验证通过。 |
| Windows x64 | MSVC 19.44（VS 2022）Release /MD SDK 与独立示例编译通过；SDK 换目录后编译运行通过。 |
| Linux 同机 | 395 请求/395 响应、396 事件，校验错误 0。 |
| Linux 重启 | consumer 持续运行，provider 重启，发现 2 次/失联 1 次，785 响应和事件，错误 0。 |
| Linux 隔离 UDP | 两个独立网络 namespace + veth，128 字节载荷，392 请求/响应、392 事件，错误 0。 |
| Linux 隔离 TCP | 相同隔离网络，4096 字节载荷，394 请求/响应、394 事件，错误 0。 |
| Windows 同机 | 386 请求/响应、386 事件，错误 0。 |
| Windows 重启 | 发现 2 次/失联 1 次，754 请求、753 响应、753 事件，错误 0；重启窗口有 1 请求未响应。 |
| Windows SDK 移位运行 | 387 请求/响应、386 事件，错误 0。 |
| ARM64 Linux 实板同机 | 396 请求/响应、396 事件，错误 0，进程正常定时退出。 |
| ARM64 Linux→Windows 有线 UDP | SD 发现成功，128 字节载荷，579 请求/579 响应、594 事件，校验错误 0，两端正常退出。 |
| ARM64 Linux→Windows 有线 TCP | SD 发现成功，4096 字节载荷，579 请求/579 响应、593 事件，校验错误 0，两端正常退出。 |

测试计数来自单次有界运行，不是吞吐或可靠性保证；启动/退出窗口可少收通知。同机测试采用本地路由，不当作 UDP/TCP 网络证据。没有运行上游完整测试套件、长稳/压力、安全/E2E、SOME/IP-TP 或 AUTOSAR 一致性测试。

## 构建兼容处理

- GCC 9：移除不支持的两个告警开关，仅将 conversion 从错误降为保留告警；适用条件限制为 GNU < 10，保留其他 `-Werror`。具体补丁见 patches.json。
- Windows：明确指定 VS 2022 的 vcvarsall 路径，避免 Boost 自动检测误指向编译器 bin；关闭 Boost 隐式自动链接，由 CMake 显式链接构建出的私有静态库。
- SDK CMake 包安装使用相对目录；Linux pkg-config 不含构建机器绝对路径；Linux 共享库 RUNPATH 为 `$ORIGIN`。
- SDK 公开头文件无需 Boost。ELF 依赖检查未出现外置 Boost/DLT/systemd 运行库；ARM64 Linux 构建需要的 glibc 符号基线为 2.17，实板加载已验证。

## 证据位置与重跑

本机证据为忽略的 `out/verification/`，Windows 原生构建目录中也有同名目录；它们不随 Git clone。首次全量构建日志曾位于 /tmp，环境重启后已不可用；交付整理时的增量构建日志保存在 `out/verification/build-logs/`，不能当作全量构建日志。正式可重跑入口为 README、TESTING.md 和 scripts 中的测试工具。真实板端 IP、工具链绝对路径等属于本地环境，不作为团队默认。

## 交付整理检查（2026-10-22）

源码解压越界/链接拒绝、配置生成、补丁前置不匹配拒绝、SDK 内容损坏/额外文件检测共 4 项单元测试通过。打包前校验 SDK 的完整文件集合及 SHA256；三平台 SDK 汇总到 out/<target>/sdk，压缩包在 out/packages/。当时独立 Git 仓库已初始化，尚未提交；后续公开基线状态见文末。adaptive-middleware 工作区保持无改动。

## 真实有线网络与环境恢复（2026-10-22）

ARM64 Linux 运行 provider，原生 Windows 运行 consumer，验证服务发现、Windows→ARM64 Linux 请求、ARM64 Linux→Windows 响应和事件通知。UDP 与 TCP 分别运行，TCP 模式下 SD 仍使用 UDP。未测试 Windows 提供服务的反向部署、跨机重启恢复或长稳负载。

首次尝试发现失败时，板端缺少 SD 多播地址路由。改为有线直连后该路由仍缺失；经用户明确授权临时添加 `224.244.224.245/32 dev eth0` 后，两种业务传输均通过。测试在 finally 中删除该路由，测试前后完整 `ip route show` 文本一致。复核测试进程退出，未修改持久网络配置、防火墙或已有业务程序。恢复后再次测试仍需由环境维护者提供有效多播路由。

证据为 `out/verification/direct-20261022/` 下两种协议的 provider/consumer 日志、report.json、routes-before/during/after.txt 及测试执行脚本。测试 IP 与脚本中的本机路径仅留在该忽略目录。

## 2026-10-22：通用交叉编译目标与公开文件

公共目标及配置键统一为 aarch64-linux，文档、模板和帮助同步；本机工具链配置添加新键，原配置与旧产物保留。Windows 测试网络配置按指南放 out/，个人配置与环境文件由 Git 忽略。

4 项单元测试、已知内部标识扫描、忽略边界及帮助检查通过。用现有本地 GCC 9.2 工具链在新的 out/aarch64-linux/ 中完整构建 Boost/vSomeIP，SDK、ARM64 示例编译和打包通过；打包前校验 61 个 SDK 文件的摘要。未执行新的 Windows 构建或板端/网络运行测试，历史通信结果不视作本次重跑。

以当前完整源码建立新的单提交 main；原 Git 元数据保存在仓库外，不继承旧远程地址或企业提交邮箱，尚未推送。旧 SDK/压缩包与本地日志没有删除，也没有被自动转换成可公开制品。
