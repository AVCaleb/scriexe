<div align="center">

# scriexe

### 深入阅读。立足上下文。保持专注。

一个键盘优先的 Bible（圣经）研读 TUI，用于沉浸式 Scripture（经文）阅读、原文研究与个人释经。

[![npm](https://img.shields.io/npm/v/scriexe?color=cb3837&label=npm)](https://www.npmjs.com/package/scriexe)
[![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-64748b)](#平台支持)
[![Release](https://github.com/AVCaleb/scriexe/actions/workflows/release-scriexe.yml/badge.svg)](https://github.com/AVCaleb/scriexe/actions/workflows/release-scriexe.yml)

[English](README.md) | **中文**

```bash
npm install -g scriexe
scriexe
```

</div>

---

## 为什么需要 scriexe？

严肃的圣经研读往往分散在译本网站、词典、搜索工具、笔记文件和大量浏览器标签页中。每次切换都会打断阅读上下文：经文离开视线，观察散落各处，释经工作也逐渐脱离最初引发思考的文本。

**scriexe 把这套流程重新集中到一个专注的终端工作区。** 你可以从书卷自然进入章节、经节和原文词汇；在不离开当前经文的情况下比较译本；查看词形和出现位置；搜索本地语料；记录笔记；设置书签；并随时回到原来的阅读位置。

scriexe 并不追求把尽可能多的信息塞满屏幕。它把恰当的信息放在经文附近，使阅读、观察、词汇研究和笔记始终属于同一条连续的研读路径。

## 一个工作区，一条连续的研读流程

- **上下文阅读** — 常见研读工具把经文导航、译本比较和上下文拆散在不同页面或标签中，用户需要反复寻找原来的位置。scriexe 把四级导航器、平行译本和可调整阅读范围放在一起，使经文始终可见。

- **原文研究** — 普通词典查询会把用户带离经节，之后还要自行恢复上下文。scriexe 可以从经节直接进入希腊文或希伯来文词汇，在同一阅读路径中显示 lemma、Strong’s 编号、词形分析和语料出现位置，并保留返回原处的书签。WLC 希伯来文正文按窗格右边缘对齐。

- **本地研读笔记** — 当观察散落在无关文档中，笔记与经文之间的联系会逐渐消失。scriexe 把纯 Markdown 笔记直接绑定到经节或词汇出现位置，标记已经研读的经文，并让笔记保持可移植、可搜索且完全由用户掌控。

- **键盘优先** — 频繁移动鼠标和切换窗口会打断细读节奏。scriexe 把导航、范围切换、搜索、笔记、书签和出现位置跳转都放在键盘上；支持 Unicode 终端宽度的换行，使多语言经文保持清晰对齐。

## 安装内容

基础安装开箱即用，内置两个公版译本，不需要 Python，也不要求首次启动时下载：

| 离线内置 | 用途 |
| --- | --- |
| CUVS / 简体和合本 | 中文阅读和平行对照 |
| ASV (1901) | 高度直译的英文译本，其传承后来由 NASB/NASB95 延续；对措辞和句法结构的重视，使它特别适合与 CUVS 并排进行细致研读。 |

首次设置时可以选择 **“下载全部可选研经数据”**。此操作也一直保留在设置页；下载中断后可以重试，已经完成的数据不会被丢弃。

| 可选公共数据 | 新增功能 |
| --- | --- |
| SBLGNT | 希腊文新约词形、lemma 和词法分析 |
| WLC | 希伯来文旧约词形、lemma 和词法分析 |
| Strong’s 词典 | Strong’s 查询和词汇关联 |
| WEB 和 KJV | 更多英文对照文本 |
| Vulgate | 拉丁文对照文本 |

ESV 和 NASB95 不会随 scriexe 再分发。只有在支持的情况下，用户才能通过自己的 API Key 或本地导入副本使用它们。用户授权的译本保存在安装包之外，绝不会进入发布产物。

## 快速开始

### 1. 安装

安装需要 Node.js 18 或更高版本，不需要 Python。

```bash
npm install -g scriexe
```

npm 会根据操作系统和 CPU 架构选择对应的原生包。macOS、Linux 和 Windows 使用相同命令：

```bash
scriexe
```

### 2. 完成首次设置

首次启动时选择界面语言和默认显示译本。你可以直接使用 CUVS 与 ASV，也可以先下载完整的公共研经数据再进入工作区。

API Key 完全可选，也可以稍后从设置页添加，不影响离线阅读。

### 3. 开始阅读

TUI 会直接打开阅读工作区。一次典型研读可以完全留在 scriexe 内：

1. 打开导航器并选择经文。
2. 选择窗口、章节或单节阅读范围。
3. 比较当前显示的译本。
4. 安装研经资料后，进入希腊文或希伯来文词汇。
5. 跟随出现位置，同时用书签保留原处。
6. 在经节或词汇旁记录观察。
7. 搜索并返回先前内容，而不离开工作区。

## 常用按键

| 场景 | 按键 | 操作 |
| --- | --- | --- |
| 常规界面 | `Tab` | 打开或关闭导航器 |
| 导航器 | `j` / `k` | 移动选项 |
| 导航器 | `h` / `l` | 返回上一列或进入下一列 |
| 导航器 | `Enter` | 打开所选经节或词汇 |
| 经文 | `j` / `k` | 在经节之间移动 |
| 经文 | `z` | 循环切换窗口、章节和单节范围 |
| 经文 | `+` / `-` | 调整上下文窗口 |
| 经文 | `p` / `b` | 设置并返回书签 |
| 经文 | `i` | 编辑笔记 |
| 经文 | `/` | 查找当前经文预览 |
| 查找激活 | `j` / `k` | 上一个或下一个匹配 |
| 查找激活 | `Enter` / `Esc` | 接受当前位置或清除查找 |
| 经文 | `o` | 打开设置 |
| 词汇/结果 | `Enter` | 跳到所选出现位置 |
| 常规界面 | `?` | 打开帮助 |

## 命令行工具

交互式工作区是主要使用方式；同一个安装包也提供适合脚本和快速查询的一次性命令：

```bash
# 使用指定译本显示经文
scriexe passage "1Pet 3:18-22" --versions cuvs,asv

# 搜索本地语料
scriexe search "living hope"

# 安装研经数据后查询 Strong’s 编号或 lemma
scriexe word G3958

# 下载或更新公共数据
scriexe fetch

# 导入用户提供的译本
scriexe import ./translation.usfm --version mytranslation

# 生成双语 Markdown 研读文件
scriexe scaffold "1Pet 3:18-22"
```

经文相关命令同时接受英文和中文经文格式。

## 本地优先设计

scriexe 把已安装程序与个人工作区分开。内置资源保持只读；笔记、设置、API Key、导入内容、缓存和下载数据写入用户数据目录：

| 平台 | 用户数据位置 |
| --- | --- |
| macOS | `~/Library/Application Support/scriexe` |
| Linux | `$XDG_DATA_HOME/scriexe` 或 `~/.local/share/scriexe` |
| Windows | `%LOCALAPPDATA%\scriexe` |

研读导出和 scaffold 生成的 Markdown 文件位于上述用户数据目录的 `studies` 子目录。每次成功导出都会显示完整绝对路径，用户无需猜测文件去了哪里。

下载或导入的语料会优先于内置后备文本，而不会修改 npm 安装目录。这样升级与个人资料彼此分离，安装损坏时也更容易重新安装。

发布包不包含 `.env`、笔记、研读文件、缓存、下载源文件或导入译本。只有用户主动请求下载或使用已经配置的在线译本 API 时才会访问网络。

## 规划中的 AI 辅助释经

AI 辅助已经列入路线图，但不会被描述为阅读或判断的替代品。

规划方向是一个能理解当前经文、邻近上下文、原文资料和用户个人笔记的助手。它可以帮助整理观察、提出值得进一步研究的问题、比较已有材料，并指出论证中需要更紧密文本支持的位置。

边界同样重要：生成建议必须与圣经文本及用户自己的结论明确区分。解释责任仍属于用户；AI 应当帮助组织谨慎研读，而不是让释经权威消失在生成答案背后。

## 平台支持

npm 启动器会安装一个匹配平台的原生构建：

- macOS — Apple Silicon 和 Intel
- Linux — ARM64 和 x64
- Windows — x64

如果安装时禁用了 npm optional dependencies，原生包将不会安装。当 scriexe 提示缺少平台包时，请启用 optional dependencies 后重新安装。

## 项目状态

scriexe 仍处于早期版本。核心阅读、导航、搜索、笔记、词汇研究和导入流程已经实现并经过测试；随着更多终端和操作系统的实际使用，打包与界面细节仍会继续完善。

项目刻意选择小而清晰的本地工作区，而不是账号、同步服务或隐藏的后台进程。

## 开发

克隆仓库并准备本地 Python 环境：

```bash
git clone https://github.com/AVCaleb/scriexe.git
cd scriexe
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/exeg fetch
.venv/bin/pytest -q
.venv/bin/exeg
```

运行 JavaScript 启动器测试：

```bash
node --test npm/scriexe/test/*.test.js
```

构建本地独立目录：

```bash
.venv/bin/pip install -e '.[distribution]'
.venv/bin/exeg fetch --only ebible --versions cuvs,asv
.venv/bin/python packaging/build_core_data.py --output build/core
.venv/bin/pyinstaller --clean --noconfirm packaging/scriexe.spec
```

## 数据与署名

CUVS 和 ASV 来自 [eBible.org](https://ebible.org/) 提供的公版发行文件。每个原生包都包含署名文件；可选数据集保留各自上游来源信息。

授权译本仍受提供方条款约束，本项目不会再分发这些文本。

## 参与贡献

欢迎通过 GitHub Issues 提交错误报告、终端兼容性报告、文档改进和范围明确的功能建议。报告显示问题时，请附上操作系统、终端程序、终端宽度，并尽可能提供截图。

---

<div align="center">

**用更安静的界面，进行更深入的阅读。**

[安装](#快速开始) · [功能](#一个工作区一条连续的研读流程) · [隐私](#本地优先设计) · [路线图](#规划中的-ai-辅助释经)

</div>
