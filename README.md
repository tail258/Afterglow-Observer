# Afterglow Observer

轻量级的本地 Obsidian 笔记足迹可视化工具，基于 Python 和 Tkinter，结合 Git 历史与文件时间展示年度活跃热力图。支持每日笔记回顾、笔记本筛选、写作统计和四套配色。离线运行、严格只读，无需数据库或后台监控。

## 启动

克隆仓库后，双击 **启动.cmd**，在窗口中选择自己的笔记目录。关闭窗口即退出，没有后台服务。

也可以在 PowerShell 7 中运行：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\启动.ps1
```

需要 Python 3.11+（含 Tkinter）和 Git，不需要 pip 安装任何依赖。

可选：在项目目录创建 **settings.local.json**，设置 `vault` 为本机笔记目录，启动时自动读取。该文件被 Git 忽略，自动同步也拒绝上传它。界面选择目录只影响本次会话，不写入配置文件。

## 使用

- 左侧选择笔记本或任意子文件夹；搜索框用于查找文件夹。
- 顶部切换年份，点击热力图日期，查看笔记、创建／修改／删除操作和来源。
- 热力图获得焦点后，上下方向键移动一天，左右方向键移动一周。
- 当天路径搜索支持笔记标题、文件夹、旧名称；选中笔记可查看完整路径和提交短编号。
- “重新读取”获取最新文件时间和本地 Git 历史。工具不会自行同步或监控目录。
- 内置四套配色：靛蓝 · TPAMI、浅滩 · 海盐、海雾 · 子守歌、暗夜 · 绯红。切换只改变各部分颜色，不改变布局或统计。浅色背景、文字色和空白格使用适合阅读的衍生颜色。

## 数据口径

1. **分界点**是当前 HEAD 可达历史中的根提交的提交者时间。如存在多个根提交，取最早时间。
2. **Git 之前**，读取现存 Markdown 的创建时间和最后修改时间，分别只采用严格早于分界点的时间点。比较精确到时间戳，分界当天较早的时间也可以计入。Windows 使用创建时间；其他系统只有提供 birthtime 才使用创建时间，绝不将 POSIX ctime 当创建时间。
3. **Git 历史**包含当前 HEAD 可达的各分支提交，按作者时间统一换算为 **Asia/Shanghai（UTC+8）** 自然日。首次提交的新增文件也会计入创建。没有合并进 HEAD 的其他分支、远端引用及不可达旧提交不计入。
4. **合并**使用 Git combined diff：普通同步合并不再次计算父分支的活动；相对所有父提交均发生改变的文件记入合并日。Git combined diff 是文件级记录，不能精确区分文件内部的每一次冲突解决。
5. **每天去重**，同一笔记当天多个提交、多种操作、两个来源，只计一次。详情保留全部操作类型。
6. **重命名**使用 Git `-M` 默认相似度识别，识别成功的路径共用身份；跨文件夹移动也如此。没有被 Git 识别的重命名按删除／创建处理。复制是新笔记；同一路径删除后重建视为同一笔记。统计不读取笔记内容或 Obsidian ID。
7. **文件夹筛选**按活动发生时的路径，包含子文件夹；移动当天旧、新文件夹均可查看该笔记，不将旧活动追溯移动到新文件夹。
8. **四项年度统计**：活跃天数、涉及的不同笔记数、笔记日数（每日数量之和）、最长连续活跃天数。左侧当前文件数是现存 Markdown 数，可能包含未跟踪文件，和历史笔记数不必相等。
9. **热力图**周一开始，四档颜色按当前年份和文件夹范围的正活动数分位划分。悬停底部显示精确数量，空白日期可点击。闰年自动支持。
10. 忽略 `.git`、`.obsidian`、`.trash`、`node_modules` 内的文件。文件时间扫描跳过文件／目录链接、Windows 目录联接。

文件时间只能提供两个可用时间点，无法恢复提交之前每天的修改。同步／复制可能重置时间；已删除且未纳入 Git 的笔记也无法还原。Git 存在时，截止点之后的未提交修改、创建、删除均不计入足迹。

浅克隆缺少完整历史时显示错误，不会误用文件时间补算。无仓库或仓库未产生提交时，仅显示可用文件时间；程序不处理并列的多个独立仓库，可以分别选择打开。

## 只读与体量

仅调用 `git rev-parse`、`git rev-list`、`git log`，关闭 optional locks 和 fsmonitor，禁止外部 diff、textconv。不调用 `status`、`add`、`checkout`、`fetch`，不读取 Markdown 正文，不写笔记或仓库。

可视化程序没有数据库、网络请求、后台监控、运行时第三方依赖或数据缓存。筛选和配色都在内存中完成。读取任务放在工作线程，关闭程序即结束。Python 启动脚本也关闭 `.pyc` 写入。可选本地配置仅保存笔记目录，程序只读取该配置。

下面的源码同步是独立、可选的开发工具，不属于笔记可视化程序，也不访问笔记仓库。

## 两台 Windows 设备同步开发源码

每台设备分别克隆项目、登录 GitHub，再运行一次安装脚本：

```powershell
git clone https://github.com/tail258/Afterglow-Observer.git
cd Afterglow-Observer
gh auth login
pwsh -NoProfile -ExecutionPolicy Bypass -File .\启用自动同步.ps1
```

需要 GitHub CLI（`gh`）或其他已配置好的 Git 登录方式。安装脚本使用当前用户的 Python 和 Git 凭据，仅创建本项目的 Windows 计划任务。默认登录时运行，并每 5 分钟运行一次；不需要打开 Codex 或可视化窗口。任务仅在该 Windows 用户登录时运行，离线失败会在下一次运行时重试。

同步顺序：保存已跟踪源码的改动与删除 → 获取远端 → 快进或对本地未推送提交 rebase → 普通 push。没有改动时不生成提交，不创建备份、标签或发布版本，不使用强制推送。双机同时修改同一处代码发生冲突时，退出 rebase 并保留本地提交，停止本次同步，待手动合并；不覆盖任何一方代码。

**只同步公开源码。** 未跟踪的新文件不会自动添加；新模块请先自行检查，再使用 `git add`。随后脚本仍会检查文件类型和内容。允许程序源码、Python 测试、启动／同步脚本、README 和仓库配置；拒绝其他 Markdown、笔记、截图、临时文件、本地配置、链接、子模块、疑似凭据、个人用户主目录和已配置的本地笔记路径。每个将推送的提交都检查，避免秘密被删除后仍通过提交历史泄漏。它是误提交保护措施，新增源码或文档仍需由开发者确认不含个人信息。

手动同步、检查和停用：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\同步.ps1
py -3 -B sync.py --audit
Get-Content .git\afterglow-sync-status.json -Encoding utf8
pwsh -NoProfile -ExecutionPolicy Bypass -File .\停用自动同步.ps1
```

仅保留 `.git/afterglow-sync-status.json` 中的最新同步结果，不上传该文件。正常的 Git 提交是双机同步的基础，不另外保留历史快照。

实现依据：[Windows 任务触发器](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger)、[Git rebase](https://git-scm.com/docs/git-rebase) 和 [Git merge](https://git-scm.com/docs/git-merge)。

## 命令行核对

```powershell
py -3 -B app.py --summary --vault '你的笔记目录'
py -3 -B app.py --summary --vault '你的笔记目录' --year 2026 --folder '某个笔记本'
py -3 -B app.py --vault '你的笔记目录'
py -3 -B -m unittest discover -s tests -v
```

`--summary` 仅输出统计 JSON，不生成文件。测试在系统临时目录创建自己的 Git 仓库，不操作真实笔记。
