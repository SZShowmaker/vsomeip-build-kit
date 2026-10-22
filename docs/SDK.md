# SDK 使用说明

SDK 是一个可整体复制的目录；各平台必须使用对应版本。先完成构建，或解压对应 SDK 压缩包。Linux tar 包的根目录是 `sdk/`，Windows zip 内容直接是 SDK 文件。

## 从 SDK 编译完整示例

以下 Linux 示例在解压后的 SDK 根目录执行，输出在包外：

```bash
cmake -S examples/smoke -B ../smoke-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$PWD"
cmake --build ../smoke-build --parallel 4
../smoke-build/someip_smoke --help
```

Windows 在 VS 2022 x64 开发环境中、SDK 根目录执行：

```powershell
cmake -S examples/smoke -B ../smoke-build -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$PWD"
cmake --build ../smoke-build --parallel 4
$env:PATH = "$PWD/bin;$env:PATH"
../smoke-build/someip_smoke.exe --help
```

这些命令只编译示例，不会自行建立通信配置。收发需要指定 JSON 和应用名，完整配置生成及运行命令见构建仓库的 `docs/TESTING.md`。

## 应用工程接入

随 SDK 的 `examples/smoke/CMakeLists.txt` 与 `main.cpp` 是可直接编译的完整工程。自己的 CMake 工程使用：

```cmake
# 这是嵌入已有 CMakeLists.txt 的片段；my_app 应已由应用工程定义。
find_package(vsomeip3 3.6.4 EXACT CONFIG REQUIRED)
target_link_libraries(my_app PRIVATE vsomeip3)
target_compile_features(my_app PRIVATE cxx_std_17)
```

配置时把 SDK 根目录放入 `CMAKE_PREFIX_PATH`。Linux 运行时把 SDK `lib/` 加入 `LD_LIBRARY_PATH`，或为应用安装布局设置相对 RPATH；核心库使用 `$ORIGIN` 查找同目录插件。Windows 把 SDK `bin/` 放到应用 exe 同目录或加入进程 PATH。仅复制核心库不够，运行配置与发现分别需要 cfg/sd 插件；建议整体交付四个 vSomeIP 库。

ARM64 Linux 必须使用 GCC 9.2 对应 ARM64 Linux 工具链。工具链文件属于应用构建配置，不能用 SDK 路径推断目标板的 sysroot。Release SDK 不支持混用 MSVC Debug `/MDd` 对象；Windows 应用统一 `/MD`。

## 内容与追溯

- `include/vsomeip/`：公共 API。
- `lib/`：Linux 共享库/软链接或 Windows 导入库；`bin/`：Windows DLL。
- `lib/cmake/vsomeip3/`：可搬移 CMake 导入目标；Linux 另有相对路径 pkg-config 文件。
- `sources.lock.json`：上游版本、下载 URL、SHA256、vSomeIP 提交。
- `patches.json`：构建兼容调整；`licenses/source-modifications/` 保存实际修改的上游文件。
- `build-info.json`：平台、编译器、构建模式、补丁摘要；`manifest.sha256.json`：文件校验摘要。
- `licenses/`：MPL-2.0、Boost BSL-1.0；原始源码可按版本锁下载，修改内容随包提供。

SDK 不包含应用消息类型或自动序列化代码。示例显式编码为 magic/version + 大端帧号 + 确定性字节数据，避免把 C/C++ 结构体内存直接跨平台发送。后续中间件接入需另外定义类型编码、服务标识和订阅状态语义。
