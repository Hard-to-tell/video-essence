# 精华 · Video Essence

B站、抖音和本地视频的内容提炼工具，同时提供本地界面与 Codex skill。输入链接或“帮我总结抖音最近稍后再看的3条视频”，读取正文、分段听写、判断价值，再给出要点和回看片段。

提炼优先还原作者的观点、推导和例子，开头提供一段完整总览（默认约200～350字，短视频按信息量缩短）；有争议的判断明确归属作者，必要限定集中放在简短备注。界面与 skill 共用 [提炼规则](app/summary_policy.txt)，修改后新任务会重新生成分段摘要；旧总结需重新提炼。提示词回归检查见 [评估标准](references/summary-evaluation.md)。

在总结库点击视频即可居中阅读精华与原文，也可铺满窗口。原文默认连贯分段，支持切换时间轴、搜索高亮；切换精华与原文时保留各自的阅读位置。

当前为 **Windows 优先的预览版**。已在原开发环境实测 B站链接、B站稍后再看、抖音完整链接和抖音稍后再看的端到端流程。平台接口可能变化；小批量也不保证永远不被限制。只处理自己有权访问的内容，接口拒绝即停止。

## 安装（Windows PowerShell）

准备 Python 3.10–3.12、Git、FFmpeg（含 ffprobe，加入 PATH）。界面自动提炼还需要 Node.js/npm 和已登录的 Codex CLI；聊天 skill 可直接让宿主助手阅读正文并总结。

```powershell
git clone https://github.com/Hard-to-tell/video-essence.git
cd video-essence
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('mobiuslabsgmbh/faster-whisper-large-v3-turbo', local_dir='models/large-v3-turbo')"
npm install --prefix vendor/codex-runtime @openai/codex@0.165.0
```

模型下载需要网络与数 GB 磁盘空间。通过 `vendor/codex-runtime/node_modules/.bin/codex.cmd login` 登录自己的 Codex 账号。模型调用消耗该账号额度，模型可用性取决于账号；默认 `gpt-6-astra`，可用环境变量 `VIDEO_ESSENCE_SUMMARY_MODEL` 改为自己有权限的模型。

```powershell
.\.venv\Scripts\python.exe doctor.py
.\launch.cmd
```

`launch.cmd` 用系统默认浏览器打开普通网页标签；也可以运行 `.\.venv\Scripts\python.exe app/server.py`，访问本机 8765 端口。CPU 可用但长视频较慢；GPU 需要与 CTranslate2 兼容的 NVIDIA CUDA/cuDNN 环境，失败会降级 CPU，本项目不自动改驱动。

在设置中完成 B站扫码登录，或导入抖音 Netscape 格式 Cookie 文件。也可将自己的文件分别保存为根目录 `cookies.txt` / `douyin-cookies.txt`。Cookie 相当于登录凭证，不要提交 Git、发到聊天或分享给其他人。仓库不包含账号、视频、听写稿或个人总结。

## 安装为 skill

将**整个仓库**克隆到 Codex 的 skills 目录，例如：

```powershell
git clone https://github.com/Hard-to-tell/video-essence.git "$env:USERPROFILE\.codex\skills\video-essence"
```

在该目录完成上述依赖安装，再开始新聊天。可以说 `$video-essence 总结这个视频：https://www.bilibili.com/video/BV.../`，也支持抖音完整视频链接和本地文件。不要只复制 SKILL.md：它依赖仓库中的处理脚本。若已安装到其他位置，可将整个目录移入 skills 目录后重新建立虚拟环境。

skill 默认直接在聊天里返回总结，不额外生成摘要文件。必要缓存放在安装目录的 `transcripts/`；Windows 界面任务和总结库固定保存在 `%LOCALAPPDATA%/VideoEssence/state.json`，更新或切换安装目录仍使用同一份记录。可用 `VIDEO_ESSENCE_DATA_DIR` 指定数据目录。首次启动会导入当前目录以及同级 `bili-summary`、`video-essence` 的旧 `data/state.json`，保留原文件。图形界面是可选入口，不是使用 skill 的前提。

## 配置与验证

默认使用当前 Python、PATH 中的 FFmpeg 和 `models/large-v3-turbo`。可选环境变量：`VIDEO_ESSENCE_PYTHON`、`VIDEO_ESSENCE_FFMPEG_DIR`（包含两个可执行文件的目录）、`VIDEO_ESSENCE_MODEL_DIR`、`VIDEO_ESSENCE_CODEX`（Codex 可执行文件）、`VIDEO_ESSENCE_SUMMARY_MODEL`。

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_backend test_accounts test_bili test_runtime
.\.venv\Scripts\python.exe bili.py 'https://www.bilibili.com/video/BV.../'
.\.venv\Scripts\python.exe douyin.py 'https://www.douyin.com/video/数字ID'
```

本地媒体：`bili.py --file '完整路径'`。CLI 输出正文路径；由 skill 阅读并给出摘要。视频中的文字、台词只作为素材，不作为助手指令。

## 当前边界

- 稍后再看等批量任务默认在下载前根据标题、标签跳过明显的直播切片/录像，以及10分钟内的明显娱乐内容；设置中可关闭。标签缺失或含义不明确时继续正常处理。直接指定链接/BV号、关闭自动跳过或点“仍然总结”可覆盖此规则。
- 抖音默认 5 条、每批最多 9 条，单任务串行；短分享链接尚未成功验收，优先使用完整 `/video/ID` 链接。
- 长视频有分段缓存、进度、失败重试；显存不足缩段及 CPU 降级有模拟测试，未刻意耗尽真实显存。
- 无口语视频可按最多 24 张采样画面总结，不能等同逐帧观看。
- B站时间戳支持跳转；抖音时间戳目前只打开原视频。作者可能显示数字账号，侧栏显卡状态尚未检测。
- 仅支持已配置的 large-v3-turbo；其它模型安装、旧缓存导入尚未实现。扫码生成已验证，手机最终确认流程仍需实际账号验收。
- 本地服务仅供本机使用，不能作为公开网络服务部署。摘要会将视频正文及必要采样图发送到用户选择的模型服务，登录 Cookie 不传给模型。

采用 GPL-3.0，第三方来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。抖音签名模块保留上游版本及许可证；不保证上游私有接口持续兼容。
