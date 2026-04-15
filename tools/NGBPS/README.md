# GKI Kernel Build & Patch Development Script

这是一套用于自动化构建 **GKI（通用内核映像）** 内核并进行补丁开发的工具链。它支持下载内核源码与工具链、应用模块化补丁（Mod）、管理编译环境，并提供开发模式用于生成和迭代内核补丁。
我希望开创新的内核补丁格式，并实现新的创意工坊标准

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
  - [1. 准备配置文件](#1-准备配置文件)
  - [2. 初始化工作区](#2-初始化工作区)
  - [3. 开始构建](#3-开始构建)
- [普通用户使用指南](#普通用户使用指南)
  - [配置文件说明](#配置文件说明)
    - [`kernel.json`](#kerneljson)
    - [`build.env`](#buildenv)
    - [`defconfig_append`](#defconfig_append)
  - [命令详解](#命令详解)
    - [`--init [--dev]`：初始化工作区](#--init---dev初始化工作区)
    - [`--build`：构建内核](#--build构建内核)
    - [`--clean`：清理工作区](#--clean清理工作区)
    - [`--download`：下载文件](#--download下载文件)
  - [构建产物](#构建产物)
- [内核补丁制作者教程](#内核补丁制作者教程)
  - [Mod 目录结构](#mod-目录结构)
  - [Mod 配置文件 (`config.json`)](#mod-配置文件-configjson)
  - [Mod 文件类型说明](#mod-文件类型说明)
    - [`patch.diff` / `patch.patch`](#patchdiff--patchpatch)
    - [`defconfig_append`](#defconfig_append-1)
    - [`setup.sh`（预构建脚本）](#setupsh预构建脚本)
    - [`post.sh`（后构建脚本）](#postsh后构建脚本)
  - [依赖管理与加载顺序](#依赖管理与加载顺序)
  - [补丁开发工作流](#补丁开发工作流)
    - [1. 在开发模式下初始化](#1-在开发模式下初始化)
    - [2. 修改内核源码](#2-修改内核源码)
    - [3. 生成补丁文件](#3-生成补丁文件)
    - [4. 组织为 Mod](#4-组织为-mod)
    - [5. 测试与迭代](#5-测试与迭代)
- [目录结构详解](#目录结构详解)
- [故障排除](#故障排除)
- [许可证](#许可证)

---

## 功能特性

- **自动化工具链下载**：自动拉取 Clang、Rust、build-tools 等编译器组件。
- **模块化补丁管理**：通过 JSON 配置的 Mod 系统，支持依赖解析与拓扑排序。
- **开发模式**：保留原始源码副本，便于生成补丁及迭代开发。
- **可重现构建**：集成 `libfaketime` 与 `libfakestat`，支持确定性时间戳。
- **AnyKernel3 打包**：构建完成后自动生成可直接刷入的 AnyKernel3 ZIP 包。
- **CCache 加速**：内置 CCache 配置，大幅提升重复构建速度。

---

## 环境要求

### 必需软件
- **Python 3.6+**
- **unzip** – 用于解压源码包
- **aria2c** 或 **curl** – 用于下载文件（优先使用 aria2c）
- **patch** – 用于应用补丁
- **zip** – 用于打包 AnyKernel3
- **GNU Make** 及其他标准编译工具链

### 推荐操作系统
- Linux（Debian / Ubuntu 测试通过）
- 其他类 Unix 系统可能需要调整部分路径

### 安装依赖示例（Debian/Ubuntu）
```bash
sudo apt update
sudo apt install python3 unzip aria2 patch zip make git ccache
```

---

## 快速开始

### 1. 准备配置文件

在脚本根目录下创建 `kernel.json`，填写内核源码 URL、版本信息及工具链 URL。  
示例：
```json
{
  "version": "6.12.23",
  "name": "MyGKI",
  "android_version": "android16-6.12",
  "source": "https://github.com/.../kernel_common-6.12.23.zip",
  "compiler": {
    "clang": "https://.../clang-r536225.zip",
    "rustc": "https://.../rust.zip",
    "build-tools": "https://.../build-tools.zip"
  },
  "anykernel3": "https://.../AnyKernel3.zip"
}
```
可选：创建 `build.env` 文件配置环境变量，`defconfig_append` 文件添加额外内核配置。

### 2. 初始化工作区

```bash
python3 kernelbuild.py --init
```
此命令会：
- 下载内核源码及所有编译器组件
- 解压到 `kernel_workspace/` 目录
- 自动应用 `mods/` 目录下所有兼容的 Mod
- 处理内核版本后缀及 `-dirty` 标记

### 3. 开始构建

```bash
python3 kernelbuild.py --build
```
构建完成后，会在脚本根目录生成 `anykernel3.zip`，可直接用于刷入设备。

---

## 普通用户使用指南

### 配置文件说明

#### `kernel.json`

| 字段 | 说明 |
|------|------|
| `version` | 内核版本号，用于 Mod 兼容性检查 |
| `name` | 内核名称，若未指定 `suffix` 则用作版本后缀 |
| `android_version` | Android 版本代号（供 Mod 脚本使用） |
| `source` | 内核源码 ZIP 包 URL（支持 `http://`、`https://`、`file://`） |
| `compiler` | 编译器组件的 URL 字典：`clang`、`rustc`、`build-tools` |
| `anykernel3` | AnyKernel3 模板 ZIP 包 URL |
| `suffix` | （可选）自定义内核版本后缀，例如 `-MyKernel` |

#### `build.env`

此文件用于设置构建环境变量，例如：
```bash
KSU=none #初始值 禁止修改
##下面都可以修改
KPM=builtin
BBR_DEFAULT=false
FAKESTAT="2025-05-25 12:00:00"
FAKETIME="@2025-05-25 13:00:00"
CCACHE_MAXSIZE="3G"
```
构建脚本会加载这些变量并传递给 `make`。

#### `defconfig_append`

如需添加额外的内核配置选项，请将配置项逐行写入此文件。构建时它们会被追加到 `gki_defconfig` 末尾。

### 命令详解

#### `--init [--dev]`：初始化工作区

- `--init`：标准初始化，删除旧工作区，下载源码并应用 Mod。
- `--init --dev`：**开发模式**初始化，额外保留一份 `common_original` 副本，用于后续生成补丁。

#### `--build`：构建内核

执行完整的构建流程：
1. 恢复 `gki_defconfig` 到官方 Mod 附加前的状态。
2. 追加用户自定义的 `defconfig_append`。
3. 设置编译环境（PATH、CC、LD、时间劫持等）。
4. 运行 `make gki_defconfig` 及 `make Image`。
5. 应用 `post.sh` 后处理 Mod。
6. 将生成的 `Image` 打包进 AnyKernel3 ZIP。

#### `--clean`：清理工作区

将 `common/` 目录恢复为 `common_original/` 的状态（仅在开发模式初始化后有效）。

#### `--download URL OUTPUT_PATH`

辅助功能，使用脚本内置的下载缓存机制下载任意文件。

### 构建产物

- **anykernel3.zip**：位于脚本根目录，可直接通过 TWRP 或 KernelSU / Magisk 管理器刷入。
- **中间文件**：全部位于 `kernel_workspace/` 下，包括 `common/out/` 编译输出。

---

## 内核补丁制作者教程

本工具的核心设计围绕 **Mod（模块）** 展开。每个 Mod 是一个独立的文件夹，包含补丁文件、配置脚本以及元数据，便于分发和维护。

### Mod 目录结构

Mod 应放置在 `mods/` 目录下（或通过 `mod_repo/` 管理）。推荐结构：
```
mods/
└── your_mod_name/
    ├── config.json        # 必需：元数据与依赖
    ├── patch.diff         # 可选：标准补丁文件
    ├── defconfig_append   # 可选：追加的内核配置
    ├── setup.sh           # 可选：预构建脚本
    └── post.sh            # 可选：后构建脚本
```

### Mod 配置文件 (`config.json`)

```json
{
  "name": "example_mod",
  "description": "An example kernel modification",
  "versions": ["6.12", "6.6"],
  "dependency": ["other_mod_name"],
  "type": "patch"
}
```

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | ✅ | 唯一标识符，用于依赖解析 |
| `description` | ❌ | 简短描述 |
| `versions` | ✅ | 支持的**内核版本前缀**列表，例如 `"6.12"` 可匹配 `6.12.23` |
| `dependency` | ❌ | 字符串数组，声明对其他 Mod 的依赖关系 |
| `type` | ❌ | 保留字段，当前忽略 |

### Mod 文件类型说明

#### `patch.diff`

标准的 `git diff` 格式补丁文件，应基于 `common/` 目录的根生成（即补丁内路径以 `a/`、`b/` 开头）。  
应用时会使用 `patch -p1` 在 `common/` 目录执行。

#### `defconfig_append`

内容会被直接追加到 `gki_defconfig` 末尾。适合添加新的配置项或覆写默认值。

#### `setup.sh`（预构建脚本）

在应用补丁**之前**执行。脚本运行于 `kernel_workspace/` 目录，可访问以下环境变量：
- `KERNEL_WORKSPACE`：工作区根目录
- `MOD_PATH`：当前 Mod 目录
- `ANDROID_VERSION`：来自 `kernel.json`
- `KERNEL_VERSION`：来自 `kernel.json`

常用于执行复杂的源码修改，例如复制额外文件、运行自定义脚本。

#### `post.sh`（后构建脚本）

在 `Image` 生成**之后**、打包 AnyKernel3 **之前**执行。额外提供：
- `IMAGE_PATH`：生成的 `Image` 文件路径
- `AK3_DIR`：AnyKernel3 模板目录

常用于修改 AnyKernel3 内容、添加模块文件等。

### 依赖管理与加载顺序

工具会解析所有 Mod 的 `dependency` 字段，执行**拓扑排序**以确定应用顺序。  
若存在循环依赖或依赖不存在的 Mod，构建过程将终止并报错。

### 补丁开发工作流

#### 1. 在开发模式下初始化

```bash
python3 kernelbuild.py --init --dev
```
此命令会额外保留 `kernel_workspace/common_original/` 作为干净源码快照。

#### 2. 修改内核源码

直接编辑 `kernel_workspace/common/` 下的文件，进行所需的内核修改。  
如需测试，可运行 `--build` 验证。

#### 3. 生成补丁文件

```bash
python3 kernelbuild.py --genpatch
```
此命令比较 `common_original/` 与 `common/` 的差异，并生成 `common_changes.patch`。  
生成的补丁已转换为 `git diff` 兼容格式（`a/`、`b/` 路径）。

#### 4. 组织为 Mod

- 在 `mods/` 下创建新文件夹（例如 `mods/my_feature/`）。
- 将生成的补丁重命名为 `patch.diff` 放入其中。
- 创建 `config.json`，填写名称、版本等信息。
- 如有额外配置追加，创建 `defconfig_append`。
- 如需复杂逻辑，编写 `setup.sh` 或 `post.sh`。

#### 5. 测试与迭代

- 运行 `--clean` 恢复源码到原始状态。
- 重新运行 `--build`，验证 Mod 是否能正确应用并编译通过。
- 若需修改补丁，重复步骤 2–4。

> **提示**：你可以使用 `--applypatch <patch_file>` 命令手动应用外部补丁进行测试。

---

## 目录结构详解

```
.
├── kernelbuild.py          # 主脚本
├── kernel.json             # 用户配置文件
├── build.env               # 环境变量（可选）
├── defconfig_append        # 用户自定义配置追加（可选）
├── lib/                    # 辅助库（faketime等）
├── mods/                   # 用户自定义 Mod 存放目录
├── mod_repo/               # 官方 Mod 仓库（按版本分类）
│   ├── 6.12/
│   └── generic/
├── kernels/                # 预设内核配置示例
├── cache/                  # 下载缓存目录
├── download_cache.json     # 下载缓存映射文件
└── kernel_workspace/       # 自动生成的工作区
    ├── build.env           # 合并后的环境变量
    ├── common/             # 内核源码
    ├── common_original/    # （仅开发模式）原始源码快照
    ├── clang/              # Clang 工具链
    ├── rust/               # Rust 工具链
    ├── build-tools/        # 构建辅助工具
    └── anykernel3/         # AnyKernel3 模板及生成的 Image
```

---

## 故障排除

### 1. 下载失败或网络问题
- 确保 `aria2c` 或 `curl` 已正确安装。
- 手动下载文件后可使用 `file://` 协议指定本地路径。

### 2. 编译错误：`pahole` 缺失
`pahole` 是 BTF 生成所需工具，安装 `dwarves` 包：
```bash
sudo apt install dwarves
```

### 3. 补丁应用失败
- 检查补丁是否基于相同的内核版本生成。
- 使用 `--clean` 恢复源码后重新应用补丁。
- 在 `setup.sh` 中应用复杂修改可绕过 `patch` 限制。

### 4. 依赖解析错误
- 确认所有被依赖的 Mod 名称在 `config.json` 中拼写正确。
- 检查是否存在循环依赖。

### 5. 时间劫持未生效
- 确保 `lib/` 目录下的 `.so` 文件具有可执行权限。
- 检查 `build.env` 中 `FAKESTAT` 和 `FAKETIME` 变量格式是否正确。

---

## 许可证

本脚本及相关文件遵循其原始发布者的许可条款。请根据您的使用场景自行确认。
