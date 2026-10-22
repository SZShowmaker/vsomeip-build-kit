# vsomeip-build-kit

独立构建 vSomeIP SDK，供上层中间件按路径引用。不修改或依赖 adaptive-middleware / fastdds-build-kit，不实现业务数据序列化或 `ara::com` 接口。

当前版本锁定 **vSomeIP 3.6.4 + Boost 1.83.0，C++17**。下载地址、上游提交及 SHA256 见 [sources.lock.json](sources.lock.json)。支持的构建目标为 Linux x64 GCC 11、ARM64 Linux GCC 9.2、Windows x64 MSVC 2022 Release `/MD`。实际运行验证范围见 [docs/VALIDATION.md](docs/VALIDATION.md)，交叉编译不能替代上板验证。

## Linux 首次构建

前提：Ubuntu 22.04 或具备等效工具的 Linux x64，Python >= 3.9、GCC/G++ 11、CMake >= 3.16、Ninja、curl。Ubuntu 可由环境维护者安装：

```bash
sudo apt-get update
sudo apt-get install python3 gcc-11 g++-11 cmake ninja-build curl
```

进入 clone 后的仓库根目录执行：

```bash
./someip doctor --target native
./someip build --target native --jobs 4
./someip example --target native
python3 scripts/test_local.py \
  --sdk out/native/sdk --exe out/native/example/someip_smoke \
  --output out/verification/native-local
./someip package --target native
```

预期：SDK 位于 `out/native/sdk`；独立示例位于 `out/native/example`；测试输出一条 JSON 报告，`errors=0`，响应和事件各不少于 10 条；压缩包和 SHA256 位于 `out/packages`。默认示例运行约 12 秒。本机双进程测试证明 IPC 收发，不证明网络 UDP/TCP。

首次构建会下载源码到 `.cache/`，逐次校验 SHA256；解压源码、构建中间文件、SDK 均留在 `out/<target>/`。网络失败可重新执行；校验失败会停止，不自动接受新摘要。离线环境可把同摘要源码包预先放入 `.cache/`。为兼容 Windows 长路径，解压时跳过名为 `doc` 或 `html` 的文档目录，不修改库实现源码。

## ARM64 Linux 交叉编译

在 Linux 仓库根目录首次复制 `config.example.json` 为被 Git 忽略的 `config.local.json`（已有配置直接编辑，避免覆盖），修改 `aarch64-linux.toolchain_root` 为 GCC 9.2 工具链根目录；`compiler_prefix` 默认为 `aarch64-none-linux-gnu`。模板中的 `/opt/toolchains/...` 是占位路径，不会自动下载工具链。

```bash
cp config.example.json config.local.json
# 编辑 config.local.json 后执行：
./someip doctor --target aarch64-linux
./someip build --target aarch64-linux --jobs 4
./someip example --target aarch64-linux
./someip package --target aarch64-linux
```

产物在 `out/aarch64-linux/sdk`、`out/aarch64-linux/example`。生成的 `out/aarch64-linux/toolchain.cmake` 只用于本机构建，不随 SDK 作为固定工具链配置交付。更换工具链或编译器时，先另存旧 `out/aarch64-linux` 并重新构建，避免复用旧 Boost/CMake 缓存。板端部署与双机测试见 [测试指南](docs/TESTING.md)。

## Windows 原生构建

前提：Windows x64，Python >= 3.9 在 PATH，Visual Studio 2022 Build Tools 安装 **C++ x64/x86 工具、Windows SDK、CMake/Ninja 工具**。构建器用 vswhere 查找 VS 2022 并自动导入 x64 开发环境。运行程序需要匹配的 Visual C++ x64 Runtime。

在 Windows 本地磁盘 clone 本仓库，进入根目录，使用 PowerShell：

```powershell
python scripts/kit.py doctor --target windows-x64
python scripts/kit.py build --target windows-x64 --jobs 4
python scripts/kit.py example --target windows-x64
python scripts/test_local.py --sdk out/windows-x64/sdk --exe out/windows-x64/example/someip_smoke.exe --output out/verification/windows-local
python scripts/kit.py package --target windows-x64
```

也可用 `./someip.ps1` 代替 `python scripts/kit.py`，前提是当前 PowerShell 策略允许执行脚本。无需修改系统执行策略。Windows SDK 在 `out/windows-x64/sdk`，压缩包为 ZIP。不能拿 Linux/ARM `.so` 给 MSVC 链接，也不能在 WSL 中把 Linux Python 构建当作 Windows 原生构建。

## 交付与集成

- SDK 包含公开头文件、核心/配置/发现/E2E 库、CMake package、来源和文件摘要、许可证、最小示例源码。
- Boost filesystem 及其所需库作为私有静态依赖链接到 vSomeIP 动态库；公开头文件不依赖 Boost。SDK 使用者无需另行安装 Boost。
- Linux 交付库剥离非必要符号，保留真实文件与 SONAME 软链接；未剥离库仍在 `out/<target>/build`。Windows 使用 Release DLL + import LIB。
- 不打包目标操作系统的 libc/libstdc++ 或 Windows 系统运行库；目标系统仍须满足 ABI。
- DLT 和 systemd 集成关闭；保留 cfg/sd/e2e 插件，但未声明已验证 E2E、安全策略、性能或所有上游功能。
- 当前 SDK 是 vSomeIP 独立通信基础，尚未接入 adaptive-middleware 的 NetworkBinding、GUI 或 src-gen。

完整集成步骤见 [SDK 使用说明](docs/SDK.md)。构建诊断、网络与恢复测试见 [测试指南](docs/TESTING.md)。上游编译兼容调整以可核对前置文本的 [patches.json](patches.json) 保存；应用前置不匹配即停止。

## Git 与协作

提交脚本、版本锁、补丁、示例、测试、文档和配置模板。`.cache/`、`out/`、`local/`、`config.local.json` 和 `config.*.local.json` 自动忽略。工程师自己的测试工程放 `local/`，构建输出放 `out/`；对正式源码或测试的修改应继续显示在 `git status` 中。

```bash
python3 -m unittest discover -s tests -v
./someip --help
git status --short
```

不要修改全局 Git 配置或依靠个人 hooks 才能忽略生成物。第三方许可见 SDK 的 `licenses/` 和来源清单；本仓库不代替上游许可，也不声明 AUTOSAR AP 符合性。

公开源码、模板和文档统一使用 `aarch64-linux` 作为 ARM64 Linux 交叉编译目标。已有本地配置只需在该键下填写工具链参数；旧目标目录和 SDK 不自动删除或移动。新目标首次构建输出 `out/aarch64-linux/`，不能把旧 CMake/Boost 缓存直接改名后复用。已有 SDK 仍可通过 example 的 `--sdk` 参数显式用于编译验证。

内部项目名称、设备地址和真实安装路径仅保存在忽略的本地文件中。公开前审查主分支文件和提交历史；`.gitignore` 不会清除历史，也不控制 SDK 包里的内容。已有 SDK 中的旧文档、构建信息和业务配置不会自动更新，公开交付需另行审查。

## 新公开仓库的首次推送

本地 main 从当前完整源码快照开始，仅包含一条初始提交；旧 Git 数据保存在仓库外，不作为公开分支或标签携带。已有本地配置和生成物仍由忽略规则保护。

在 GitHub 新建空仓库，不自动添加 README、许可证或 .gitignore；然后在对应本地仓库根目录执行下列命令，将示例 URL 替换为自己的新仓库地址：

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

首次推送只指定 main，不使用 --mirror，不从旧备份导入历史或分支。提交前检查 `git log -1 --format=fuller`，作者及提交者邮箱应为个人公开邮箱或 GitHub noreply 邮箱；避免全局企业邮箱进入后续提交。本地仓库配置可单独设置身份，无需修改全局 Git 配置。
