# 最小收发与故障定位

工作目录均为构建仓库根目录。先按 README 构建 SDK 和 example。正常测试退出码为 0，最后打印 `RESULT` JSON；响应和事件至少 10 条、`errors=0` 才算通过。日志与报告由 `--output` 指定，放 `out/verification/`。

## 同机与重启恢复

```bash
python3 scripts/test_local.py --sdk out/native/sdk \
  --exe out/native/example/someip_smoke --output out/verification/native-local
python3 scripts/test_local.py --sdk out/native/sdk \
  --exe out/native/example/someip_smoke --output out/verification/native-restart --restart
```

Windows 换成 `out/windows-x64/sdk` 和 `out/windows-x64/example/someip_smoke.exe`，通过 Windows Python 执行同一脚本。`--restart` 保留 consumer，停止并重启 provider；还必须观察到 `discoveries>=2` 和 `losses>=1`。同机连接通过 vSomeIP 本地路由，不据此声称实际走 UDP/TCP。不要同时运行两个使用相同示例应用 ID 的同机测试。

## Linux 隔离网络

需要 `iproute2`、`util-linux`、`mount`，内核允许非特权 user/network/mount namespace。脚本拒绝在宿主 root namespace 直接运行。

```bash
unshare -Urnm python3 scripts/test_network.py --sdk out/native/sdk \
  --exe out/native/example/someip_smoke --output out/verification/network-udp --transport udp
unshare -Urnm python3 scripts/test_network.py --sdk out/native/sdk \
  --exe out/native/example/someip_smoke --output out/verification/network-tcp --transport tcp
```

脚本建立两个临时网络 namespace 与 veth，地址为 `192.0.2.1/24`、`192.0.2.2/24`，使用各自 routing manager 和不同本地 IPC 路径，确保经过网络。UDP 载荷 128 字节，TCP 4096 字节。网络空间随测试销毁，不修改宿主网卡、路由或防火墙。若系统禁用 namespace，可在两台独立主机验证，不能把失败记录成协议不支持。

## ARM64 Linux 与 Windows 双机

两端网卡需直连或同网段，双向允许 UDP 30510（SD，多播 `224.244.224.245`）、业务端口 30511（UDP 或 TCP）及协议选用的客户端接收端口。此工具不会修改防火墙。JSON 的 `--address` 是**该进程所在主机的本地 IPv4**，不是对端地址。

板端还必须能路由 SD 多播地址。可先只读执行 `ip route get 224.244.224.245`；若返回 Network is unreachable，由网络维护者配置对应网卡的多播路由，再测试。本工具不自动更改板端路由。

以下命令给出完整可执行流程，IP 变量需按实际网卡修改。Linux 构建机生成配置，参数使用示例地址：

```bash
BOARD_IP=192.0.2.10
WINDOWS_IP=192.0.2.20
python3 scripts/smoke_config.py --role provider --address "$BOARD_IP" --transport udp --output out/board-provider.json
python3 scripts/smoke_config.py --role consumer --address "$WINDOWS_IP" --transport udp --output out/windows-consumer.json
```

把 `out/aarch64-linux/example/someip_smoke`、`out/aarch64-linux/sdk/lib/` 中全部 `libvsomeip3*.so*` 及 `out/board-provider.json` 复制到板端独立测试目录，例如 `/tmp/vsomeip-smoke/`，保持 `lib/` 子目录及软链接。可用不压缩的 tar 传输；部分板端 BusyBox tar 不支持 `-z`。不要覆盖现有业务 App 或 `/opt/lib`。板端执行：

```sh
cd /tmp/vsomeip-smoke
export LD_LIBRARY_PATH="$PWD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VSOMEIP_CONFIGURATION="$PWD/board-provider.json"
export VSOMEIP_APPLICATION_NAME=vsk_provider
./someip_smoke provider udp 60 128
```

把 `windows-consumer.json` 复制到 Windows 构建仓库的 `out/` 目录（不存在时先创建），本机网络配置不要放进公开源码目录。在 provider 启动后，于 Windows PowerShell 执行：

```powershell
$env:PATH = "$PWD/out/windows-x64/sdk/bin;$env:PATH"
$env:VSOMEIP_CONFIGURATION = "$PWD/out/windows-consumer.json"
$env:VSOMEIP_APPLICATION_NAME = 'vsk_consumer'
./out/windows-x64/example/someip_smoke.exe consumer udp 15 128
```

TCP 验证应重新用 `--transport tcp` 生成**两端** JSON，将运行参数改为 `tcp`，两端载荷统一改为 `4096`。示例允许 UDP 8..1200、TCP 8..65536 字节；并未配置 SOME/IP-TP，不能拿这个 UDP 示例直接承诺大型感知结构体的传输能力。

## 出错时检查

1. SDK 加载失败：确认目标架构和 ABI，Linux 检查库软链接/LD_LIBRARY_PATH，Windows 检查 PATH、cfg/sd DLL 及 VC++ Runtime。
2. 没有发现：先检查网卡本地 IP、SD 多播和端口、网线与防火墙，确认两端服务 ID/instance/major 相同。
3. 发现但没有事件：检查 event/eventgroup、两端可靠性和载荷长度一致，确认 consumer 订阅成功；以 RESULT 中计数为准。
4. 构建 SHA256/补丁前置失败：保留日志，核对下载源与版本锁，不随意更新摘要来绕过检查。
5. 构建缓存与新工具链冲突：另存旧 `out/<target>`，重新构建；不混用不同编译器生成的 Boost 静态库。

示例固定 service `0x6b10`、instance `0x0001`、method `0x0101`、event `0x8001`、eventgroup `0x0001`，仅用于该独立验证。不是后续中间件服务编号规范。
