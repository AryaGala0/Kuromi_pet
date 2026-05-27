# 🖤 库洛米桌面宠物 ｜ Kuromi Desktop Pet

> 一只陪你工作、提醒你吃饭喝水下班的可爱库洛米！  
> A cute Kuromi who keeps you company at work and reminds you to eat, drink and clock off!

![AI Generated](https://img.shields.io/badge/AI%20Generated-90%25-ff69b4?style=flat-square&logo=openai&logoColor=white)
![Human Curated](https://img.shields.io/badge/Human%20Curated-10%25-blueviolet?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)

> 🤖 **本项目约 90% 的代码、文档与素材由 AI 生成**，人工仅负责需求设计、调试与少量微调。  
> 🤖 **About 90% of the code, docs and assets in this project were written by AI.** Humans only handled requirements, debugging and minor tweaks.

[简体中文](#-中文文档) ｜ [English](#-english-docs)

---

## 🐰 中文文档

### ✨ 功能

- 🪟 **透明无边框窗口** + 始终置顶
- 🖱️ **左键拖拽**自由移动到屏幕任意位置
- 💬 **可爱气泡对话**（带尾巴指向桌宠）
- ⏰ **定时提醒**：吃早午晚餐、下班、多次喝水
- 🔔 **系统托盘通知**（即使关掉窗口也能提醒）
- 🎀 **右键菜单**：查看 / 添加 / 修改 / 删除提醒、切换状态
- 🎭 **表情切换**：触发提醒时切换成开心表情
- 💤 **闲聊**：每隔几分钟随机蹦一句话

### 🆕 更新日志

#### v1.1.0
- 🤖 **AI 对话情绪联动动画**：与库洛米 AI 聊天时，会自动识别她回复中的情绪并切换到对应的动画状态——
  - 回复带有「开心 / 高兴 / 快乐 / 喜欢 / 哈哈 / 嘿嘿 / 可爱」等字眼时 → 切换到 `happy` 帧
  - 回复带有「生气 / 讨厌 / 哼 / 气死 / 烦死 / 无语」等字眼时 → 切换到 `angry` 帧
  - 回复带有「偷看 / 偷偷 / 害羞 / 悄悄」等字眼时 → 切换到 `peek` 帧
  - 切换持续约 6 秒后自动恢复
- 🎯 **三层情绪识别策略**（优先级从高到低）：
  1. 模型显式标注的括号标签（如 `（开心）`、`（生气）`）—— 最可信
  2. 回复末尾 12 字符内的裸关键词兜底（如「好开心」）
  3. **全文关键词扫描**（本次新增）：即使模型忘记加情绪标签，只要正文中出现情绪字眼也能触发动画切换
- ⚖️ **冲突优先级**：当回复中同时出现多种情绪关键词时，按 `angry > happy > peek` 的顺序判定，避免普通的「哈哈」覆盖更强的「生气」信号
- P.S. 我把config文件的api_key删除了，如果你要使用代码的话，需要自己取glm的官网上申请一个免费的api key

#### v1.0.1
- 🎭 **手动切换状态时不再有"先变开心再回来"的过渡**：右键菜单切换状态会直接呈现目标状态，气泡仅作文字提示。
- 🪟 **修复添加 / 修改提醒对话框中文字被截断的问题**：
  - 对话框宽度从固定 340px 改为最小 420px，可随内容自适应
  - 输入框增加最小高度，并设置为可随窗口拉伸
  - 「保存 / 添加 / 取消」按钮加大内边距，避免按钮文字被裁
- 🎨 **`QMessageBox`（关于 / 删除确认 / 输入校验提示）适配紫色主题**：之前在透明桌宠下可能出现黑底黑字看不清的问题已修复，并设置最小宽度避免长文本截断。
- 💬 **修复气泡 `SpeechBubble` 文字被折叠 / 最后一行被裁的问题**：测量与绘制使用同一份 `QFont` 实例，并采用足够大的最大高度让 `boundingRect` 正确计算多行换行后的真实高度，额外加半行冗余防止下沉笔画被切。



### 🛠 技术栈

| 项目 | 选用 | 理由 |
|---|---|---|
| 语言 | **Python 3.10+** | 开发快、跨平台、生态丰富 |
| GUI | **PySide6 (Qt6)** | 原生透明窗口、性能好、商用免费 (LGPL) |
| 配置 | JSON | 用户可随时编辑 |

> 也可以用 PyQt5 / PyQt6，API 完全一致。

### 📦 安装与运行

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 把精灵图（4 行 × 6 帧）保存为 assets/sheet.png
#    然后切图（自动把白底转透明）
python slice_sheet.py

# 3. 运行桌宠
python kuromi_pet.py
```

> Windows 推荐 Python ≥ 3.10。

### 🎞 帧动画系统

- 精灵图共 **4 行**，每行代表一种状态，每行 **6 帧**：

| 行 | 状态 ID | 说明 |
|---|---|---|
| 1 | `normal` | 日常 |
| 2 | `happy`  | 开心 / 爱心 |
| 3 | `angry`  | 生气 / 喷气 |
| 4 | `peek`   | 偷看（半身） |

- 默认 **10 FPS** 循环播放当前状态的 6 帧
- **每 20 分钟**自动按顺序切换到下一个状态
- **右键菜单 → 🎭 切换状态**：手动切换 / 直接跳到指定状态
- 触发提醒时会**临时切到 happy**，过几秒自动还原
- 双击桌宠会**临时切到 angry**，调皮一下

> FPS 和切换间隔可在 `config.json -> animation` 中改：
> ```json
> "animation": { "fps": 10, "state_switch_minutes": 20 }
> ```

### 🗂 目录结构

```
Kuromi/
├── kuromi_pet.py        # 主程序
├── slice_sheet.py       # 精灵图切分工具（白底转透明）
├── make_icon.py         # 生成 exe 图标
├── KuromiPet.spec       # PyInstaller 打包配置
├── build.bat            # 一键打包脚本
├── config.json          # 提醒 + 动画配置
├── requirements.txt
├── README.md
└── assets/
    ├── sheet.png        # 你的 4×6 精灵图（放这里）
    └── frames/          # 切分脚本生成
        ├── normal/frame_0.png ... frame_5.png
        ├── happy/
        ├── angry/
        └── peek/
```

### ⚙️ 自定义提醒

直接编辑 `config.json`：

```json
{
  "id": "tea_time",
  "name": "下午茶",
  "time": "15:30",
  "message": "下午茶时间到啦~喝杯奶茶吧！",
  "enabled": true
}
```

- `time` 必须是 24 小时制 `HH:MM`
- `enabled` 为 `false` 时该条不触发
- 也可以在桌宠上**右键 → 今日提醒**中点击开关，或通过菜单**添加 / 修改 / 删除**

### 🎮 操作

| 操作 | 效果 |
|---|---|
| 左键拖动 | 移动库洛米 |
| 双击 | 触发害羞对话 |
| 右键 | 弹出菜单 |
| 托盘双击 | 显示 / 隐藏库洛米 |

### 📦 打包成单独 exe

仓库已附带 `KuromiPet.spec` 与一键脚本 `build.bat`：

```powershell
# (可选) 生成 exe 图标
python make_icon.py

# 一键打包
build.bat
```

或手动执行：

```powershell
pip install pyinstaller
pyinstaller KuromiPet.spec --noconfirm --clean
```

产物：`dist/KuromiPet.exe`，双击即可运行，无需 Python 环境。  
首次启动会在 exe 旁边自动生成 `config.json`，用户对提醒的修改会持久保存。

### 🌟 后续可扩展

- 帧动画（多张图循环播放，走路 / 眨眼）
- 语音 TTS 播报提醒
- 番茄钟 / 久坐提醒
- 透明窗口穿透（不挡操作）—— 已预留 `click_through` 字段
- 多只宠物切换（Hello Kitty / 美乐蒂 / 大耳狗）

---

## 🐰 English Docs

### ✨ Features

- 🪟 **Transparent, frameless, always-on-top window**
- 🖱️ **Left-click drag** to move Kuromi anywhere on screen
- 💬 **Cute speech bubble** with a tail pointing to the pet
- ⏰ **Scheduled reminders**: meals, clock-off, multiple water breaks
- 🔔 **System tray notifications** (even when the window is hidden)
- 🎀 **Right-click menu**: view / add / edit / delete reminders, switch state
- 🎭 **Emotion switching**: shows a happy face when a reminder fires
- 💤 **Idle chatter**: random cute lines every few minutes

### 🆕 Changelog

#### v1.1.0
- 🤖 **AI chat now drives the animation state**: while chatting with Kuromi, her reply is scanned for emotion words and the matching animation kicks in automatically —
  - Words like "开心 / 高兴 / 快乐 / 喜欢 / 哈哈 / 嘿嘿 / 可爱" (happy / glad / love / haha) → switches to the `happy` frames
  - Words like "生气 / 讨厌 / 哼 / 气死 / 烦死 / 无语" (angry / hate / hmph / annoyed) → switches to the `angry` frames
  - Words like "偷看 / 偷偷 / 害羞 / 悄悄" (peek / shy / sneaky) → switches to the `peek` frames
  - The temporary state lasts ~6 s before reverting
- 🎯 **Three-layer emotion detection** (high → low priority):
  1. Explicit bracket tags from the model, e.g. `（开心）` / `（生气）` — most reliable
  2. Bare keyword fallback in the last 12 characters of the reply (e.g. "好开心")
  3. **Full-text keyword scan (new in this release)**: even if the model forgets the bracket tag, any emotion word inside the reply still triggers the animation
- ⚖️ **Tie-breaking**: when multiple emotion words coexist in a reply, the priority order is `angry > happy > peek`, so a casual "haha" never overrides a stronger "angry" signal
- P.S. I delete the api_key in config.py, if you want to use the code, you should ask for a api key in GLM official website

#### v1.0.1
- 🎭 **Manual state switch is now instant** — no more "flash to happy and back". The right-click state switch jumps straight to the target state; the bubble is text-only.
- 🪟 **Fixed clipped text in the Add / Edit Reminder dialog**:
  - Dialog width changed from a fixed 340px to a minimum 420px and auto-grows with content
  - Inputs now have a minimum height and stretch with the dialog
  - "Save / Add / Cancel" buttons get larger padding so the labels are no longer cut off
- 🎨 **`QMessageBox` (About / Delete confirm / input validation) now follows the purple theme** — fixes the previous "black-on-black, unreadable" issue on the transparent pet, and adds a minimum width to prevent long text from being truncated.
- 💬 **Fixed the `SpeechBubble` collapsing text / clipping the last line**: measurement and painting now use the exact same `QFont` instance, and `boundingRect` is given a large enough max height to correctly compute the wrapped multi-line height, with an extra half-line of padding so descenders are no longer chopped.



### 🛠 Tech Stack

| Item | Choice | Reason |
|---|---|---|
| Language | **Python 3.10+** | Fast to develop, cross-platform, rich ecosystem |
| GUI | **PySide6 (Qt6)** | Native transparency, great performance, LGPL-friendly |
| Config | JSON | Easy for users to edit |

> PyQt5 / PyQt6 also works — the APIs are identical.

### 📦 Install & Run

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Put your 4-row x 6-frame sprite sheet at assets/sheet.png,
#    then slice it (white background will be turned transparent)
python slice_sheet.py

# 3. Run the pet
python kuromi_pet.py
```

> Python ≥ 3.10 is recommended on Windows.

### 🎞 Frame Animation

- The sprite sheet has **4 rows × 6 frames**:

| Row | State ID | Meaning |
|---|---|---|
| 1 | `normal` | Idle |
| 2 | `happy`  | Happy / hearts |
| 3 | `angry`  | Angry / steaming |
| 4 | `peek`   | Peeking (half-body) |

- Plays 6 frames of the current state in a loop at **10 FPS** by default
- Automatically rotates to the next state every **20 minutes**
- **Right-click → 🎭 Switch State** to change manually or jump to a specific state
- A reminder temporarily switches Kuromi to `happy`, then restores
- Double-click temporarily switches her to `angry` for a playful pout

> Tweak FPS and rotation in `config.json -> animation`:
> ```json
> "animation": { "fps": 10, "state_switch_minutes": 20 }
> ```

### 🗂 Project Layout

```
Kuromi/
├── kuromi_pet.py        # Main program
├── slice_sheet.py       # Sprite slicer (white background -> transparent)
├── make_icon.py         # Generates the exe icon
├── KuromiPet.spec       # PyInstaller build config
├── build.bat            # One-click build script
├── config.json          # Reminders + animation config
├── requirements.txt
├── README.md
└── assets/
    ├── sheet.png        # Your 4x6 sprite sheet goes here
    └── frames/          # Generated by slice_sheet.py
        ├── normal/frame_0.png ... frame_5.png
        ├── happy/
        ├── angry/
        └── peek/
```

### ⚙️ Customize Reminders

Edit `config.json` directly:

```json
{
  "id": "tea_time",
  "name": "Tea time",
  "time": "15:30",
  "message": "It's tea time~ grab a cup of milk tea!",
  "enabled": true
}
```

- `time` must be 24-hour format `HH:MM`
- `enabled: false` disables a reminder
- You can also toggle / **add / edit / delete** reminders from the right-click menu

### 🎮 Controls

| Action | Effect |
|---|---|
| Left-click drag | Move Kuromi |
| Double-click | Trigger a shy line |
| Right-click | Open the context menu |
| Double-click tray icon | Show / hide Kuromi |

### 📦 Build a Standalone exe

A `KuromiPet.spec` and a one-click `build.bat` are included:

```powershell
# (optional) generate the exe icon first
python make_icon.py

# one-click build
build.bat
```

Or manually:

```powershell
pip install pyinstaller
pyinstaller KuromiPet.spec --noconfirm --clean
```

Output: `dist/KuromiPet.exe` — double-click to run, no Python required.  
On first launch a `config.json` is created next to the exe, so user edits to reminders are persisted.

### 🌟 Roadmap

- Richer frame animations (walking / blinking)
- TTS voice for reminders
- Pomodoro / sit-too-long reminders
- Click-through transparent window (already reserved as `click_through`)
- Multiple pets to switch (Hello Kitty / My Melody / Cinnamoroll)

---

### 📝 License & Disclaimer ｜ 许可与声明

Kuromi character © Sanrio. This project is for personal / learning use only.  
库洛米形象版权归 Sanrio 所有，本项目仅供个人学习使用。

#### 🤖 AI Disclosure ｜ AI 透明声明

- 🇨🇳 本项目约 **90% 的内容**（包括但不限于 Python 代码、`README.md`、`config.json`、打包脚本、注释与提示文案）由 AI 助手生成；剩余约 10% 为作者进行的需求规划、UI 调试、参数调优与人工校对。使用前请自行检查代码安全性与适用性。
- 🇬🇧 Approximately **90% of this project** — including the Python source, this `README.md`, `config.json`, build scripts, comments and prompt strings — was generated by an AI assistant. The remaining ~10% covers requirement planning, UI tuning, parameter polishing and manual review by the author. Please review the code for safety and fitness for your use case before relying on it.



