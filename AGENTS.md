# 仓库维护

先读 README.md、DEVELOPMENT_CONTEXT.md，核对分支、工作区和本次任务。这里是独立 vSomeIP SDK 构建仓库，不自动修改 adaptive-middleware 或业务项目。

- 依赖版本与摘要以 sources.lock.json 为准，不在失败后自动接受新摘要。
- 上游兼容修改记录在 patches.json，前置文本不匹配应失败；不手改 out 中源码作为正式修复。
- 三平台使用同一源码基线，Windows 为原生 MSVC Release /MD，ARM64 Linux 工具链由 config.local.json 配置。
- 不把本机绝对路径、设备 IP、生成物或日志提交。不要忽略正式源码修改。
- 区分构建、同机 IPC、隔离网络、Windows 运行与真实板端证据。测试通过不等于 AUTOSAR 符合性。
- 运行配置须显式指定；不修改系统网络、防火墙、业务 App 或系统库目录。
- 新命令同步帮助与文档；交付文件变化更新 SDK manifest；重要工作同步交接和验证记录。
- 常用检查：python3 -m unittest discover -s tests -v；各平台 build/example；scripts/test_local.py；Linux scripts/test_network.py。
