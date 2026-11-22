# Skyward for Lenovo Legion Y700 (4th Gen) / TB322FC（elden）

把 [kirklin/skyward](https://github.com/kirklin/skyward)（用 Rust 从零写的 Android recovery）移植到联想 Y700 四代 TB322FC 的仓库：设备配置、打包与签名工具、GitHub Actions 构建，以及针对这台机器 SELinux 限制的改动。

上游在 [lemonsn/skyward](https://github.com/lemonsn/skyward) 的 `elden` 分支上，本仓库只放设备相关的东西。

## 现状（2026-11-22）

| 功能 | 状态 |
| --- | --- |
| 启动、界面、主题、语言切换 | 可用（默认简体中文） |
| 触摸 | 可用（Novatek `nvt_36xxx`，开机由第一阶段 init 加载） |
| 背光、RAM、存储显示 | 已修（读设备树属性 / `sysinfo()` / `BLKGETSIZE64`） |
| 解密 | 进行中：密钥链受 SELinux 限制，逐条绕过后仍在验证 |
| Wi-Fi、振动、备份、双系统、OTA | 未验证 |

## 设备事实（实测）

- TB322FC / 社区代号 elden，SoC sun（SM8750P），ZUXOS `TB322FC_CN_OPEN_USER_Q00041.1_A17_ZUXOS_2.5.02.086_DEV_261010`（Android 17）
- 内核 **6.6.139**（原厂；recovery 没有自己的内核，恢复模式用的就是 `boot` 里的这个）
- 屏幕 1904×3040 / 440 dpi / 8.8 寸；虚拟 A/B；`recovery` 分区 100 MiB，`recovery_b` 为空
- bootloader locked/green，但实测接受 **AOSP testkey** 签名（`rollback_index` 必须 ≥ 1，0 会被拒）
- `ro.build.type=user`、`ro.debuggable=0`：init 的 `ALLOW_PERMISSIVE_SELINUX` 为 0，`androidboot.selinux=permissive` 被忽略；内核 `CONFIG_SECURITY_SELINUX_BOOTPARAM` 未开

## 仓库内容

```
devices/elden.toml        # Skyward 设备配置（显示、模块、固件分区、WLAN、备份/擦除）
devices/elden.modules.rc  # 追加给 init 的 rc：早启动开 firmware 回退、按属性 insmod
firmware/                 # 4 个 Novatek 触摸固件，打进 ramdisk 的 /lib/firmware
tools/avbtool.py          # AOSP avbtool（重签名用）
tools/testkey_rsa4096.pem # AOSP 公开测试密钥
tools/sign_image.py       # 把 skyward-pack 的无签名 footer 换成 testkey 签名（rollback 1）
tools/check_image.py      # 校验镜像尺寸/头部/rollback
tools/patch_cmdline.py    # 往镜像 cmdline 追加参数
.github/workflows/build.yml
```

## 上游分支上的改动（`elden`，共 19 个提交）

- **显示/模块**：读面板自身的亮度属性（`qcom,mdss-brightness-max-level` 等，读不到退回全量程）；`system_dlkm` 两种布局；模块依赖跨目录查找
- **文件与信息**：可写路径从 `/skyward/...` 挪到 `/tmp/skyward/...`；语言优先 `ro.product.locale.language`+`region`；RAM 用 `sysinfo()`、存储用 `BLKGETSIZE64`
- **SELinux 容错**（这台机器 `recovery` 域限制很多）：uevent socket、`/dev` 遍历与 chown、`/proc/meminfo`、`/mem_sleep`、固件回退写、`ro.*` 属性、执行 vendor 脚本、VINTF 描述准备、逐服务启动
- **诊断留痕**：`trace.rs` 把启动阶段写到两个 recovery 分区 64 MiB 处，每次启动先清零

## 构建

CI（`Build Skyward for elden`）在 ubuntu-24.04 上：

1. checkout 本仓库
2. 从 `lemonsn/skyward` 取固定 commit（`SKYWARD_COMMIT`）
3. 复制 `devices/elden.toml`
4. Rust 1.100（`rust-toolchain.toml`）+ NDK r29 + cargo-ndk 4.1.2
5. 构建 `skyward`（aarch64-linux-android）、静态 `system-init`、宿主 `skyward-pack`
6. 下载原厂 recovery（release 资产 `stock-elden/recovery.img`，校验 sha256）
7. 打包：`skyward-pack recovery --stock ... --config ... --init-rc devices/elden.modules.rc --firmware-dir firmware`
8. `patch_cmdline.py` 追加 `androidboot.selinux=permissive`（本机忽略，保留兼容）
9. `sign_image.py` 用 testkey 以 `rollback_index=1` 重签，`avbtool verify_image` 校验
10. 校验尺寸/头部，上传 artifact `skyward-elden`

## 刷入与回滚

```sh
unzip skyward-elden.img.zip
adb push skyward-elden.img /data/local/tmp/
adb shell su -c 'dd if=/data/local/tmp/skyward-elden.img of=/dev/block/by-name/recovery_a bs=4M'
# 或在 recovery 里直接 dd；BL 允许时也可 fastboot flash recovery_a skyward-elden.img
```

回滚用任意一份可启动的 recovery 写回 `recovery_a`：用户自签的原厂镜像（sha256 `30763f4e…`）、TWRP 产物，或 release 资产里的原厂镜像。

## 诊断留痕

镜像内 `trace.rs` 把启动阶段写进 `recovery_a`/`recovery_b` 的 **64 MiB** 处（镜像本体之外的空白区，AVB 不覆盖）。重启回 Android 后读取：

```sh
dd if=/dev/block/by-name/recovery_b bs=4096 skip=16384 count=16 | tr -d '\0'
# 想清掉：dd if=/dev/zero of=/dev/block/by-name/recovery_b bs=4096 count=16
```

最后一行是最远走到的阶段；`failed: ...` 是失败原因，`... is not started: ...` 是某个密钥程序被拒的原因。

## 已知限制

- 这台机器是 user 构建，**无法把 recovery 域切到 permissive**（无 `CAP_MAC_ADMIN`），只能逐条绕开被拒的接口
- 想靠内核配置解决固件加载（`CONFIG_FW_LOADER_USER_HELPER_FALLBACK`）需要重编并刷 `boot`，且必须与整套原厂 6.6 厂商模块的 KMI 匹配；当前用「固件进 ramdisk + init 写 `force_sysfs_fallback`」等价替代
- 不要刷 `boot`/`init_boot`/`vendor_boot`，只刷 `recovery`

## 许可

设备配置与工具脚本沿用上游的 **GPL-3.0-or-later**；`tools/avbtool.py` 来自 AOSP（Apache-2.0），`tools/testkey_rsa4096.pem` 是 AOSP 公开测试密钥。
