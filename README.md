<div align="center">

# Afterglow Observer

**把写过的日子，重新看见。**

一个本地运行的 Obsidian 笔记足迹查看器。<br>
从 Git 历史与文件时间中，拼出属于你的年度写作热力图。

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-6C5B8F?style=flat-square&logo=python&logoColor=white) ![Tkinter](https://img.shields.io/badge/UI-Tkinter-9873A8?style=flat-square) ![Offline](https://img.shields.io/badge/Offline-Local-C77C83?style=flat-square) ![Read only](https://img.shields.io/badge/Notes-Read_Only-D99A76?style=flat-square)

[快速开始](#快速开始) · [日常使用](#日常使用) · [三套配色](#三套配色) · [统计口径](#统计口径)

</div>

---

## 看见写作的积累

哪些日子写过笔记，哪些主题反复打磨，哪一段时间最投入——Afterglow Observer 把这些记录放在同一个窗口里。选择一个年份、一份笔记本，或热力图上的某一天，就能从全年概览走到当天的具体笔记。

它是一款基于 **Python + Tkinter** 的独立桌面应用。数据在本机按需读取，筛选与配色在内存中完成；关闭窗口，程序即退出。

| 功能 | 你能看到什么 |
| --- | --- |
| **年度热力图** | 每天涉及的不同笔记数，点击日期查看详情 |
| **笔记本筛选** | 浏览或搜索文件夹，统计范围包含其子文件夹 |
| **当天回顾** | 笔记名称、创建／修改／删除操作、数据来源与历史路径 |
| **四项年度统计** | 活跃天数、涉及笔记、笔记日数、最长连续活跃天数 |
| **主题与交互** | 三套配色、细圆角滚动条、键盘日期导航 |
| **桌面入口** | 透明背景的晚霞渐变水晶图标，可创建桌面快捷方式 |

## 快速开始

### 1. 准备环境

Windows 启动脚本需要 **Python 3.11 或更高版本（含 Tkinter）** 和 **Git**。应用使用 Python 标准库，运行前无需安装 pip 依赖。

### 2. 下载并启动

```powershell
git clone https://github.com/tail258/Afterglow-Observer.git
cd Afterglow-Observer
.\启动.cmd
```

也可以直接双击项目文件夹里的 **`启动.cmd`**。

### 3. 选择笔记目录

点击窗口中的 **“选择笔记目录…”**，选择你的 Obsidian 笔记库。程序读取文件时间与当前 Git 历史，随后展示年度足迹。

**没有 Git 历史的笔记库也可以使用**：此时展示现存 Markdown 文件可用的创建和最后修改时间。

<details>
<summary><strong>桌面快捷方式与默认笔记目录</strong></summary>

#### 创建桌面快捷方式

在项目目录运行一次：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\创建快捷方式.ps1
```

桌面会出现 **Afterglow Observer** 快捷方式，使用 `pythonw.exe` 启动，带有晚霞水晶图标，打开时不弹出命令行窗口。图标包含 16、32、48、64、128、256 像素六种尺寸。

生成的 `afterglow.local.ico` 和桌面快捷方式只保存在本机，受 Git 忽略规则保护。

#### 设置默认笔记目录

在项目目录创建 `settings.local.json`：

```json
{
  "vault": "D:/Notes/Obsidian"
}
```

将示例路径替换为自己的笔记目录，下次启动会自动读取。该配置受 Git 忽略规则和源码同步检查保护。界面中选择目录仅用于当前会话。

#### PowerShell 7 启动

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\启动.ps1
```

</details>

## 日常使用

1. **选范围**：在左侧选择笔记本或子文件夹，用搜索框快速定位。
2. **选年份**：从顶部年份列表切换，查看这一年的写作分布。
3. **看一天**：点击热力图日期，查看当天笔记、操作、来源和所在文件夹。
4. **找笔记**：搜索标题、文件夹或旧名称；选中结果查看完整路径和提交短编号。
5. **更新数据**：点击 **“重新读取”**，获取最新文件时间与本地 Git 历史。

| 操作 | 方式 |
| --- | --- |
| 移动到相邻日期 | 热力图获得焦点后，按 `↑` / `↓` |
| 移动到相邻一周 | 热力图获得焦点后，按 `←` / `→` |
| 查看当天数量 | 将鼠标悬停在日期上，底部显示精确数量 |
| 滚动列表 | 拖动圆角滑块、点击轨道，或使用鼠标滚轮 |
| 横向滚动当天列表 | 按住 `Shift` 使用鼠标滚轮 |
| 键盘滚动 | 滚动条获得焦点后，使用方向键、`Page Up` / `Page Down`、`Home` / `End` |

## 三套配色

| 主题 | 色彩印象 | 色值预览 |
| --- | --- | --- |
| **靛蓝 · TPAMI** | 浅底色与沉静的靛蓝 | `#33395B` · `#5D74A2` · `#4A59B2` · `#5A5E8C` |
| **浅滩 · 海盐** | 沙色、海盐绿与深青 | `#E4D2C5` · `#E1C7BA` · `#90BAAB` · `#488883` · `#245053` |
| **海雾 · 子守歌** | 雾蓝、石灰与柔和的灰紫 | `#404E5B` · `#677B8F` · `#8FA0B8` · `#948F8C` · `#CCC9C6` |

主题同步调整文字、面板、热力图和滚动条颜色，保留当前统计范围与布局。列表没有溢出时，滚动滑块自动隐藏。

## 统计口径

**一格代表一天，数量代表当天涉及的不同笔记数。** 同一篇笔记当天发生多次提交或多种操作，热力图只计一次；详情保留其操作类型。

| 指标 | 含义 |
| --- | --- |
| **活跃天数** | 当前年份与文件夹范围内，有笔记活动的天数 |
| **涉及笔记** | 当前范围内参与活动的不同笔记数 |
| **笔记日数** | 每天不同笔记数之和；同一篇笔记在两天活动，计为两个笔记日 |
| **最长连续** | 连续出现笔记活动的最长天数 |

日期统一按 **Asia/Shanghai（UTC+8）** 计算。热力图从周一开始，四档颜色按当前范围内的正活动数分位划分。

<details>
<summary><strong>展开：时间来源、Git 历史与重命名规则</strong></summary>

#### 两种时间来源

- **分界点**：当前 `HEAD` 可达历史中，根提交的提交者时间；有多个根提交时，取最早时间。
- **分界点之前**：采用现存 Markdown 文件的创建时间和最后修改时间，仅计入严格早于分界点的时间戳。分界当天较早的记录也可计入。
- **分界点之后**：采用当前 `HEAD` 可达的 Git 历史，按提交作者时间归入自然日。首次提交的新增文件计入创建活动。
- **没有仓库或尚无提交**：仅展示可用文件时间。Windows 使用创建时间；其他系统仅在提供 `birthtime` 时采用创建时间，不以 POSIX `ctime` 代替。

文件时间提供创建与最后修改两个时间点；此前每天的修改记录需要 Git 历史。复制或同步可能改变文件时间，已删除且未纳入 Git 的笔记没有可恢复的活动记录。已有 Git 历史时，分界点之后的未提交创建、修改和删除不计入足迹。

#### 历史与笔记身份

- **历史范围**：包括已经合入当前 `HEAD` 的各分支提交。未合入的分支、远端引用和不可达旧提交不计入。
- **合并提交**：使用 Git combined diff。普通同步合并不会再次计入父分支活动；相对所有父提交都发生变化的文件计入合并日。记录为文件级粒度，不能区分文件内每次冲突解决。
- **重命名与移动**：使用 Git `-M` 的默认相似度识别；识别成功的路径共用笔记身份。未识别的重命名按删除与创建处理。
- **复制与重建**：复制视为新笔记；同一路径删除后重建视为同一笔记。身份判断基于路径历史，不读取正文或 Obsidian ID。
- **文件夹归属**：按活动发生时的路径筛选，包含子文件夹。移动当天，在旧、新文件夹中均可查看该笔记；此前活动仍归属当时的文件夹。

#### 扫描范围

扫描跳过 `.git`、`.obsidian`、`.trash`、`node_modules`，以及文件／目录链接和 Windows 目录联接。

左侧“当前范围”统计现存 Markdown 文件，可能包含未跟踪文件，因此与历史涉及笔记数不同。浅克隆因缺少完整历史会显示错误，不以文件时间补算。多个独立笔记仓库可分别选择打开。空白日期也可点击，闰年自动支持。

</details>

## 本地运行与隐私

| 项目 | 应用行为 |
| --- | --- |
| **读取内容** | 文件路径、创建／修改时间、Git 历史元数据；不读取 Markdown 正文 |
| **笔记访问** | 只读；笔记文件与笔记仓库保持原样 |
| **网络与存储** | 离线运行；无数据库、持久数据缓存或运行时第三方依赖 |
| **任务生命周期** | 按需在工作线程读取；关闭窗口即退出，无后台监控 |
| **Git 调用** | 仅使用 `rev-parse`、`rev-list`、`log`；关闭 optional locks、fsmonitor、外部 diff 与 textconv |

启动脚本关闭 `.pyc` 写入。默认目录配置仅在本机读取；图标和快捷方式仅在主动运行安装脚本时生成。

## 命令行与开发

输出统计 JSON，或指定目录启动界面：

```powershell
py -3 -B app.py --summary --vault '你的笔记目录'
py -3 -B app.py --summary --vault '你的笔记目录' --year 2026 --folder '某个笔记本'
py -3 -B app.py --vault '你的笔记目录'
```

运行测试：

```powershell
py -3 -B -m unittest discover -s tests -v
```

统计命令向终端输出 JSON，不生成文件。历史与同步测试使用临时 Git 仓库，界面测试使用合成数据；界面测试需要 Tk 图形环境。

<details>
<summary><strong>可选：两台 Windows 设备自动同步开发源码</strong></summary>

源码同步是独立的开发工具，仅处理本项目的公开源码。运行可视化应用无需启用它。

#### 启用

每台设备克隆项目后，在项目目录执行：

```powershell
gh auth login
pwsh -NoProfile -ExecutionPolicy Bypass -File .\启用自动同步.ps1
```

需安装 GitHub CLI（`gh`），或准备其他可用的 Git 登录方式。脚本创建当前用户的 Windows 计划任务，默认在登录时和每 5 分钟运行一次。任务仅在该用户登录期间执行，离线失败会在下一次运行时重试。

#### 同步顺序

保存已跟踪源码的修改与删除 → 获取远端 → 快进或 rebase 本地未推送提交 → 普通 push。

没有改动时不生成提交。双机修改冲突时，脚本退出 rebase、恢复本地提交并停止本次同步，等待手动合并。同步以正常 Git 提交为基础，不创建额外备份、标签或历史快照，不使用强制推送。

#### 上传范围

同步检查允许程序源码、Python 测试、启动／快捷方式／同步脚本、README 和仓库配置。笔记、截图、临时文件、本地配置、链接、子模块、疑似凭据、个人主目录和已配置的笔记路径会被拒绝。

新文件须先检查，再显式 `git add`；未跟踪文件不会自动添加。脚本检查每个待推送提交的文件与内容，以防敏感信息通过提交历史上传。使用 GitHub CLI 启用同步时，新配置的提交邮箱采用 GitHub 隐私邮箱；已有 Git 身份请自行核对。

#### 手动同步、检查与停用

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\同步.ps1
py -3 -B sync.py --audit
Get-Content .git\afterglow-sync-status.json -Encoding utf8
pwsh -NoProfile -ExecutionPolicy Bypass -File .\停用自动同步.ps1
```

仅保留 `.git/afterglow-sync-status.json` 中的最新同步结果，该文件不上传。

实现参考：[Windows 任务触发器](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger) · [Git rebase](https://git-scm.com/docs/git-rebase) · [Git merge](https://git-scm.com/docs/git-merge)。

</details>

---

<p align="center"><strong>Afterglow Observer</strong><br>写作留下足迹，余晖照见积累。</p>
