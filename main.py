import sys
import json
import random
from datetime import datetime, timedelta
from collections import defaultdict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QProgressBar, QPushButton, QStackedWidget, QLineEdit, QFormLayout, QMenu,
    QAction, QMessageBox, QGroupBox, QComboBox, QDateEdit, QSpinBox, QInputDialog, QGraphicsSimpleTextItem,
    QDialog, QDialogButtonBox, QTextEdit, QScrollArea, QShortcut, QAbstractItemView, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, QSize
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PyQt5.QtGui import QColor, QPainter, QKeySequence

# --- 全局变量 ---
# 将缩放因子设为全局可修改变量，以便在运行时调整
SCALING_FACTOR = 1.0

# 获取屏幕DPI缩放因子
def get_base_scaling_factor():
    screen = QApplication.primaryScreen()
    dpi = screen.logicalDotsPerInch()
    # 基准DPI为96，计算缩放因子
    return dpi / 96.0

# 根据缩放因子调整尺寸
def scaled_size(size):
    return int(size * SCALING_FACTOR)

# 根据缩放因子调整字体大小
def scaled_font_size(base_size):
    return scaled_size(base_size)

# 数据结构定义
class SubTask:
    def __init__(self, name, total=100, auto_offset=0):
        self.name = name
        self.total = total
        self.auto_offset = auto_offset
        self.records = {}  # {date: progress}
    
    @property
    def progress(self):
        if not self.records:
            return 0
        last_date = max(self.records.keys())
        return self.records[last_date]
    
    @property
    def completed(self):
        return min(self.progress, self.total)
    
    def add_record(self, date, progress):
        self.records[date] = progress
    
    def to_dict(self):
        return {
            "name": self.name,
            "total": self.total,
            "auto_offset": self.auto_offset,
            "records": self.records
        }
    
    @classmethod
    def from_dict(cls, data):
        subtask = cls(data.get("name", ""), data.get("total", 100), data.get("auto_offset", 0))
        subtask.records = {k: v for k, v in data.get("records", {}).items()}
        return subtask

class Task:
    # 新增类变量 RECENT_X，表示用于计算剩余天数时使用的最近样本数 x（默认 5）
    RECENT_X = 5

    STATUS_COLORS = {
        "进行中": QColor(50, 205, 50),    # 绿色
        "暂停": QColor(255, 215, 0),      # 黄色
        "废止": QColor(220, 20, 60)       # 红色
    }
    
    def __init__(self, name):
        self.name = name
        self.status = "进行中"
        self.sub_tasks = []
        self.start_date = datetime.now().strftime("%Y-%m-%d")
    
    def add_subtask(self, subtask):
        self.sub_tasks.append(subtask)
    
    @property
    def total(self):
        return sum(st.total for st in self.sub_tasks)
    
    @property
    def completed(self):
        return sum(st.completed for st in self.sub_tasks)
    
    @property
    def progress(self):
        return (self.completed / self.total * 100) if self.total > 0 else 0
    
    @property
    def remaining_days(self):
        """
        修改后的剩余天数计算逻辑（按用户要求）：
        - 取全任务的按日期快照（每个日期的总体完成量）
        - 取最近 Task.RECENT_X 次快照：change = newest - oldest
        - avg = change / len(samples)  （按用户要求“除以天数（也就是 x）”）
        - remaining = total - newest
        - remaining_days = round(remaining / avg) （若 avg <= 0 或数据不足，返回 0）
        """
        # 若没有子任务，无法估算
        if not self.sub_tasks:
            return 0
        
        # 收集所有出现过的日期（来自每个子任务）
        all_dates = set()
        for st in self.sub_tasks:
            all_dates.update(st.records.keys())
        
        if not all_dates:
            return 0
        
        # 将字符串日期转换为 datetime 并排序
        try:
            date_objs = sorted({datetime.strptime(d, "%Y-%m-%d") for d in all_dates})
        except Exception:
            return 0
        
        # 构建按日期的总体完成量快照（每个日期取该日或之前每个子任务的最近记录并相加）
        snapshots = []
        for d_obj in date_objs:
            d_str = d_obj.strftime("%Y-%m-%d")
            total_completed_on_date = 0
            for st in self.sub_tasks:
                # 找到 st 在 d_str 当天或之前的最新记录
                cand_dates = [dd for dd in st.records.keys() if dd <= d_str]
                if cand_dates:
                    latest = max(cand_dates)
                    total_completed_on_date += min(st.records[latest], st.total)
                else:
                    total_completed_on_date += 0
            snapshots.append((d_obj, total_completed_on_date))
        
        if len(snapshots) < 2:
            return 0
        
        # 取最近 RECENT_X 次快照（如果样本不足则取全部可用）
        x = max(1, int(Task.RECENT_X))
        samples = snapshots[-x:] if x <= len(snapshots) else snapshots[:]
        
        # 如果样本少于2条，无法计算
        if len(samples) < 2:
            return 0
        
        oldest_val = samples[0][1]
        newest_val = samples[-1][1]
        change = newest_val - oldest_val
        
        denom = len(samples)  # 按你的要求，除以样本数 x
        if denom <= 0:
            return 0
        
        avg_daily = change / denom
        
        if avg_daily <= 0:
            # 无增长或负增长时不做估算，返回 0
            return 0
        
        remaining = max(0, self.total - newest_val)
        remaining_days = max(1, round(remaining / avg_daily))
        return remaining_days
    
    # 保留 estimated_date 的原有实现（不修改）
    @property
    def estimated_date(self):
        """基于过去7天记录预测完成日期（包含所有日期）"""
        # 如果没有子任务，返回N/A
        if not self.sub_tasks:
            return "N/A"
        
        # 获取当前日期
        now = datetime.now()
        
        # 收集所有记录日期
        all_dates = set()
        for st in self.sub_tasks:
            all_dates.update(st.records.keys())
        
        # 如果没有记录，返回N/A
        if not all_dates:
            return "N/A"
        
        # 转换日期并排序
        sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d") for d in all_dates])
        min_date = min(sorted_dates)
        max_date = max(sorted_dates)
        
        # 确定开始日期（7天前或第一次记录日期）
        start_date = max(min_date, now - timedelta(days=7))
        
        # 计算开始日期和结束日期的总完成量
        start_completion = 0
        end_completion = 0
        
        for st in self.sub_tasks:
            # 获取开始日期前的最后记录
            start_records = [p for d, p in st.records.items() 
                            if datetime.strptime(d, "%Y-%m-%d") <= start_date]
            start_completion += max(start_records) if start_records else 0
            
            # 获取当前完成量
            end_completion += st.completed
        
        # 计算时间跨度（自然日）
        days_span = (now - start_date).days
        if days_span <= 0:
            return "N/A"
        
        # 计算平均日增量
        total_increase = end_completion - start_completion
        avg_daily = total_increase / days_span
        
        # 计算剩余量
        remaining = max(0, self.total - end_completion)
        
        if avg_daily <= 0:
            return "N/A"
        
        # 计算剩余天数
        remaining_days = max(1, round(remaining / avg_daily))
        
        # 预计完成日期 = 当前日期 + 剩余天数
        return (now + timedelta(days=remaining_days)).strftime("%Y-%m-%d")
    
    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "start_date": self.start_date,
            "sub_tasks": [st.to_dict() for st in self.sub_tasks]
        }
    
    @classmethod
    def from_dict(cls, data):
        task = cls(data.get("name", ""))
        task.status = data.get("status", "进行中")
        task.start_date = data.get("start_date", datetime.now().strftime("%Y-%m-%d"))
        task.sub_tasks = [SubTask.from_dict(st) for st in data.get("sub_tasks", [])]
        return task

class TaskCard(QWidget):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.parent = parent
        
        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled_size(10), scaled_size(10), scaled_size(10), scaled_size(10)
        )
        layout.setSpacing(scaled_size(15))
        
        # 任务名称和状态
        header_layout = QHBoxLayout()
        self.name_label = QLabel(task.name)
        self.status_label = QLabel(task.status)
        self.status_label.setStyleSheet(f"font-family: \"黑体\", sans-serif; color: {Task.STATUS_COLORS.get(task.status, QColor(0,0,0)).name()}; font-size: 19px;")
        
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(round(task.progress))
        self.progress_bar.setFormat(f" {task.progress:.2f}%")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
            font-size:16px;
            }}
            QProgressBar::chunk {{
                background-color: {Task.STATUS_COLORS.get(task.status, QColor(0,0,0)).name()};
            }}
        """)
        
        # 任务信息（剩余天数和预计完成日期）
        info_layout = QHBoxLayout()
        
        days_text = f"剩余天数: {task.remaining_days}天 | 预计完成: {task.estimated_date}"
        self.days_info = QLabel(days_text)
        self.days_info.setStyleSheet("font-size: 14px; color: #000;")
        
        info_layout.addWidget(self.days_info)
        info_layout.addStretch()
        
        # 添加到主布局
        layout.addLayout(header_layout)
        layout.addWidget(self.progress_bar)
        layout.addLayout(info_layout)
        
        self.setLayout(layout)
        self.setMinimumHeight(scaled_size(100))
        self.setStyleSheet("""
            TaskCard {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #ddd;
            }
            TaskCard:hover {
                border: 1px solid #aaa;
            }
        """)

        # 初始化时更新一次显示
        self.update_task(task)
        
    def update_task(self, task):
        """更新卡片显示的任务数据"""
        self.task = task
        self.name_label.setText(task.name)
        self.name_label.setStyleSheet(f"font-family: \"黑体\", sans-serif; font-weight: bold; font-size: {scaled_font_size(20)}px;")
        self.name_label.setWordWrap(True)

        self.status_label.setText(task.status)
        self.status_label.setStyleSheet(f"font-family: \"黑体\", sans-serif; color: {Task.STATUS_COLORS.get(task.status, QColor(0,0,0)).name()}; font-size: 19px;")
        self.progress_bar.setValue(round(task.progress))
        self.progress_bar.setFormat(f" {task.progress:.2f}%")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
            font-size: {scaled_font_size(16)}px;
            height: {scaled_size(25)}px;
            }}
            QProgressBar::chunk {{
                background-color: {Task.STATUS_COLORS.get(task.status, QColor(0,0,0)).name()};
            }}
        """)
        
        # 更新剩余天数和预计完成日期（remaining_days 会使用 Task.RECENT_X）
        days_text = f"剩余天数: {task.remaining_days}天 | 预计完成: {task.estimated_date}"
        self.days_info.setText(days_text)
        self.days_info.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #000;")

# --- 新增：子任务卡片，显式提供合理的 sizeHint，确保选中框能完整包裹内容 ---
class SubTaskCard(QWidget):
    def __init__(self, subtask: SubTask, parent=None):
        super().__init__(parent)
        self.subtask = subtask
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(scaled_size(12), scaled_size(8), scaled_size(12), scaled_size(10))
        layout.setSpacing(scaled_size(8))

        self.name_label = QLabel(subtask.name)
        self.name_label.setStyleSheet(
            f"font-family: \"黑体\", sans-serif; font-weight: bold; font-size: {scaled_font_size(14)}px;"
        )
        self.name_label.setWordWrap(True)

        progress = (subtask.completed / subtask.total * 100) if subtask.total > 0 else 0
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(round(progress))
        self.progress_bar.setFormat(f"{progress:.2f}% ({subtask.completed}/{subtask.total})")
        # 稍微加高，便于触控与可读性
        self.progress_bar.setFixedHeight(scaled_size(26))
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ font-size: {scaled_font_size(13)}px; height: {scaled_size(26)}px; }}"
        )

        layout.addWidget(self.name_label)
        layout.addWidget(self.progress_bar)

        # 让 QListWidget 的选中高亮透出（本卡片背景透明）
        self.setStyleSheet("background: transparent;")

        # 调整尺寸策略，保证以内容高度为准
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def update_subtask(self, subtask: SubTask):
        self.subtask = subtask
        self.name_label.setText(subtask.name)
        progress = (subtask.completed / subtask.total * 100) if subtask.total > 0 else 0
        self.progress_bar.setValue(round(progress))
        self.progress_bar.setFormat(f"{progress:.2f}% ({subtask.completed}/{subtask.total})")
        self.updateGeometry()

    def sizeHint(self):
        # 显式返回足够的高度，确保选中框覆盖 name + progress + 内边距
        name_h = self.name_label.sizeHint().height()
        pb_h = max(self.progress_bar.sizeHint().height(), scaled_size(26))
        margins = scaled_size(8) + scaled_size(10) + scaled_size(8)  # top + bottom + 中间间距
        h = name_h + pb_h + margins + scaled_size(6)  # 额外余量
        # 宽度可交给视图自行计算
        return QSize(scaled_size(300), h)

class ProgressManager(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- 新增：存储原始缩放因子 ---
        self.base_scaling_factor = get_base_scaling_factor()
        global SCALING_FACTOR
        SCALING_FACTOR = self.base_scaling_factor

        self.setWindowTitle("任务进度管理器 by TZYLT&QianXiquq")
        self.setGeometry(100, 100, scaled_size(1200), scaled_size(800))
        self.tasks = []
        self.current_task = None
        self.current_subtask = None
        self.data_file = "tasks.json"
        self.config_file = "config.json"
        # recent_x 控制“取最近 x 次记录”用于剩余天数估算
        self.recent_x = Task.RECENT_X  # 默认值与 Task 保持一致

        # 先加载配置（以便 RECENT_X 可用）
        self.load_config()

        # 添加全屏快捷键
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)

        self.load_data()
        self.init_ui()
    
    def toggle_fullscreen(self):
        """
        切换全屏模式，并在切换后根据状态重新计算和应用UI缩放
        """
        is_entering_fullscreen = not self.isFullScreen()

        if is_entering_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

        # 根据新状态更新并应用UI样式
        self.update_and_apply_styles(is_fullscreen=is_entering_fullscreen)

    def update_and_apply_styles(self, is_fullscreen):
        """
        计算新的缩放因子，并刷新整个UI以应用新尺寸和字体大小
        """
        global SCALING_FACTOR
        if is_fullscreen:
            # 进入全屏时，放大UI
            SCALING_FACTOR = self.base_scaling_factor * 1.25
        else:
            # 退出全屏时，恢复原始DPI缩放
            SCALING_FACTOR = self.base_scaling_factor
        
        # 保存当前选中的任务索引
        current_index = self.task_list.currentRow()
        
        # 重新应用所有样式和尺寸
        self.apply_styles()
        
        # 重新填充任务列表（这将使用新的缩放因子创建TaskCard）
        self.populate_task_list()
        
        # 恢复之前的选中状态
        if current_index >= 0 and current_index < self.task_list.count():
            self.task_list.setCurrentRow(current_index)
        
        # 刷新详情和图表视图
        self.update_detail_view()
        self.update_chart()

    # ---------- 配置持久化 ----------
    def load_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self.recent_x = int(cfg.get("recent_x", self.recent_x))
        except Exception:
            # 若读取失败则保持默认
            self.recent_x = getattr(self, "recent_x", Task.RECENT_X)
        # 将配置同步到 Task.RECENT_X（使 Task.remaining_days 使用此值）
        try:
            Task.RECENT_X = int(self.recent_x)
        except Exception:
            Task.RECENT_X = Task.RECENT_X
    
    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"recent_x": int(self.recent_x)}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    # ---------- 数据加载/保存 ----------
    def load_data(self):
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [Task.from_dict(t) for t in data]
        except FileNotFoundError:
            self.tasks = []
        except Exception:
            self.tasks = []
    
    def save_data(self):
        data = [t.to_dict() for t in self.tasks]
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        
        # 左侧任务列表
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        self.task_list = QListWidget()
        self.task_list.itemSelectionChanged.connect(self.on_task_selected)
        
        # 添加任务按钮
        self.add_task_btn = QPushButton("添加新任务")
        self.add_task_btn.clicked.connect(self.add_new_task)
        
        self.task_list_label = QLabel("任务列表")
        left_layout.addWidget(self.task_list_label)
        left_layout.addWidget(self.task_list)
        left_layout.addWidget(self.add_task_btn)
        left_panel.setLayout(left_layout)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # 模式切换与控制按钮行
        mode_layout = QHBoxLayout()
        self.mode_label = QLabel("显示模式:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["详细信息", "图表分析"])
        self.mode_combo.currentIndexChanged.connect(self.switch_mode)
        
        self.today_summary_btn = QPushButton("今日总结")
        self.today_summary_btn.setToolTip("显示今日有更新的任务总结")
        self.today_summary_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.today_summary_btn.clicked.connect(self.show_today_summary)
        
        # 设置按钮：用于修改 recent_x（顶部设置面板按钮）
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setToolTip("剩余天数计算的最近记录次数")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.today_summary_btn)
        mode_layout.addWidget(self.settings_btn)
        mode_layout.addStretch()
        
        # 堆叠窗口
        self.stacked_widget = QStackedWidget()
        
        # 详细信息模式
        self.detail_widget = QWidget()
        self.init_detail_ui()
        self.stacked_widget.addWidget(self.detail_widget)
        
        # 图表模式
        self.chart_widget = QWidget()
        self.init_chart_ui()
        self.stacked_widget.addWidget(self.chart_widget)
        
        right_layout.addLayout(mode_layout)
        right_layout.addWidget(self.stacked_widget)
        right_panel.setLayout(right_layout)
        
        # 主布局
        main_layout.addWidget(left_panel, 30)
        main_layout.addWidget(right_panel, 70)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 设置任务列表右键菜单
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_task_context_menu)

        # 首次加载时应用样式和填充列表
        self.apply_styles()
        self.populate_task_list()

    def apply_styles(self):
        """
        一个集中的方法，用于设置所有UI组件的样式和尺寸。
        这样可以在缩放因子变化后统一刷新界面。
        """
        # --- 全局字体 ---
        app_font = QApplication.instance().font()
        app_font.setPointSize(scaled_font_size(10))
        QApplication.instance().setFont(app_font)

        # --- 左侧面板 ---
        self.task_list_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px; font-weight: bold;")
        self.task_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #f0f2f5;
                border: none;
                border-radius: 8px;
                padding: 5px;
                font-size: {scaled_font_size(14)}px;
            }}
            QListWidget::item {{
                border-bottom: 1px solid #dee2e6;
            }}
            QListWidget::item:selected {{
                background-color: #e2e6ea;
            }}
        """)
        self.add_task_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #4CAF50; color: white; border: none;
                padding: {scaled_size(8)}px; border-radius: 4px;
                font-weight: bold; font-size: {scaled_font_size(14)}px;
            }}
            QPushButton:hover {{ background-color: #45a049; }}
        """)

        # --- 右侧面板 ---
        self.mode_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.mode_combo.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.today_summary_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #1976D2; color: white; border: none;
                padding: {scaled_size(6)}px {scaled_size(10)}px;
                border-radius: 4px; font-size: {scaled_font_size(14)}px;
            }}
            QPushButton:hover {{ background-color: #145a9e; }}
        """)
        
        # --- 详细信息视图 ---
        self.detail_widget.layout().setSpacing(scaled_size(15))
        self.task_overview.setStyleSheet(f"QGroupBox {{ font-size: {scaled_font_size(16)}px; font-weight: bold; }}")
        self.task_name_label.setStyleSheet(f"font-family: \"黑体\", sans-serif; font-size: {scaled_font_size(18)}px; font-weight: bold;")
        self.task_progress_bar.setStyleSheet(f"""
            QProgressBar {{ font-size: {scaled_font_size(16)}px; height: {scaled_size(25)}px; }}
        """)
        self.task_info_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #555;")
        self.subtask_list_label.setStyleSheet(f"font-size: {scaled_font_size(16)}px; font-weight: bold;")
        # 关键：子任务列表的选中高亮更明显 + 行距更大，避免选中框过小
        self.subtask_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #f8f9fa; border: 1px solid #dee2e6;
                border-radius: 8px; font-size: {scaled_font_size(14)}px;
            }}
            QListWidget::item {{
                padding: {scaled_size(6)}px {scaled_size(8)}px;
            }}
            QListWidget::item:selected {{
                background-color: #d0e7ff; /* 更明显的选中底色 */
                border-radius: {scaled_size(6)}px;
            }}
        """)
        self.subtask_list.setSpacing(scaled_size(6))
        self.subtask_list.setUniformItemSizes(False)
        self.subtask_list.setSelectionMode(QAbstractItemView.SingleSelection)

        self.progress_group.setStyleSheet(f"QGroupBox {{ font-size: {scaled_font_size(16)}px; font-weight: bold; }}")
        self.subtask_name_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.date_edit.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.date_edit.setFixedHeight(scaled_size(30))
        self.progress_input.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.progress_input.setFixedHeight(scaled_size(30))
        self.offset_input.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.offset_input.setFixedHeight(scaled_size(30))
        self.register_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #4CAF50; color: white;
                font-size: {scaled_font_size(14)}px; padding: {scaled_size(8)}px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: #45a049; }}
        """)
        self.register_btn.setFixedHeight(scaled_size(40))

        # --- 图表视图 ---
        self.chart_widget.layout().setSpacing(scaled_size(15))
        self.chart_type_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        self.chart_type_combo.setStyleSheet(f"font-size: {scaled_font_size(14)}px;")
        
    def populate_task_list(self):
        self.task_list.clear()
        for task in self.tasks:
            item = QListWidgetItem()
            widget = TaskCard(task, parent=self)
            item.setSizeHint(widget.sizeHint())
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, widget)
    
    def init_detail_ui(self):
        layout = QVBoxLayout()
        
        # 任务概览
        self.task_overview = QGroupBox("任务概览")
        overview_layout = QVBoxLayout()
        
        self.task_name_label = QLabel("")
        self.task_progress_bar = QProgressBar()
        self.task_progress_bar.setRange(0, 100)
        self.task_info_label = QLabel("")
        
        overview_layout.addWidget(self.task_name_label)
        overview_layout.addWidget(self.task_progress_bar)
        overview_layout.addWidget(self.task_info_label)
        self.task_overview.setLayout(overview_layout)
        
        # 子任务列表
        self.subtask_list_label = QLabel("子任务列表")
        self.subtask_list = QListWidget()
        self.subtask_list.itemSelectionChanged.connect(self.on_subtask_selected)
        # 为子任务列表启用右键菜单（最小改动）
        self.subtask_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.subtask_list.customContextMenuRequested.connect(self.show_subtask_context_menu)
        
        # 进度登记
        self.progress_group = QGroupBox("进度登记")
        progress_layout = QFormLayout()
        progress_layout.setLabelAlignment(Qt.AlignRight)
        progress_layout.setFormAlignment(Qt.AlignHCenter | Qt.AlignTop)
        
        self.subtask_name_label = QLabel("选择子任务")
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.progress_input = QSpinBox()
        self.progress_input.setRange(0, 100000)
        self.offset_input = QSpinBox()
        self.offset_input.setRange(-1000, 1000)
        self.register_btn = QPushButton("登记进度")
        self.register_btn.clicked.connect(self.register_progress)
        
        progress_layout.addRow(QLabel("子任务:"), self.subtask_name_label)
        progress_layout.addRow(QLabel("日期:"), self.date_edit)
        progress_layout.addRow(QLabel("进度值:"), self.progress_input)
        progress_layout.addRow(QLabel("自动偏移:"), self.offset_input)
        progress_layout.addRow("", self.register_btn)
        self.progress_group.setLayout(progress_layout)
        
        layout.addWidget(self.task_overview)
        layout.addWidget(self.subtask_list_label)
        layout.addWidget(self.subtask_list, 50)
        layout.addWidget(self.progress_group, 30)
        self.detail_widget.setLayout(layout)
    
    def init_chart_ui(self):
        layout = QVBoxLayout()
        
        # 图表类型选择
        chart_type_layout = QHBoxLayout()
        self.chart_type_label = QLabel("图表模式:")
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["总量模式", "增量模式"])
        self.chart_type_combo.currentIndexChanged.connect(self.update_chart)
        
        chart_type_layout.addWidget(self.chart_type_label)
        chart_type_layout.addWidget(self.chart_type_combo)
        chart_type_layout.addStretch()
        
        # 图表视图
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        
        layout.addLayout(chart_type_layout)
        layout.addWidget(self.chart_view)
        self.chart_widget.setLayout(layout)
    
    def on_task_selected(self):
        selected_items = self.task_list.selectedItems()
        if not selected_items:
            self.current_task = None
            return
        
        idx = self.task_list.row(selected_items[0])
        if 0 <= idx < len(self.tasks):
            self.current_task = self.tasks[idx]
        else:
            self.current_task = None
        self.update_detail_view()
    
    def refresh_task_cards(self):
        """刷新所有任务卡片"""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget and i < len(self.tasks):
                widget.update_task(self.tasks[i])

    def refresh_current_task_card(self):
        """刷新当前选中的任务卡片"""
        selected_items = self.task_list.selectedItems()
        if not selected_items:
            return
        
        idx = self.task_list.row(selected_items[0])
        item = self.task_list.item(idx)
        widget = self.task_list.itemWidget(item)
        if widget:
            widget.update_task(self.current_task)

    def select_current_task_in_list(self):
        """确保当前任务在列表中被选中"""
        if self.current_task is None:
            return
        for i in range(len(self.tasks)):
            if self.tasks[i].name == self.current_task.name:
                self.task_list.setCurrentRow(i)
                break

    def update_detail_view(self):
        if not self.current_task:
            self.task_name_label.setText("")
            self.task_progress_bar.setValue(0)
            self.task_info_label.setText("")
            self.subtask_list.clear()
            self.subtask_name_label.setText("选择子任务")
            return
        
        # 更新任务概览
        self.task_name_label.setText(self.current_task.name)
        self.task_progress_bar.setValue(round(self.current_task.progress))
        self.task_progress_bar.setFormat(f"{self.current_task.progress:.2f}%")
        # 在显示预计完成时，使用 self.recent_x（用户设置）—— estimated_date 保持不变
        est_date = self.current_task.estimated_date
        self.task_info_label.setText(
            f"状态: {self.current_task.status} | 剩余天数: {self.current_task.remaining_days} | "
            f"预计完成: {est_date}"
        )
        
        # 更新子任务列表（使用 SubTaskCard，显式设置足够的 sizeHint）
        self.subtask_list.clear()
        for subtask in self.current_task.sub_tasks:
            item = QListWidgetItem()
            widget = SubTaskCard(subtask)
            # 关键：使用卡片的 sizeHint 确定行高，确保选中框覆盖全部组件
            item.setSizeHint(widget.sizeHint())
            self.subtask_list.addItem(item)
            self.subtask_list.setItemWidget(item, widget)
    
        # 更新图表
        self.update_chart()
        
        # 刷新当前任务卡片
        self.refresh_current_task_card()
    
    def on_subtask_selected(self):
        selected_items = self.subtask_list.selectedItems()
        if not selected_items or not self.current_task:
            self.current_subtask = None
            self.subtask_name_label.setText("选择子任务")
            return
        
        idx = self.subtask_list.row(selected_items[0])
        if 0 <= idx < len(self.current_task.sub_tasks):
            self.current_subtask = self.current_task.sub_tasks[idx]
            self.subtask_name_label.setText(self.current_subtask.name)
            self.offset_input.setValue(self.current_subtask.auto_offset)
        else:
            self.current_subtask = None
            self.subtask_name_label.setText("选择子任务")
    
    def register_progress(self):
        if not self.current_task or not self.current_subtask:
            QMessageBox.warning(self, "错误", "请先选择任务和子任务")
            return
        
        date = self.date_edit.date().toString("yyyy-MM-dd")
        progress = self.progress_input.value() - self.offset_input.value()
        self.current_subtask.add_record(date, progress)
        self.current_subtask.auto_offset = self.offset_input.value()
        
        self.save_data()
        self.update_detail_view()
        self.refresh_current_task_card()
    
    def switch_mode(self, index):
        self.stacked_widget.setCurrentIndex(index)
        if index == 1:  # 图表模式
            self.update_chart()
        
    def update_chart(self):
        if not self.current_task:
            self.chart_view.setChart(QChart())
            return
        
        chart = QChart()
        chart.setTitle(f"{self.current_task.name} - 进度分析")
        chart.legend().setVisible(True)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # 设置标题/图例/坐标轴字体大小以配合缩放
        font = chart.titleFont()
        font.setPointSize(scaled_font_size(16))
        chart.setTitleFont(font)
        legend_font = chart.legend().font()
        legend_font.setPointSize(scaled_font_size(12))
        chart.legend().setFont(legend_font)
        
        axisX = QDateTimeAxis()
        axisX.setFormat("yyyy-MM-dd")
        axisX.setTitleText("日期")
        
        axisY = QValueAxis()
        axisY.setTitleText("进度 (%)")
        
        axis_font = axisX.labelsFont()
        axis_font.setPointSize(scaled_font_size(10))
        axisX.setLabelsFont(axis_font)
        axisY.setLabelsFont(axis_font)
        title_font = axisX.titleFont()
        title_font.setPointSize(scaled_font_size(12))
        axisX.setTitleFont(title_font)
        axisY.setTitleFont(title_font)
        
        chart_mode = self.chart_type_combo.currentText()
        
        all_dates = set()
        for subtask in self.current_task.sub_tasks:
            all_dates.update(subtask.records.keys())
        
        if not all_dates:
            self.chart_view.setChart(chart)
            return
        
        sorted_dates = sorted(all_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
        date_objs = [datetime.strptime(d, "%Y-%m-%d") for d in sorted_dates]
        min_date = min(date_objs)
        max_date = max(date_objs)
        
        axisX.setRange(min_date, max_date + timedelta(days=1))
        
        total_series = QLineSeries()
        total_series.setName("总进度")
        total_series.setColor(QColor(0, 0, 0))
        total_series.setPointsVisible(True)
        
        subtask_series = []
        for i, subtask in enumerate(self.current_task.sub_tasks):
            series = QLineSeries()
            color = QColor(
                random.randint(50, 200),
                random.randint(50, 200),
                random.randint(50, 200)
            )
            series.setName(subtask.name)
            series.setColor(color)
            series.setPointsVisible(True)
            subtask_series.append(series)
        
        current_subtask_progress = [0] * len(self.current_task.sub_tasks)
        
        if chart_mode == "增量模式":
            prev_total_progress = 0
            prev_subtask_progress = [0] * len(self.current_task.sub_tasks)
            max_increment_value = 0
            
            for date in sorted_dates:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                timestamp = date_obj.timestamp() * 1000
                
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    if date in subtask.records:
                        current_subtask_progress[i] = min(subtask.records[date], subtask.total)
                
                total_completed = sum(current_subtask_progress)
                total_required = sum(subtask.total for subtask in self.current_task.sub_tasks)
                total_progress = (total_completed / total_required * 100) if total_required > 0 else 0
                
                total_delta = total_progress - prev_total_progress
                total_series.append(timestamp, max(0, total_delta))
                prev_total_progress = total_progress
                
                max_increment_value = max(max_increment_value, max(0, total_delta))
                
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    subtask_percent = (current_subtask_progress[i] / subtask.total * 100) if subtask.total > 0 else 0
                    delta = subtask_percent - prev_subtask_progress[i]
                    delta_value = max(0, delta)
                    subtask_series[i].append(timestamp, delta_value)
                    prev_subtask_progress[i] = subtask_percent
                    max_increment_value = max(max_increment_value, delta_value)
            
            upper_bound = max_increment_value * 1.2 if max_increment_value > 0 else 10
            axisY.setRange(0, upper_bound)
            axisY.setTickCount(6)
        else:
            for date in sorted_dates:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                timestamp = date_obj.timestamp() * 1000
                
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    if date in subtask.records:
                        current_subtask_progress[i] = min(subtask.records[date], subtask.total)
                
                total_completed = sum(current_subtask_progress)
                total_required = sum(subtask.total for subtask in self.current_task.sub_tasks)
                total_progress = (total_completed / total_required * 100) if total_required > 0 else 0
                total_series.append(timestamp, total_progress)
                
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    progress = current_subtask_progress[i]
                    percent = (progress / subtask.total * 100) if subtask.total > 0 else 0
                    subtask_series[i].append(timestamp, percent)
            
            axisY.setRange(0, 100)
            axisY.setTickCount(11)
        
        chart.addSeries(total_series)
        for series in subtask_series:
            chart.addSeries(series)
        
        chart.addAxis(axisX, Qt.AlignBottom)
        chart.addAxis(axisY, Qt.AlignLeft)
        
        for series in [total_series] + subtask_series:
            series.attachAxis(axisX)
            series.attachAxis(axisY)
        
        self.chart_view.setChart(chart)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self.add_data_labels)

    def add_data_labels(self):
        chart = self.chart_view.chart()
        if not chart:
            return
        scene = self.chart_view.scene()
        if not scene:
            return
        # 清除现有标签
        for item in list(scene.items()):
            if isinstance(item, QGraphicsSimpleTextItem):
                scene.removeItem(item)
        series_list = chart.series()
        if not series_list:
            return
        for series in series_list:
            try:
                points = series.pointsVector()
            except Exception:
                continue
            for point in points:
                scene_point = chart.mapToPosition(point)
                value_text = f"{point.y():.2f}"
                label = QGraphicsSimpleTextItem(value_text)
                label_x = scene_point.x() + 5
                label_y = scene_point.y() - 15
                plot_area = chart.plotArea()
                if label_y < plot_area.top():
                    label_y = scene_point.y() + 10
                label.setPos(label_x, label_y)
                label.setBrush(QColor(0, 0, 0))
                font = label.font()
                font.setPointSize(scaled_font_size(8))
                label.setFont(font)
                scene.addItem(label)

    def show_task_context_menu(self, pos):
        item = self.task_list.itemAt(pos)
        if not item: return
        
        idx = self.task_list.row(item)
        task = self.tasks[idx]
        
        menu = QMenu()
        menu.setStyleSheet(f"QMenu {{ font-size: {scaled_font_size(14)}px; }}")
        
        status_menu = QMenu("更改状态")
        status_menu.setStyleSheet(f"QMenu {{ font-size: {scaled_font_size(14)}px; }}")
        for status in ["进行中", "暂停", "废止"]:
            action = status_menu.addAction(status)
            action.triggered.connect(lambda _, s=status, t=task: self.change_task_status(t, s))
        menu.addMenu(status_menu)
        
        rename_action = menu.addAction("重命名")
        rename_action.triggered.connect(lambda _, t=task: self.rename_task(t))
        
        add_sub_action = menu.addAction("添加子任务")
        add_sub_action.triggered.connect(lambda _, t=task: self.add_subtask(t))
        
        delete_action = menu.addAction("删除任务")
        delete_action.triggered.connect(lambda _, t=task: self.delete_task(t))
        
        menu.exec_(self.task_list.mapToGlobal(pos))
    
    def change_task_status(self, task, status):
        task.status = status
        self.save_data()
        self.populate_task_list()
        self.select_current_task_in_list()
        if task == self.current_task:
            self.update_detail_view()
    
    def rename_task(self, task):
        new_name, ok = QInputDialog.getText(
            self, "重命名任务", "输入新任务名称:", text=task.name
        )
        if ok and new_name:
            task.name = new_name
            self.save_data()
            self.populate_task_list()
            self.select_current_task_in_list()
            if task == self.current_task:
                self.update_detail_view()
    
    def add_subtask(self, task):
        name, ok = QInputDialog.getText(
            self, "添加子任务", "输入子任务名称:"
        )
        if ok and name:
            total, ok = QInputDialog.getInt(
                self, "设置总量", "输入任务总量:", value=100
            )
            if ok:
                task.add_subtask(SubTask(name, total))
                self.save_data()
                if task == self.current_task:
                    self.update_detail_view()
    
    def delete_task(self, task):
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除任务 '{task.name}' 及其所有子任务吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            was_current = (task == self.current_task)
            self.tasks.remove(task)
            if was_current:
                self.current_task = None
            self.save_data()
            self.populate_task_list()
            self.update_detail_view()
    
    def add_new_task(self):
        name, ok = QInputDialog.getText(
            self, "添加新任务", "输入任务名称:"
        )
        if ok and name:
            self.tasks.append(Task(name))
            self.save_data()
            self.populate_task_list()

    # ---------------- 今日总结（合并后的更完整实现） ----------------
    def show_today_summary(self):
        """弹出窗口显示今日有更新的任务总结，按指定格式显示"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        summary_lines = []
        
        for task in self.tasks:
            task_lines = []
            
            # 计算任务整体今日前后的完成量和百分比
            total_before = 0  # 今日之前的最新记录之和
            total_after = 0   # 包含今日的最新记录之和
            
            # 收集所有子任务的信息
            subtask_info = []
            
            for st in task.sub_tasks:
                # 获取今日之前的最新记录
                prev_records = []
                for d_str, val in st.records.items():
                    try:
                        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                        if d_obj < datetime.strptime(today_str, "%Y-%m-%d"):
                            prev_records.append((d_obj, val))
                    except Exception:
                        continue
                
                prev_val = 0
                if prev_records:
                    prev_records.sort(key=lambda x: x[0])
                    prev_val = prev_records[-1][1]
                
                # 获取包含今日的最新记录
                all_records = []
                for d_str, val in st.records.items():
                    try:
                        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                        if d_obj <= datetime.strptime(today_str, "%Y-%m-%d"):
                            all_records.append((d_obj, val))
                    except Exception:
                        continue
                
                curr_val = prev_val  # 默认使用之前的值
                if all_records:
                    all_records.sort(key=lambda x: x[0])
                    curr_val = all_records[-1][1]
                
                # 计算子任务百分比
                prev_percent = (min(prev_val, st.total) / st.total * 100) if st.total > 0 else 0
                curr_percent = (min(curr_val, st.total) / st.total * 100) if st.total > 0 else 0
                
                # 累加到任务总量
                total_before += min(prev_val, st.total)
                total_after += min(curr_val, st.total)
                
                # 检查子任务是否有今日更新
                if today_str in st.records:
                    change = max(0, st.records[today_str] - prev_val)
                    # 只有当有实际变化时才记录子任务
                    if change > 0 or abs(curr_percent - prev_percent) > 1e-6:
                        subtask_info.append({
                            'name': st.name,
                            'change': change,
                            'prev_percent': prev_percent,
                            'curr_percent': curr_percent
                        })
            
            # 计算任务整体百分比
            total_required = task.total if task.total > 0 else 1
            total_prev_percent = (total_before / total_required * 100)
            total_curr_percent = (total_after / total_required * 100)
            total_change = total_after - total_before
            
            # 检查任务是否有更新（有子任务更新或总量变化）
            if subtask_info or total_change > 0 or abs(total_curr_percent - total_prev_percent) > 1e-6:
                # 添加任务行
                task_line = f"{task.name} : {total_change}, {total_prev_percent:.2f}% -> {total_curr_percent:.2f}%"
                task_lines.append(task_line)
                
                # 添加子任务行（缩进显示）
                for info in subtask_info:
                    subtask_line = f"    {info['name']} : {info['change']}, {info['prev_percent']:.2f}% -> {info['curr_percent']:.2f}%"
                    task_lines.append(subtask_line)
                
                summary_lines.extend(task_lines)
                summary_lines.append("")  # 空行分隔不同任务
        
        # 弹窗显示
        dlg = QDialog(self)
        dlg.setWindowTitle("今日总结")
        dlg_layout = QVBoxLayout()
        
        if summary_lines:
            # 使用 QTextEdit 以便更好地显示格式化文本
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            # 构建格式化文本
            formatted_text = ""
            for line in summary_lines:
                if line.strip():  # 非空行
                    formatted_text += line + "\n"
                else:  # 空行
                    formatted_text += "\n"
            
            text_edit.setPlainText(formatted_text.strip())
            dlg_layout.addWidget(text_edit)
        else:
            dlg_layout.addWidget(QLabel("今日没有更新"))
        
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        dlg_layout.addWidget(btns)
        
        dlg.setLayout(dlg_layout)
        dlg.resize(700, 500)
        dlg.exec_()

    # ---------------- 子任务右键菜单及处理函数 ----------------
    def show_subtask_context_menu(self, pos):
        """在子任务列表右键时弹出菜单：重命名 / 修改总量 / 删除"""
        if not self.current_task:
            return
        item = self.subtask_list.itemAt(pos)
        if not item:
            return
        idx = self.subtask_list.row(item)
        if idx < 0 or idx >= len(self.current_task.sub_tasks):
            return
        st = self.current_task.sub_tasks[idx]
        
        menu = QMenu(self)
        rename_act = menu.addAction("重命名子任务")
        change_total_act = menu.addAction("修改任务总量")
        delete_act = menu.addAction("删除子任务")
        
        rename_act.triggered.connect(lambda _, t=self.current_task, i=idx: self.rename_subtask(t, i))
        change_total_act.triggered.connect(lambda _, t=self.current_task, i=idx: self.change_subtask_total(t, i))
        delete_act.triggered.connect(lambda _, t=self.current_task, i=idx: self.delete_subtask(t, i))
        
        menu.exec_(self.subtask_list.mapToGlobal(pos))
    
    def rename_subtask(self, task, idx):
        """重命名子任务"""
        try:
            st = task.sub_tasks[idx]
        except Exception:
            return
        new_name, ok = QInputDialog.getText(self, "重命名子任务", "输入新子任务名称：", text=st.name)
        if ok and new_name:
            st.name = new_name
            self.save_data()
            if task == self.current_task:
                self.update_detail_view()
            self.refresh_task_cards()
    
    def change_subtask_total(self, task, idx):
        """修改子任务总量"""
        try:
            st = task.sub_tasks[idx]
        except Exception:
            return
        new_total, ok = QInputDialog.getInt(self, "修改任务总量", "输入新的总量：", value=st.total, min=0)
        if ok:
            st.total = new_total
            self.save_data()
            if task == self.current_task:
                self.update_detail_view()
            self.refresh_task_cards()
    
    def delete_subtask(self, task, idx):
        """删除子任务（带确认）"""
        try:
            st = task.sub_tasks[idx]
        except Exception:
            return
        reply = QMessageBox.question(self, "确认删除", f"确定要删除子任务 '{st.name}' 吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # 若当前选中是该子任务，清空 current_subtask
            if self.current_subtask is not None and self.current_subtask == st:
                self.current_subtask = None
                self.subtask_name_label.setText("选择子任务")
            task.sub_tasks.pop(idx)
            self.save_data()
            if task == self.current_task:
                self.update_detail_view()
            self.refresh_task_cards()

    # ---------- 设置对话框（改为可放多个设置项的面板，当前仅一个 x 输入框） ----------
    def open_settings_dialog(self):
        """
        弹出一个完整的设置面板（QDialog），面板使用 QFormLayout 放置多个设置项。
        现在只放置一个：最近记录次数 x 的输入控件，但布局支持放更多控件。
        修改后会同步保存配置并刷新界面中显示的剩余天数。
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("设置")
        dlg_layout = QVBoxLayout(dlg)

        # 使用滚动区承载内容（便于未来放很多设置项）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form_layout = QFormLayout()
        content.setLayout(form_layout)
        scroll.setWidget(content)

        # 最近记录次数 x（QSpinBox）
        x_spin = QSpinBox()
        x_spin.setRange(1, 365)
        x_spin.setValue(int(self.recent_x) if hasattr(self, "recent_x") else int(Task.RECENT_X))
        form_layout.addRow(QLabel("剩余天数计算的最近记录次数："), x_spin)

        dlg_layout.addWidget(scroll)

        # 对话框按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dlg_layout.addWidget(btns)

        # 连接信号
        def on_accept():
            # 保存之前的当前任务/子任务引用（用于恢复选择）
            prev_task = self.current_task
            prev_subtask = self.current_subtask

            new_x = int(x_spin.value())
            self.recent_x = new_x
            # 同步到 Task.RECENT_X（使所有 Task.remaining_days 使用新值）
            Task.RECENT_X = new_x
            self.save_config()

            # 重新生成左侧任务列表（可能会清除选择），但我们会尝试恢复之前的选择
            self.populate_task_list()

            # 如果之前有选中的任务，恢复它在列表中的选中状态
            if prev_task is not None:
                # 保证 current_task 引用仍指向原对象
                # 将 self.current_task 指为 prev_task 然后选择对应项
                self.current_task = prev_task
                self.select_current_task_in_list()

            # 现在刷新右侧详情（此时子任务列表会根据 current_task 重建）
            self.update_detail_view()

            # 如果之前选择了某个子任务，尝试恢复子任务的选中（通过匹配对象引用）
            if prev_task is not None and prev_subtask is not None and self.current_task == prev_task:
                try:
                    idx = self.current_task.sub_tasks.index(prev_subtask)
                    if 0 <= idx < self.subtask_list.count():
                        # 设置子任务选择行，会触发 on_subtask_selected()
                        self.subtask_list.setCurrentRow(idx)
                except ValueError:
                    # 之前的子任务可能被删除或索引改变，忽略恢复
                    pass

            # 刷新左侧卡片样式/数据
            self.refresh_task_cards()

            dlg.accept()

        def on_reject():
            dlg.reject()

        btns.accepted.connect(on_accept)
        btns.rejected.connect(on_reject)

        dlg.resize(480, 320)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 初始设置缩放因子，之后将由 ProgressManager 控制
    SCALING_FACTOR = get_base_scaling_factor()
    
    window = ProgressManager()
    window.show()
    sys.exit(app.exec_())
