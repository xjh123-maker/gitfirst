"""
番茄钟 (Pomodoro Timer) — 桌面番茄钟应用
基于 Python tkinter，无需额外依赖
"""

import tkinter as tk
from tkinter import messagebox
import winsound
import struct
import array
import tempfile
import subprocess
import shutil
import ctypes
import os
import sys


class PomodoroTimer:
    """番茄钟主应用类"""

    # 配色常量
    COLOR_BG_WORK = "#FFF5F5"         # 工作模式背景（淡红）
    COLOR_BG_BREAK = "#F0FFF4"        # 休息模式背景（淡绿）
    COLOR_BG_LONG_BREAK = "#FFF8F0"   # 长休息模式背景（淡橙）
    COLOR_CARD_BG = "#FFFFFF"         # 卡片背景
    COLOR_TEXT = "#2D3748"            # 主文字颜色
    COLOR_TEXT_LIGHT = "#718096"      # 副文字颜色
    COLOR_WORK_ACCENT = "#E74C3C"     # 工作强调色（红）
    COLOR_BREAK_ACCENT = "#27AE60"    # 休息强调色（绿）
    COLOR_LONG_BREAK_ACCENT = "#E67E22"  # 长休息强调色（橙）
    COLOR_BUTTON_START = "#E74C3C"    # 开始按钮
    COLOR_BUTTON_PAUSE = "#F39C12"    # 暂停按钮
    COLOR_BUTTON_RESET = "#95A5A6"    # 重置按钮
    COLOR_BUTTON_TEXT = "#FFFFFF"     # 按钮文字
    COLOR_PROGRESS_BG = "#EDF2F7"     # 进度条背景

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🍅 番茄钟")
        self.root.geometry("380x570")
        self.root.resizable(False, False)
        self.root.configure(bg=self.COLOR_BG_WORK)

        # 尝试设置窗口图标（如果没有ico文件就跳过）
        try:
            if sys.platform == "win32":
                self.root.iconbitmap(default="")
        except Exception:
            pass

        # 状态变量
        self.work_duration = 25 * 60         # 25 分钟（秒）
        self.break_duration = 5 * 60         # 短休息 5 分钟
        self.long_break_duration = 15 * 60   # 长休息 15 分钟
        self.long_break_interval = 3         # 每 N 个番茄触发长休息
        self.current_time = self.work_duration
        self.running = False
        self.paused = False
        self.mode = "work"               # "work" | "break" | "long_break"
        self.sessions = 0                # 完成的工作番茄数
        self.after_id = None             # after() 回调 ID
        self._alarm_id = None            # 旋律结束定时器 ID
        self._melody_wav = None         # 旋律 WAV 数据（懒加载）
        self._melody_tmp_path = None    # 临时 WAV 文件路径

        # 置顶状态
        self.always_on_top = tk.BooleanVar(value=False)

        # 构建 UI
        self._build_ui()

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """构建完整的用户界面"""
        # === 顶部间距 ===
        tk.Frame(self.root, height=20, bg=self.root["bg"]).pack()

        # === 标题 ===
        title_label = tk.Label(
            self.root,
            text="🍅 番茄钟",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg=self.COLOR_TEXT,
            bg=self.root["bg"],
        )
        title_label.pack(pady=(0, 15))

        # === 计时器卡片 ===
        self.timer_card = tk.Frame(
            self.root,
            bg=self.COLOR_CARD_BG,
            highlightbackground="#E2E8F0",
            highlightthickness=1,
            padx=30,
            pady=25,
        )
        # 用 winfo_children 来实现圆角效果的视觉近似
        self.timer_card.pack(padx=25, fill="x")

        self.time_label = tk.Label(
            self.timer_card,
            text=self._format_time(self.current_time),
            font=("Consolas", 52, "bold"),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_CARD_BG,
        )
        self.time_label.pack()

        # 进度条
        self.progress_canvas = tk.Canvas(
            self.timer_card,
            height=6,
            bg=self.COLOR_CARD_BG,
            highlightthickness=0,
        )
        self.progress_canvas.pack(fill="x", pady=(15, 0))
        self._draw_progress(1.0)

        # === 模式标签 ===
        self.mode_label = tk.Label(
            self.root,
            text="🔴 工作中",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=self.COLOR_WORK_ACCENT,
            bg=self.root["bg"],
        )
        self.mode_label.pack(pady=(15, 10))

        # === 控制按钮行 ===
        btn_frame = tk.Frame(self.root, bg=self.root["bg"])
        btn_frame.pack(pady=(5, 5))

        self.start_btn = tk.Button(
            btn_frame,
            text="▶  开始",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=self.COLOR_BUTTON_TEXT,
            bg=self.COLOR_BUTTON_START,
            activebackground="#C0392B",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
            command=self._start_pause,
        )
        self.start_btn.pack(side="left", padx=4)

        self.reset_btn = tk.Button(
            btn_frame,
            text="↺  重置",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=self.COLOR_BUTTON_TEXT,
            bg=self.COLOR_BUTTON_RESET,
            activebackground="#7F8C8D",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
            command=self._reset,
        )
        self.reset_btn.pack(side="left", padx=4)

        # === 模式切换按钮 ===
        self.switch_btn = tk.Button(
            self.root,
            text="🔄  切换为休息",
            font=("Microsoft YaHei UI", 10),
            fg="#4A5568",
            bg="#EDF2F7",
            activebackground="#E2E8F0",
            activeforeground="#4A5568",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._switch_mode,
        )
        self.switch_btn.pack(pady=(8, 5))

        # === 设置按钮 ===
        self.settings_btn = tk.Button(
            self.root,
            text="⚙️  设置",
            font=("Microsoft YaHei UI", 10),
            fg="#4A5568",
            bg="#EDF2F7",
            activebackground="#E2E8F0",
            activeforeground="#4A5568",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._show_settings,
        )
        self.settings_btn.pack(pady=(0, 15))

        # === 分隔线 ===
        sep = tk.Frame(self.root, height=1, bg="#E2E8F0")
        sep.pack(fill="x", padx=40)

        # === 统计区域 ===
        stats_frame = tk.Frame(self.root, bg=self.root["bg"])
        stats_frame.pack(pady=(15, 10))

        self.session_label = tk.Label(
            stats_frame,
            text=f"已完成: {self.sessions} 个番茄 🍅",
            font=("Microsoft YaHei UI", 11),
            fg=self.COLOR_TEXT_LIGHT,
            bg=self.root["bg"],
        )
        self.session_label.pack()

        # 长休息进度提示
        remain = self.long_break_interval - (self.sessions % self.long_break_interval)
        self.long_break_label = tk.Label(
            stats_frame,
            text=f"距长休息还有: {remain} 个番茄",
            font=("Microsoft YaHei UI", 10),
            fg="#A0AEC0",
            bg=self.root["bg"],
        )
        self.long_break_label.pack(pady=(4, 0))

        # === 置顶开关 ===
        topmost_frame = tk.Frame(self.root, bg=self.root["bg"])
        topmost_frame.pack(pady=(5, 0))

        self.topmost_check = tk.Checkbutton(
            topmost_frame,
            text="📌 窗口置顶",
            variable=self.always_on_top,
            font=("Microsoft YaHei UI", 10),
            fg=self.COLOR_TEXT_LIGHT,
            bg=self.root["bg"],
            activebackground=self.root["bg"],
            selectcolor=self.root["bg"],
            cursor="hand2",
            command=self._toggle_topmost,
        )
        self.topmost_check.pack()

        # 底部留白
        tk.Frame(self.root, height=10, bg=self.root["bg"]).pack()

    # ========== 计时核心逻辑 ==========

    def _format_time(self, seconds: int) -> str:
        """将秒数格式化为 MM:SS"""
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    def _draw_progress(self, ratio: float):
        """绘制进度条"""
        self.progress_canvas.delete("all")
        w = self.progress_canvas.winfo_width()
        if w < 10:
            w = 300
        h = 6
        # 背景
        self.progress_canvas.create_rectangle(
            0, 0, w, h,
            fill=self.COLOR_PROGRESS_BG,
            outline="",
        )
        # 进度
        if self.mode == "work":
            fill_color = self.COLOR_WORK_ACCENT
        elif self.mode == "long_break":
            fill_color = self.COLOR_LONG_BREAK_ACCENT
        else:
            fill_color = self.COLOR_BREAK_ACCENT
        self.progress_canvas.create_rectangle(
            0, 0, w * ratio, h,
            fill=fill_color,
            outline="",
        )

    def _start_pause(self):
        """开始 / 暂停 切换"""
        self._stop_alarm()  # 用户操作时停止响铃

        if not self.running:
            # 首次开始
            self.running = True
            self.paused = False
            self.start_btn.config(text="⏸  暂停", bg=self.COLOR_BUTTON_PAUSE,
                                  activebackground="#D68910")
            self._tick()
        elif not self.paused:
            # 暂停
            self.paused = True
            if self.after_id is not None:
                self.root.after_cancel(self.after_id)
                self.after_id = None
            self.start_btn.config(text="▶  继续", bg="#3498DB",
                                  activebackground="#2980B9")
        else:
            # 继续
            self.paused = False
            self.start_btn.config(text="⏸  暂停", bg=self.COLOR_BUTTON_PAUSE,
                                  activebackground="#D68910")
            self._tick()

    def _tick(self):
        """每秒回调：倒数计时"""
        if self.paused or not self.running:
            return

        if self.current_time > 0:
            self.current_time -= 1
            self.time_label.config(text=self._format_time(self.current_time))
            total = self.work_duration if self.mode == "work" else (self.long_break_duration if self.mode == "long_break" else self.break_duration)
            ratio = self.current_time / total
            self._draw_progress(ratio)
            self.after_id = self.root.after(1000, self._tick)
        else:
            self.running = False
            self._timer_complete()

    def _reset(self):
        """重置当前计时"""
        self._stop_alarm()
        self.running = False
        self.paused = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.current_time = self.work_duration if self.mode == "work" else (self.long_break_duration if self.mode == "long_break" else self.break_duration)
        self.time_label.config(text=self._format_time(self.current_time))
        self._draw_progress(1.0)
        self.start_btn.config(text="▶  开始", bg=self.COLOR_BUTTON_START,
                              activebackground="#C0392B")

    def _apply_mode_style(self):
        """根据当前 self.mode 统一更新背景色、模式标签和按钮配色"""
        old_bg = self.root["bg"]  # 记录切换前的背景色，用于递归更新子控件

        if self.mode == "work":
            new_bg = self.COLOR_BG_WORK
            self.mode_label.config(text="🔴 工作中", fg=self.COLOR_WORK_ACCENT)
            self.switch_btn.config(text="🔄  切换为休息")
            self.start_btn.config(bg=self.COLOR_BUTTON_START, activebackground="#C0392B")
        elif self.mode == "long_break":
            new_bg = self.COLOR_BG_LONG_BREAK
            self.mode_label.config(text="🟠 长休息中", fg=self.COLOR_LONG_BREAK_ACCENT)
            self.switch_btn.config(text="🔄  切换为工作")
            self.start_btn.config(bg=self.COLOR_LONG_BREAK_ACCENT, activebackground="#D35400")
        else:  # break
            new_bg = self.COLOR_BG_BREAK
            self.mode_label.config(text="🟢 休息中", fg=self.COLOR_BREAK_ACCENT)
            self.switch_btn.config(text="🔄  切换为工作")
            self.start_btn.config(bg=self.COLOR_BREAK_ACCENT, activebackground="#219A52")

        self.root.configure(bg=new_bg)
        self._update_bg_recursive(self.root, old_bg, new_bg)

    def _switch_mode(self):
        """手动切换模式：工作 → 短休息 → 长休息 → 工作 循环"""
        self._stop_alarm()
        if self.running:
            # 如果正在运行，先停止
            if self.after_id is not None:
                self.root.after_cancel(self.after_id)
                self.after_id = None

        self.running = False
        self.paused = False

        # 三态循环：work → break → long_break → work
        if self.mode == "work":
            self.mode = "break"
            self.current_time = self.break_duration
        elif self.mode == "break":
            self.mode = "long_break"
            self.current_time = self.long_break_duration
        else:  # long_break
            self.mode = "work"
            self.current_time = self.work_duration

        self._apply_mode_style()
        self.time_label.config(text=self._format_time(self.current_time))
        self._draw_progress(1.0)
        self.start_btn.config(text="▶  开始")

    def _update_bg_recursive(self, widget: tk.Widget, old_bg: str, new_bg: str):
        """递归更新所有子控件的背景色"""
        try:
            if widget.cget("bg") == old_bg:
                widget.configure(bg=new_bg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._update_bg_recursive(child, old_bg, new_bg)

    def _timer_complete(self):
        """计时结束处理"""
        self.start_btn.config(text="▶  开始", bg=self.COLOR_BUTTON_START,
                              activebackground="#C0392B")

        # 主线程息屏（避免后台线程调 SendMessage 导致死锁）
        self._monitor_off()

        if self.mode == "work":
            # 完成一个工作番茄
            self.sessions += 1
            self.session_label.config(text=f"已完成: {self.sessions} 个番茄 🍅")

            # 更新长休息倒计时提示
            remain = self.long_break_interval - (self.sessions % self.long_break_interval)
            self.long_break_label.config(
                text=f"距长休息还有: {remain} 个番茄" if remain != self.long_break_interval else "🎉 该长休息啦！"
            )

            # 每 long_break_interval 个番茄触发长休息，否则短休息
            if self.sessions % self.long_break_interval == 0:
                self.mode = "long_break"
                self.current_time = self.long_break_duration
            else:
                self.mode = "break"
                self.current_time = self.break_duration

            self._apply_mode_style()

            # 后台线程播放旋律 + 休息提醒窗口
            self._start_alarm()
            self._show_break_reminder()
        else:
            # 休息结束（短休息或长休息）
            self.mode = "work"
            self.current_time = self.work_duration
            self._apply_mode_style()

            self._start_alarm()
            self._show_work_reminder()

        self.time_label.config(text=self._format_time(self.current_time))
        self._draw_progress(1.0)

    # ==================== 响铃控制（兰花草旋律 + 息屏） ====================

    # 《兰花草》旋律 — 传统版本，仅作无音频文件时的回落
    # 简谱 1=C5，含休止符 0
    _NOTE_FREQ = {
        0: 0, 1: 523, 2: 587, 3: 659, 4: 698, 5: 784, 6: 880, 7: 988,
    }

    ORCHID_MELODY = [
        (3, 400), (3, 300), (3, 200), (2, 300),
        (1, 300), (2, 300), (3, 400), (5, 900),
        (3, 400), (3, 300), (5, 200), (3, 300),
        (2, 300), (1, 400), (2, 300), (1, 900),
    ]

    # ---------- 响铃 ----------

    def _find_audio_file(self):
        """在脚本目录查找外部音频/视频文件"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for name in os.listdir(script_dir):
            lower = name.lower()
            if lower.endswith((".wav", ".mp3", ".mp4", ".m4a", ".flac", ".aac")):
                return os.path.join(script_dir, name)
        return None

    def _start_alarm(self):
        """开始响铃 — 优先外部音频（WAV / MCI），失败则回落 beep 旋律"""
        if self._alarm_id is not None:
            return

        audio_path = self._find_audio_file()

        if audio_path:
            ext = os.path.splitext(audio_path)[1].lower()
            if ext == ".wav":
                # WAV：winsound 原生支持，异步 + 可停止
                try:
                    winsound.PlaySound(
                        audio_path,
                        winsound.SND_FILENAME | winsound.SND_ASYNC,
                    )
                except Exception:
                    pass
                return
            else:
                # MP3 / MP4：先试 MCI，不行就用 ffmpeg 转 WAV
                if self._mci_play(audio_path):
                    return
                # MCI 失败 → 尝试 ffmpeg 自动转 WAV
                converted = self._convert_to_wav(audio_path)
                if converted:
                    try:
                        winsound.PlaySound(
                            converted,
                            winsound.SND_FILENAME | winsound.SND_ASYNC,
                        )
                    except Exception:
                        pass
                    return

        # ── 回落：beep 生成旋律 ──
        if self._melody_wav is None:
            self._melody_wav, self._melody_duration_ms = self._build_melody_wav()

        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False,
            )
            tmp.write(self._melody_wav)
            tmp.close()
            self._melody_tmp_path = tmp.name
        except Exception:
            self._melody_tmp_path = None

        if self._melody_tmp_path:
            try:
                winsound.PlaySound(
                    self._melody_tmp_path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC,
                )
            except Exception:
                pass

        self._alarm_id = self.root.after(
            self._melody_duration_ms + 500,
            self._on_melody_finished,
        )

    def _on_melody_finished(self):
        """旋律自然结束回调"""
        self._cleanup_melody_tmp()
        self._monitor_on()
        self._alarm_id = None

    def _stop_alarm(self):
        """停止响铃并关闭遮罩"""
        if self._alarm_id is not None:
            try:
                self.root.after_cancel(self._alarm_id)
            except Exception:
                pass
            self._alarm_id = None
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self._mci_stop()
        self._cleanup_melody_tmp()
        self._monitor_on()

    # ---------- MCI 播放控制（MP3/MP4 等非 WAV 格式） ----------

    # MCI 别名，避免和其他程序冲突
    MCI_ALIAS = "pomodoro_alarm"

    def _mci_play(self, path):
        """用 MCI 后台播放 — 成功返回 True，失败返回 False"""
        self._mci_stop()
        try:
            r = ctypes.windll.winmm.mciSendStringW(
                f'open "{path}" alias {self.MCI_ALIAS}', None, 0, None,
            )
            if r != 0:
                return False  # 打开失败（可能无解码器）
            ctypes.windll.winmm.mciSendStringW(
                f"play {self.MCI_ALIAS}", None, 0, None,
            )
            return True
        except Exception:
            return False

    def _mci_stop(self):
        """停止 MCI 播放"""
        try:
            ctypes.windll.winmm.mciSendStringW(
                f"stop {self.MCI_ALIAS}", None, 0, None,
            )
            ctypes.windll.winmm.mciSendStringW(
                f"close {self.MCI_ALIAS}", None, 0, None,
            )
        except Exception:
            pass

    def _convert_to_wav(self, src_path):
        """用 ffmpeg 将音频/视频转为 WAV，成功返回 WAV 路径"""
        wav_path = os.path.splitext(src_path)[0] + "_orchid.wav"
        if os.path.isfile(wav_path):
            return wav_path
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            return None
        try:
            # CREATE_NO_WINDOW 防止 ffmpeg 弹出控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.run(
                [
                    ffmpeg, "-y", "-i", src_path,
                    "-vn",                # 不要视频
                    "-acodec", "pcm_s16le",
                    "-ar", "22050",
                    "-ac", "1",
                    wav_path,
                ],
                capture_output=True,
                timeout=120,
                check=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
            )
            if os.path.isfile(wav_path):
                return wav_path
        except Exception:
            pass
        return None

    def _cleanup_melody_tmp(self):
        """删除临时 WAV 文件"""
        if self._melody_tmp_path:
            try:
                os.unlink(self._melody_tmp_path)
            except Exception:
                pass
            self._melody_tmp_path = None

    def _build_melody_wav(self):
        """将《兰花草》旋律生成为 WAV 格式的连续音频

        生成 22050Hz 16-bit 单声道方波，音符间加 5ms 静音做自然断句。
        返回 (wav_bytes, total_duration_ms)。
        """
        SAMPLE_RATE = 22050
        AMPLITUDE = 28000
        NOTE_GAP_MS = 5

        samples = array.array("h")  # signed 16-bit

        for note, duration_ms in self.ORCHID_MELODY:
            freq = self._NOTE_FREQ.get(note, 440)
            n = int(SAMPLE_RATE * duration_ms / 1000)

            if freq > 0 and n > 0:
                period = int(SAMPLE_RATE / freq)
                half = period // 2
                one_period = array.array(
                    "h",
                    [AMPLITUDE] * half + [-AMPLITUDE] * (period - half),
                )
                repeats = n // period
                remainder = n % period
                if repeats:
                    samples.extend(one_period * repeats)
                if remainder:
                    samples.extend(one_period[:remainder])

            gap = int(SAMPLE_RATE * NOTE_GAP_MS / 1000)
            if gap:
                samples.extend([0] * gap)

        total_ms = sum(dur for _, dur in self.ORCHID_MELODY)
        data_bytes = samples.tobytes()

        # PCM = 1, mono = 1
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + len(data_bytes), b"WAVE",
            b"fmt ", 16, 1, 1,
            SAMPLE_RATE,
            SAMPLE_RATE * 2,
            2,
            16,
            b"data", len(data_bytes),
        )
        return header + data_bytes, total_ms

    # ---------- 息屏遮罩（全屏黑窗，不碰系统 API） ----------

    def _monitor_off(self):
        """显示全屏黑色遮罩模拟息屏 — 纯 tkinter"""
        if hasattr(self, "_blackout") and self._blackout is not None:
            return
        self._blackout = tk.Toplevel(self.root)
        self._blackout.attributes("-fullscreen", True)
        self._blackout.attributes("-topmost", True)
        self._blackout.configure(bg="black", cursor="none")
        for seq in ("<Button-1>", "<Key>", "<Motion>"):
            self._blackout.bind(seq, self._on_blackout_dismiss)
        self._blackout.overrideredirect(True)
        self._blackout.update()

    def _on_blackout_dismiss(self, event=None):
        """用户交互 → 关闭遮罩（不停止旋律）"""
        self._monitor_on()

    def _monitor_on(self):
        """关闭息屏遮罩 — 可安全重复调用"""
        if hasattr(self, "_blackout") and self._blackout is not None:
            try:
                self._blackout.destroy()
            except Exception:
                pass
            self._blackout = None

    def _show_break_reminder(self):
        """弹出休息提醒窗口 — 短休息和长休息显示不同内容"""
        # 阻止重复弹出
        if hasattr(self, "_reminder_open") and self._reminder_open:
            return
        self._reminder_open = True

        is_long = self.mode == "long_break"
        break_mins = self.current_time // 60

        # 根据休息类型选用不同的文案和配色
        if is_long:
            title = "🎉 长休息时间！"
            subtitle = f"已连续完成 {self.long_break_interval} 个番茄，休息 {break_mins} 分钟吧～ 🍅"
            icon = "☕"
            water_text = "接杯水，补充水分！"
            move_text = "站起来走动一下，伸展身体"
            btn_text = "👌  好的，好好休息"
            btn_color = "#E67E22"
            btn_active = "#D35400"
            bg_color = "#FFF8F0"
            water_color = "#E67E22"
        else:
            title = "🍅 该休息啦！"
            subtitle = f"已完成 {self.sessions} 个番茄，休息 {break_mins} 分钟～ 🍅"
            icon = "🧘"
            water_text = "起来喝杯水！"
            move_text = "站起来活动一下身体"
            btn_text = "👌  好的，开始休息"
            btn_color = "#27AE60"
            btn_active = "#219A52"
            bg_color = "#FFFDF5"
            water_color = "#3182CE"

        reminder = tk.Toplevel(self.root)
        reminder.title(title)
        reminder.geometry("400x380")
        reminder.resizable(False, False)
        reminder.configure(bg=bg_color)

        # 置顶
        reminder.wm_attributes("-topmost", True)

        # 居中于主窗口
        reminder.update_idletasks()
        rw = reminder.winfo_width()
        rh = reminder.winfo_height()
        px = self.root.winfo_x()
        py = self.root.winfo_y()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        x = px + (pw - rw) // 2
        y = py + (ph - rh) // 2
        reminder.geometry(f"+{x}+{y}")

        def on_close():
            self._stop_alarm()
            self._reminder_open = False
            reminder.destroy()

        reminder.protocol("WM_DELETE_WINDOW", on_close)

        # === 内容 ===
        # 顶部大图标
        tk.Label(
            reminder,
            text=icon,
            font=("Microsoft YaHei UI", 64),
            bg=bg_color,
        ).pack(pady=(30, 5))

        # 主标题
        tk.Label(
            reminder,
            text=title,
            font=("Microsoft YaHei UI", 22, "bold"),
            fg="#2D3748",
            bg=bg_color,
        ).pack()

        # 副标题
        tk.Label(
            reminder,
            text=subtitle,
            font=("Microsoft YaHei UI", 12),
            fg="#718096",
            bg=bg_color,
        ).pack(pady=(4, 15))

        # 分隔线
        sep = tk.Frame(reminder, height=1, bg="#E2E8F0")
        sep.pack(fill="x", padx=50)

        # 喝水提醒
        water_frame = tk.Frame(reminder, bg=bg_color)
        water_frame.pack(pady=(15, 5))

        tk.Label(
            water_frame,
            text="💧",
            font=("Microsoft YaHei UI", 28),
            bg=bg_color,
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            water_frame,
            text=water_text,
            font=("Microsoft YaHei UI", 16, "bold"),
            fg=water_color,
            bg=bg_color,
        ).pack(side="left")

        # 活动提醒
        move_frame = tk.Frame(reminder, bg=bg_color)
        move_frame.pack(pady=5)

        tk.Label(
            move_frame,
            text="🚶",
            font=("Microsoft YaHei UI", 28),
            bg=bg_color,
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            move_frame,
            text=move_text,
            font=("Microsoft YaHei UI", 14),
            fg="#718096",
            bg=bg_color,
        ).pack(side="left")

        # 确认按钮 — 关闭弹窗并停止响铃
        def dismiss():
            self._stop_alarm()
            on_close()

        tk.Button(
            reminder,
            text=btn_text,
            font=("Microsoft YaHei UI", 13, "bold"),
            fg="#FFFFFF",
            bg=btn_color,
            activebackground=btn_active,
            activeforeground="white",
            relief="flat",
            padx=24,
            pady=10,
            cursor="hand2",
            command=dismiss,
        ).pack(pady=(20, 10))

        # 底部提示
        tk.Label(
            reminder,
            text=f"⏳ {break_mins} 分钟休息计时已自动开始",
            font=("Microsoft YaHei UI", 10),
            fg="#A0AEC0",
            bg=bg_color,
        ).pack()

    def _show_work_reminder(self):
        """弹出「该工作了」提醒窗口 — 非模态，不会阻塞 UI"""
        # 阻止重复弹出
        if hasattr(self, "_work_reminder_open") and self._work_reminder_open:
            return
        self._work_reminder_open = True

        reminder = tk.Toplevel(self.root)
        reminder.title("⏰ 休息结束")
        reminder.geometry("360x280")
        reminder.resizable(False, False)
        reminder.configure(bg="#FFF5F5")

        # 置顶并居中
        reminder.wm_attributes("-topmost", True)
        reminder.update_idletasks()
        rw = reminder.winfo_width()
        rh = reminder.winfo_height()
        px = self.root.winfo_x()
        py = self.root.winfo_y()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        x = px + (pw - rw) // 2
        y = py + (ph - rh) // 2
        reminder.geometry(f"+{x}+{y}")

        def on_close():
            self._stop_alarm()
            self._work_reminder_open = False
            reminder.destroy()

        reminder.protocol("WM_DELETE_WINDOW", on_close)

        # 内容
        tk.Label(
            reminder,
            text="⏰",
            font=("Microsoft YaHei UI", 56),
            bg="#FFF5F5",
        ).pack(pady=(30, 5))

        tk.Label(
            reminder,
            text="休息时间到！",
            font=("Microsoft YaHei UI", 20, "bold"),
            fg="#2D3748",
            bg="#FFF5F5",
        ).pack()

        tk.Label(
            reminder,
            text="开始下一个番茄吧～ 🍅",
            font=("Microsoft YaHei UI", 13),
            fg="#718096",
            bg="#FFF5F5",
        ).pack(pady=(5, 20))

        tk.Button(
            reminder,
            text="👌  开始工作",
            font=("Microsoft YaHei UI", 13, "bold"),
            fg="#FFFFFF",
            bg="#E74C3C",
            activebackground="#C0392B",
            activeforeground="white",
            relief="flat",
            padx=28,
            pady=10,
            cursor="hand2",
            command=on_close,
        ).pack(pady=(5, 10))

    # ==================== 设置面板 ====================

    def _show_settings(self):
        """打开自定义设置窗口 — 可调整工作/休息时长和长休息间隔"""
        # 阻止重复弹出
        if hasattr(self, "_settings_open") and self._settings_open:
            return
        self._settings_open = True

        dialog = tk.Toplevel(self.root)
        dialog.title("⚙️ 番茄钟设置")
        dialog.geometry("360x350")
        dialog.resizable(False, False)
        dialog.configure(bg="#FFFFFF")

        # 置顶并居中
        dialog.wm_attributes("-topmost", True)
        dialog.update_idletasks()
        dw = dialog.winfo_width()
        dh = dialog.winfo_height()
        px = self.root.winfo_x()
        py = self.root.winfo_y()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        dialog.geometry(f"+{x}+{y}")

        def on_close():
            self._settings_open = False
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)

        # 标题
        tk.Label(
            dialog,
            text="⚙️  自定义时间",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg="#2D3748",
            bg="#FFFFFF",
        ).pack(pady=(20, 20))

        # 表单容器
        form = tk.Frame(dialog, bg="#FFFFFF")
        form.pack(padx=30)

        # 获取当前值（分钟，精确到 0.1）
        work_mins = tk.DoubleVar(value=self.work_duration / 60.0)
        break_mins = tk.DoubleVar(value=self.break_duration / 60.0)
        long_break_mins = tk.DoubleVar(value=self.long_break_duration / 60.0)
        interval = tk.IntVar(value=self.long_break_interval)

        fields = [
            ("🍅  工作时间 (分钟)",     work_mins,       0.1, 120.0, 0.1, "%.1f"),
            ("🟢  短休息时间 (分钟)",   break_mins,      0.1, 60.0,  0.1, "%.1f"),
            ("🟠  长休息时间 (分钟)",   long_break_mins, 0.1, 60.0,  0.1, "%.1f"),
            ("🔁  长休息间隔 (几个番茄)", interval,      1,   10,    1,   "%.0f"),
        ]

        for label_text, var, vmin, vmax, step, fmt in fields:
            row = tk.Frame(form, bg="#FFFFFF")
            row.pack(fill="x", pady=5)

            tk.Label(
                row,
                text=label_text,
                font=("Microsoft YaHei UI", 11),
                fg="#4A5568",
                bg="#FFFFFF",
                anchor="w",
            ).pack(side="left")

            sb = tk.Spinbox(
                row,
                textvariable=var,
                from_=vmin,
                to=vmax,
                increment=step,
                format=fmt,
                width=6,
                font=("Microsoft YaHei UI", 12),
                justify="center",
                relief="solid",
                borderwidth=1,
                buttonbackground="#EDF2F7",
            )
            sb.pack(side="right")

        # 按钮行
        btn_frame = tk.Frame(dialog, bg="#FFFFFF")
        btn_frame.pack(pady=(25, 15))

        def save():
            """保存设置并应用"""
            w = work_mins.get()
            b = break_mins.get()
            lb = long_break_mins.get()
            iv = int(interval.get())

            # 更新时长（秒）— 浮点分钟 × 60 → 整数秒
            self.work_duration = int(w * 60)
            self.break_duration = int(b * 60)
            self.long_break_duration = int(lb * 60)
            self.long_break_interval = iv

            # 重置当前计时以应用新设置
            self._stop_alarm()
            self.running = False
            self.paused = False
            if self.after_id is not None:
                self.root.after_cancel(self.after_id)
                self.after_id = None

            self.mode = "work"
            self.current_time = self.work_duration
            self._apply_mode_style()
            self.time_label.config(text=self._format_time(self.current_time))
            self._draw_progress(1.0)
            self.start_btn.config(text="▶  开始")

            # 更新长休息提示
            remain = self.long_break_interval - (self.sessions % self.long_break_interval)
            self.long_break_label.config(text=f"距长休息还有: {remain} 个番茄")

            on_close()

        def cancel():
            on_close()

        tk.Button(
            btn_frame,
            text="保存",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#FFFFFF",
            bg="#27AE60",
            activebackground="#219A52",
            activeforeground="white",
            relief="flat",
            padx=24,
            pady=8,
            cursor="hand2",
            command=save,
        ).pack(side="left", padx=8)

        tk.Button(
            btn_frame,
            text="取消",
            font=("Microsoft YaHei UI", 11),
            fg="#4A5568",
            bg="#EDF2F7",
            activebackground="#E2E8F0",
            activeforeground="#4A5568",
            relief="flat",
            padx=24,
            pady=8,
            cursor="hand2",
            command=cancel,
        ).pack(side="left", padx=8)

    def _toggle_topmost(self):
        """切换窗口置顶"""
        self.root.wm_attributes("-topmost", self.always_on_top.get())

    def _on_close(self):
        """关闭窗口时清理"""
        self._stop_alarm()
        self.running = False
        self.paused = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.root.destroy()


def main():
    """入口函数"""
    root = tk.Tk()
    app = PomodoroTimer(root)

    # 居中窗口
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
