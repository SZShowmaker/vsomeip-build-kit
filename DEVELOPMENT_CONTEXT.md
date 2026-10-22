# 开发交接

2026-10-22 完成交付整理及真实有线网络验证；2026-10-21 完成三平台构建与同机收发。本仓库新建，独立管理 vSomeIP SDK 的获取、编译、打包与最小验证，不依赖 adaptive-middleware，不修改已有 Fast DDS SDK 或业务项目。

已锁定 vSomeIP 3.6.4（提交见 sources.lock.json）、Boost 1.83.0，SHA256 校验下载。三平台为 Linux x64 GCC 11、ARM64 Linux GCC 9.2、Windows x64 MSVC 2022 /MD。上游 GCC 9 编译兼容补丁显式保存于 patches.json；Windows Boost 的工具链检测和链接差异在构建器中处理。

入口为 someip、someip.ps1 或 scripts/kit.py。支持 doctor/fetch/build/prefix/example/package；本地配置见 config.example.json。源码缓存 .cache/，每个平台的源树、Boost 私有构建、vSomeIP build 与 sdk 位于 out/<target>/。不同目标不共享可变源码树。SDK 提供核心/cfg/sd/e2e 动态库，Boost 静态私有链接，公开 API 不要求额外 Boost。

三平台 SDK 和示例已编译，SDK 换目录编译通过；Linux 隔离网络 UDP/TCP、Linux/Windows 本地重启恢复、ARM64 Linux 实板本地收发均通过。ARM64 Linux provider→Windows consumer 的真实网线直连 UDP（128 字节）及 TCP（4096 字节）均已通过服务发现、请求响应与事件通知：各 579 请求/响应，分别 594/593 事件，校验错误 0。详细计数及边界见 docs/VALIDATION.md。

后续接入 adaptive-middleware 仍需另外授权和设计：协议选择粒度、服务标识分配、序列化、服务/订阅状态机、失败语义、GUI/JSON/生成器与随包 SDK。当前包不提供 ara::com、AMW 绑定或全功能 AUTOSAR 符合性。

维护时不要直接修改 out 下的上游源码作为修复；应修改明确补丁再重建。不要把用户 IP 和工具链路径写成默认配置，不自动修改系统防火墙或持久网络配置。依赖版本/工具链改变须隔离旧构建目录。源码、测试与文档提交，生成物和本地配置由 .gitignore 忽略。

当前公共构建目标的 SDK 输出为 out/native/sdk、out/aarch64-linux/sdk、out/windows-x64/sdk。此前目标别名下的本地产物保留在原目录，不自动迁移或复用缓存；Windows SDK 由 Windows 原生构建目录复制并校验，不能用 Linux 重新编译它。out/packages 保存三平台归档和 SHA256。Git 以当前快照建立单条初始提交 main，旧本地 Git 元数据另行备份，尚未推送。用户已授权临时添加单个 SD 多播地址路由；测试完成后已删除，完整路由表与测试前一致，测试进程正常退出。若板端仍无多播路由，下一次运行仍需由环境维护者配置；构建工具不自动修改系统路由。

公开源码整理已将交叉目标与配置键统一为 aarch64-linux。新目标完整 SDK 构建、ARM64 示例编译与打包通过，4 项单元测试通过；本次未重跑 Windows/板端通信。原目标别名的本地配置与产物保留，后续使用通用目标名；新配置只存在忽略的 config.local.json。已检查公共候选文件中的已知内部信息及忽略边界，并纳入新的初始提交；不继承企业提交邮箱或旧远程地址，尚未推送。
