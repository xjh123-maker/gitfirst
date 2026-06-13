# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

🍅 番茄钟 — 基于 Python tkinter 的桌面番茄钟应用，零外部依赖，仅使用 Python 标准库。

## 运行

```bash
python pomodoro.py
```

无构建步骤、无虚拟环境要求、无 pip 安装。仅需 Windows 系统上的 Python 3.x（`tkinter` 和 `winsound` 是标准库的一部分）。

## 架构

整个应用是单文件 (`pomodoro.py`)，包含一个主类 `PomodoroTimer` 和一个 `main()` 入口函数。

### 核心设计

- **无框架** — 纯 tkinter，所有 UI 在 `_build_ui()` 中以命令式布局构建（`pack` 几何管理器）
- **事件驱动** — 计时通过 `tkinter.after(1000, callback)` 实现 1 秒轮询循环；不使用线程
- **模式状态机** — `self.mode` 在 `"work"` → `"break"` → `"long_break"` → `"work"` 之间切换。模式通过 `_apply_mode_style()` 控制背景色、强调色和按钮样式
- **音频回退链** — 计时结束时尝试按顺序播放：
  1. 脚本目录下的外部 WAV 文件（`winsound.PlaySound` 异步）
  2. 外部 MP3/MP4 文件 → 先尝试 MCI（`ctypes.windll.winmm`），失败则 ffmpeg 转码为 WAV
  3. 回退：内存中合成的《兰花草》旋律（16-bit 22050Hz 方波 WAV），写入临时文件后播放
- **息屏特效** — 计时完成时通过全屏黑色 `Toplevel` 模拟屏幕关闭，任意用户交互后关闭
- **提醒弹窗** — 非模态 `Toplevel`：休息提醒（带喝水和活动建议）和工作提醒

### 关键属性（`PomodoroTimer` 实例）

| 属性 | 说明 |
|---|---|
| `self.mode` | `"work"`, `"break"`, `"long_break"` |
| `self.running` / `self.paused` | 计时器状态 |
| `self.current_time` | 剩余秒数 |
| `self.sessions` | 已完成的工作番茄数（触发长休息使用） |
| `self.after_id` | `after()` 回调 ID（用于取消） |
| `self._alarm_id` | 旋律结束定时器 ID |
| `self._blackout` | 息屏遮罩 Toplevel 引用 |

### Windows 专用特性

此应用为 Windows 独占，使用了：
- `winsound.PlaySound` — WAV 播放和停止（`SND_PURGE`）
- `ctypes.windll.winmm.mciSendStringW` — 用于 MP3/MP4 等格式的 MCI 音频
- `subprocess.CREATE_NO_WINDOW` + `STARTUPINFO` — ffmpeg 调用的隐藏窗口
- `tkinter.Toplevel.overrideredirect(True)` — 无边框息屏遮罩
- `widget.wm_attributes("-topmost", ...)` — 窗口置顶

### 配色系统

以类常量的形式定义在 `PomodoroTimer` 顶部 — 每种模式（工作/休息/长休息）都有独立的背景色、强调色和按钮颜色。修改外观时从这里入手。
