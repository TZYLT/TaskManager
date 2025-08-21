import sys
import json
import random
from datetime import datetime, timedelta
from collections import defaultdict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QProgressBar, QPushButton, QStackedWidget, QLineEdit, QFormLayout, QMenu,
    QAction, QMessageBox, QGroupBox, QComboBox, QDateEdit, QSpinBox, QInputDialog, QGraphicsSimpleTextItem,
    QDialog, QDialogButtonBox, QShortcut
)
# 修正：从 QtCore 导入 QMargins
from PyQt5.QtCore import Qt, QDate, QMargins
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
        if not self.records: return 0
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
        subtask = cls(data["name"], data["total"], data.get("auto_offset", 0))
        subtask.records = {k: v for k, v in data["records"].items()}
        return subtask

class Task:
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
        """基于最近5天有记录的数据预测剩余天数（忽略无记录日）"""
        if not self.sub_tasks: 
            return 0
        
        all_records = []
        for st in self.sub_tasks:
            for date, progress in st.records.items():
                all_records.append((datetime.strptime(date, "%Y-%m-%d"), progress))
        
        if not all_records: 
            return 0
        
        all_records.sort(key=lambda x: x[0])
        last_date = all_records[-1][0]
        
        recent_records = []
        for record_date, progress in all_records:
            if (last_date - record_date).days <= 5:
                recent_records.append((record_date, progress))
        
        if len(recent_records) < 2:
            return 0
        
        total_increase = recent_records[-1][1] - recent_records[0][1]
        date_span = (recent_records[-1][0] - recent_records[0][0]).days
        if date_span == 0:
            return 0
        
        avg_daily = total_increase / date_span
        remaining = max(0, self.total - self.completed)
        
        return max(1, round(remaining / avg_daily)) if avg_daily > 0 else 0
    
    @property
    def estimated_date(self):
        """基于过去7天记录预测完成日期（包含所有日期）"""
        if not self.sub_tasks:
            return "N/A"
        
        now = datetime.now()
        
        all_dates = set()
        for st in self.sub_tasks:
            all_dates.update(st.records.keys())
        
        if not all_dates:
            return "N/A"
        
        sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d") for d in all_dates])
        min_date = min(sorted_dates)
        
        start_date = max(min_date, now - timedelta(days=7))
        
        start_completion = 0
        end_completion = 0
        
        for st in self.sub_tasks:
            start_records = [p for d, p in st.records.items() 
                            if datetime.strptime(d, "%Y-%m-%d") <= start_date]
            start_completion += max(start_records) if start_records else 0
            
            end_completion += st.completed
        
        days_span = (now - start_date).days
        if days_span <= 0:
            return "N/A"
        
        total_increase = end_completion - start_completion
        avg_daily = total_increase / days_span
        
        remaining = max(0, self.total - end_completion)
        
        if avg_daily <= 0:
            return "N/A"
        
        remaining_days = max(1, round(remaining / avg_daily))
        
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
        task = cls(data["name"])
        task.status = data["status"]
        task.start_date = data.get("start_date", datetime.now().strftime("%Y-%m-%d"))
        task.sub_tasks = [SubTask.from_dict(st) for st in data["sub_tasks"]]
        return task

# ==================== UI现代化修改：TaskCard ====================
class TaskCard(QWidget):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.parent = parent
        
        layout = QVBoxLayout()
        layout.setContentsMargins(
            scaled_size(15), scaled_size(15), scaled_size(15), scaled_size(15)
        )
        layout.setSpacing(scaled_size(12))
        
        header_layout = QHBoxLayout()
        self.name_label = QLabel(task.name)
        self.status_label = QLabel(task.status)
        
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        
        info_layout = QHBoxLayout()
        self.days_info = QLabel()
        
        info_layout.addWidget(self.days_info)
        info_layout.addStretch()
        
        layout.addLayout(header_layout)
        layout.addWidget(self.progress_bar)
        layout.addLayout(info_layout)
        
        self.setLayout(layout)
        self.setMinimumHeight(scaled_size(120))
        # 关键修改：应用现代化圆角样式
        self.setStyleSheet("""
            TaskCard {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            TaskCard:hover {
                border: 1px solid #c0c0c0;
            }
        """)

        self.update_task(task)
        
    def update_task(self, task):
        self.task = task
        self.name_label.setText(task.name)
        self.name_label.setStyleSheet(f"""
            font-family: "Microsoft YaHei UI", sans-serif; 
            font-weight: bold; 
            font-size: {scaled_font_size(18)}px;
            color: #333;
        """)
        self.name_label.setWordWrap(True)

        self.status_label.setText(task.status)
        self.status_label.setStyleSheet(f"""
            font-family: "Microsoft YaHei UI", sans-serif; 
            color: {Task.STATUS_COLORS[task.status].name()}; 
            font-size: {scaled_font_size(16)}px;
            font-weight: bold;
            padding: {scaled_size(3)}px {scaled_size(8)}px;
            background-color: {Task.STATUS_COLORS[task.status].lighter(180).name()};
            border-radius: {scaled_size(8)}px;
        """)
        
        self.progress_bar.setValue(round(task.progress))
        self.progress_bar.setFormat(f" {task.progress:.2f}%")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                font-size: {scaled_font_size(14)}px;
                height: {scaled_size(22)}px;
                border: none;
                border-radius: {scaled_size(11)}px;
                background-color: #eeeeee;
                color: #555;
            }}
            QProgressBar::chunk {{
                background-color: {Task.STATUS_COLORS[task.status].name()};
                border-radius: {scaled_size(11)}px;
            }}
        """)
        
        days_text = f"剩余: {task.remaining_days}天  |  预计: {task.estimated_date}"
        self.days_info.setText(days_text)
        self.days_info.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #666;")


class ProgressManager(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.base_scaling_factor = get_base_scaling_factor()
        global SCALING_FACTOR
        SCALING_FACTOR = self.base_scaling_factor

        self.setWindowTitle("任务进度管理器 by TZYLT&QianXiquq")
        self.setGeometry(100, 100, scaled_size(1200), scaled_size(800))
        self.tasks = []
        self.current_task = None
        self.current_subtask = None
        self.data_file = "tasks.json"
        
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        
        self.load_data()
        self.init_ui()
    
    def toggle_fullscreen(self):
        is_entering_fullscreen = not self.isFullScreen()

        if is_entering_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

        self.update_and_apply_styles(is_fullscreen=is_entering_fullscreen)

    def update_and_apply_styles(self, is_fullscreen):
        global SCALING_FACTOR
        if is_fullscreen:
            SCALING_FACTOR = self.base_scaling_factor * 1.25
        else:
            SCALING_FACTOR = self.base_scaling_factor
        
        current_index = self.task_list.currentRow()
        
        self.apply_styles()
        
        self.populate_task_list()
        
        if current_index >= 0 and current_index < self.task_list.count():
            self.task_list.setCurrentRow(current_index)
        
        self.update_detail_view()
        self.update_chart()

    def load_data(self):
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [Task.from_dict(t) for t in data]
        except FileNotFoundError:
            self.tasks = []
    
    def save_data(self):
        data = [t.to_dict() for t in self.tasks]
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setSpacing(scaled_size(15))
        main_layout.setContentsMargins(scaled_size(15), scaled_size(15), scaled_size(15), scaled_size(15))
        
        # 左侧任务列表
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(scaled_size(10))
        
        self.task_list = QListWidget()
        self.task_list.itemSelectionChanged.connect(self.on_task_selected)
        
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
        right_layout.setSpacing(scaled_size(10))
        
        mode_layout = QHBoxLayout()
        self.mode_label = QLabel("显示模式:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["详细信息", "图表分析"])
        self.mode_combo.currentIndexChanged.connect(self.switch_mode)
        
        self.today_summary_btn = QPushButton("今日总结")
        self.today_summary_btn.setToolTip("显示今日有更新的任务总结")
        self.today_summary_btn.clicked.connect(self.show_today_summary)
        
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        mode_layout.addWidget(self.today_summary_btn)
        
        self.stacked_widget = QStackedWidget()
        
        self.detail_widget = QWidget()
        self.init_detail_ui()
        self.stacked_widget.addWidget(self.detail_widget)
        
        self.chart_widget = QWidget()
        self.init_chart_ui()
        self.stacked_widget.addWidget(self.chart_widget)
        
        right_layout.addLayout(mode_layout)
        right_layout.addWidget(self.stacked_widget)
        right_panel.setLayout(right_layout)
        
        main_layout.addWidget(left_panel, 35)
        main_layout.addWidget(right_panel, 65)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_task_context_menu)

        self.apply_styles()
        self.populate_task_list()

    # ==================== UI现代化修改：apply_styles ====================
    def apply_styles(self):
        """
        集中的方法，用于设置所有UI组件的现代化样式和尺寸。
        """
        # --- 全局字体和背景 ---
        app_font = QApplication.instance().font()
        app_font.setFamily("Microsoft YaHei UI") # 使用更现代的字体
        app_font.setPointSize(scaled_font_size(10))
        QApplication.instance().setFont(app_font)
        self.setStyleSheet(f"QMainWindow, QDialog {{ background-color: #f8f9fa; }}")

        # --- 左侧面板 ---
        self.task_list_label.setStyleSheet(f"font-size: {scaled_font_size(16)}px; font-weight: bold; color: #333; padding-left: 5px;")
        self.task_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #f8f9fa;
                border: none;
                padding: {scaled_size(5)}px;
                spacing: {scaled_size(10)}px; /* 增加卡片间距 */
            }}
            QListWidget::item {{
                border: none; /* 移除默认边框，由TaskCard自己控制 */
            }}
            QListWidget::item:selected {{
                background-color: transparent; /* 移除默认选中背景 */
                color: black;
            }}
        """)
        self.add_task_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #007bff; color: white; border: none;
                padding: {scaled_size(12)}px; border-radius: {scaled_size(8)}px;
                font-weight: bold; font-size: {scaled_font_size(14)}px;
            }}
            QPushButton:hover {{ background-color: #0056b3; }}
        """)
        
        # --- 右侧面板 ---
        self.mode_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #555;")
        self.mode_combo.setStyleSheet(f"""
            QComboBox {{
                font-size: {scaled_font_size(14)}px;
                padding: {scaled_size(6)}px;
                border: 1px solid #ced4da;
                border-radius: {scaled_size(8)}px;
                background-color: white;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """)
        self.today_summary_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #28a745; color: white; border: none;
                padding: {scaled_size(8)}px {scaled_size(12)}px;
                border-radius: {scaled_size(8)}px; font-size: {scaled_font_size(14)}px;
            }}
            QPushButton:hover {{ background-color: #218838; }}
        """)
        
        # --- 详细信息视图 (GroupBox样式) ---
        groupbox_style = f"""
            QGroupBox {{
                font-size: {scaled_font_size(16)}px;
                font-weight: bold;
                color: #333;
                border: 1px solid #e0e0e0;
                border-radius: {scaled_size(12)}px;
                margin-top: {scaled_size(10)}px;
                background-color: #ffffff;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 {scaled_size(10)}px;
                left: {scaled_size(10)}px;
            }}
        """
        self.task_overview.setStyleSheet(groupbox_style)
        self.progress_group.setStyleSheet(groupbox_style)

        # --- 详细信息视图内部组件 ---
        self.task_name_label.setStyleSheet(f"font-family: \"Microsoft YaHei UI\", sans-serif; font-size: {scaled_font_size(20)}px; font-weight: bold; color: #212529;")
        self.task_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                font-size: {scaled_font_size(16)}px;
                height: {scaled_size(28)}px;
                border: none;
                border-radius: {scaled_size(14)}px;
                background-color: #e9ecef;
                color: #495057;
            }}
            QProgressBar::chunk {{
                background-color: #007bff;
                border-radius: {scaled_size(14)}px;
            }}
        """)
        self.task_info_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #6c757d;")
        self.subtask_list_label.setStyleSheet(f"font-size: {scaled_font_size(16)}px; font-weight: bold; color: #333; padding-left: 5px;")
        self.subtask_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #ffffff; border: 1px solid #e0e0e0;
                border-radius: {scaled_size(12)}px; font-size: {scaled_font_size(14)}px;
                padding: {scaled_size(5)}px;
            }}
        """)
        
        # --- 进度登记表单 ---
        input_style = f"""
            border: 1px solid #ced4da;
            border-radius: {scaled_size(8)}px;
            padding: {scaled_size(6)}px;
            background-color: #ffffff;
            font-size: {scaled_font_size(14)}px;
        """
        self.subtask_name_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #333;")
        self.date_edit.setStyleSheet(f"QDateEdit {{ {input_style} }}")
        self.progress_input.setStyleSheet(f"QSpinBox {{ {input_style} }}")
        self.offset_input.setStyleSheet(f"QSpinBox {{ {input_style} }}")
        
        self.register_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #17a2b8; color: white;
                font-size: {scaled_font_size(14)}px; padding: {scaled_size(10)}px;
                border-radius: {scaled_size(8)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #138496; }}
        """)

        # --- 图表视图 ---
        self.chart_type_label.setStyleSheet(f"font-size: {scaled_font_size(14)}px; color: #555;")
        self.chart_type_combo.setStyleSheet(f"""
            QComboBox {{
                font-size: {scaled_font_size(14)}px;
                padding: {scaled_size(6)}px;
                border: 1px solid #ced4da;
                border-radius: {scaled_size(8)}px;
                background-color: white;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)

    def populate_task_list(self):
        self.task_list.clear()
        for task in self.tasks:
            item = QListWidgetItem()
            widget = TaskCard(task, self) # 传入parent
            item.setSizeHint(widget.sizeHint())
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, widget)
    
    def init_detail_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(scaled_size(15))
        layout.setContentsMargins(0, 0, 0, 0) # 容器内边距设为0
        
        self.task_overview = QGroupBox("任务概览")
        overview_layout = QVBoxLayout()
        overview_layout.setSpacing(scaled_size(10))
        overview_layout.setContentsMargins(scaled_size(15), scaled_size(25), scaled_size(15), scaled_size(15))
        
        self.task_name_label = QLabel("")
        self.task_progress_bar = QProgressBar()
        self.task_progress_bar.setRange(0, 100)
        self.task_info_label = QLabel("")
        
        overview_layout.addWidget(self.task_name_label)
        overview_layout.addWidget(self.task_progress_bar)
        overview_layout.addWidget(self.task_info_label)
        self.task_overview.setLayout(overview_layout)
        
        self.subtask_list_label = QLabel("子任务列表")
        self.subtask_list = QListWidget()
        self.subtask_list.itemSelectionChanged.connect(self.on_subtask_selected)
        
        self.progress_group = QGroupBox("进度登记")
        progress_layout = QFormLayout()
        progress_layout.setLabelAlignment(Qt.AlignRight)
        progress_layout.setContentsMargins(scaled_size(15), scaled_size(25), scaled_size(15), scaled_size(15))
        progress_layout.setVerticalSpacing(scaled_size(15))
        
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
        layout.addWidget(self.subtask_list, 1) # 使用伸展因子
        layout.addWidget(self.progress_group)
        self.detail_widget.setLayout(layout)
    
    def init_chart_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        control_panel = QWidget()
        control_panel.setStyleSheet("background-color: white; border-radius: 12px;")
        
        chart_type_layout = QHBoxLayout()
        chart_type_layout.setContentsMargins(scaled_size(10), scaled_size(10), scaled_size(10), scaled_size(10))
        self.chart_type_label = QLabel("图表模式:")
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["总量模式", "增量模式"])
        self.chart_type_combo.currentIndexChanged.connect(self.update_chart)
        
        chart_type_layout.addWidget(self.chart_type_label)
        chart_type_layout.addWidget(self.chart_type_combo)
        chart_type_layout.addStretch()
        control_panel.setLayout(chart_type_layout)
        
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setStyleSheet("border: none; background-color: white; border-radius: 12px;")
        
        layout.addWidget(control_panel)
        layout.addWidget(self.chart_view, 1) # 使用伸展因子
        self.chart_widget.setLayout(layout)
    
    def on_task_selected(self):
        selected_items = self.task_list.selectedItems()
        if not selected_items:
            self.current_task = None
            return
        
        idx = self.task_list.row(selected_items[0])
        self.current_task = self.tasks[idx]
        self.update_detail_view()
    
    def refresh_task_cards(self):
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget and i < len(self.tasks):
                widget.update_task(self.tasks[i])

    def refresh_current_task_card(self):
        selected_items = self.task_list.selectedItems()
        if not selected_items: return
        
        idx = self.task_list.row(selected_items[0])
        item = self.task_list.item(idx)
        widget = self.task_list.itemWidget(item)
        if widget:
            widget.update_task(self.current_task)

    def select_current_task_in_list(self):
        if self.current_task is None:
            return
        for i in range(len(self.tasks)):
            if self.tasks[i].name == self.current_task.name:
                self.task_list.setCurrentRow(i)
                break

    def update_detail_view(self):
        if not self.current_task:
            self.task_name_label.setText("未选择任务")
            self.task_progress_bar.setValue(0)
            self.task_progress_bar.setFormat("N/A")
            self.task_info_label.setText("")
            self.subtask_list.clear()
            self.subtask_name_label.setText("选择子任务")
            self.update_chart()
            return
        
        self.task_name_label.setText(self.current_task.name)
        self.task_progress_bar.setValue(round(self.current_task.progress))
        self.task_progress_bar.setFormat(f"{self.current_task.progress:.2f}%")
        self.task_info_label.setText(
            f"状态: {self.current_task.status} | 剩余天数: {self.current_task.remaining_days} | "
            f"预计完成: {self.current_task.estimated_date}"
        )
        
        self.subtask_list.clear()
        for subtask in self.current_task.sub_tasks:
            item = QListWidgetItem()
            widget = self.create_subtask_card(subtask)
            item.setSizeHint(widget.sizeHint())
            self.subtask_list.addItem(item)
            self.subtask_list.setItemWidget(item, widget)
    
        self.update_chart()
        
        self.refresh_current_task_card()
    
    def create_subtask_card(self, subtask):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(scaled_size(10), scaled_size(8), scaled_size(10), scaled_size(8))
        
        name_label = QLabel(subtask.name)
        name_label.setStyleSheet(f"font-weight: bold; font-size: {scaled_font_size(14)}px; color: #333;")
        layout.addWidget(name_label)
        
        progress = (subtask.completed / subtask.total * 100) if subtask.total > 0 else 0
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(round(progress))
        progress_bar.setFormat(f"{progress:.2f}% ({subtask.completed}/{subtask.total})")
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                font-size: {scaled_font_size(12)}px;
                height: {scaled_size(18)}px;
                border: none;
                border-radius: {scaled_size(9)}px;
                background-color: #e9ecef;
            }}
            QProgressBar::chunk {{
                background-color: #17a2b8;
                border-radius: {scaled_size(9)}px;
            }}
        """)
        layout.addWidget(progress_bar)
        
        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #f8f9fa; border-radius: 8px;")
        return widget
    
    def on_subtask_selected(self):
        selected_items = self.subtask_list.selectedItems()
        if not selected_items or not self.current_task:
            self.current_subtask = None
            self.subtask_name_label.setText("选择子任务")
            return
        
        idx = self.subtask_list.row(selected_items[0])
        self.current_subtask = self.current_task.sub_tasks[idx]
        self.subtask_name_label.setText(self.current_subtask.name)
        self.offset_input.setValue(self.current_subtask.auto_offset)
    
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
        if index == 1:
            self.update_chart()
        
    def update_chart(self):
        if not self.current_task:
            self.chart_view.setChart(QChart())
            return
        
        chart = QChart()
        chart.setTitle(f"{self.current_task.name} - 进度分析")
        chart.legend().setVisible(True)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setBackgroundRoundness(0) # 确保图表背景不影响外部容器的圆角
        chart.setMargins(QMargins(0, 0, 0, 0))
        
        font = chart.titleFont()
        font.setPointSize(scaled_font_size(16))
        font.setBold(True)
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
        total_series.setColor(QColor("#007bff"))
        total_series.setPointsVisible(True)
        
        subtask_series = []
        colors = ["#17a2b8", "#28a745", "#ffc107", "#dc3545", "#6f42c1"]
        for i, subtask in enumerate(self.current_task.sub_tasks):
            series = QLineSeries()
            series.setName(subtask.name)
            series.setColor(QColor(colors[i % len(colors)]))
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
        if not chart: return
        scene = self.chart_view.scene()
        if not scene: return
            
        for item in scene.items():
            if isinstance(item, QGraphicsSimpleTextItem):
                scene.removeItem(item)
        
        series_list = chart.series()
        if not series_list: return
            
        for series in series_list:
            points = series.pointsVector()
            for point in points:
                scene_point = chart.mapToPosition(point)
                value_text = f"{point.y():.1f}"
                label = QGraphicsSimpleTextItem(value_text)
                
                label_x = scene_point.x() - (label.boundingRect().width() / 2)
                label_y = scene_point.y() - label.boundingRect().height() - 5
                
                plot_area = chart.plotArea()
                if label_y < plot_area.top():
                    label_y = scene_point.y() + 5
                
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
        menu.setStyleSheet(f"""
            QMenu {{ 
                font-size: {scaled_font_size(14)}px; 
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }}
            QMenu::item:selected {{
                background-color: #007bff;
                color: white;
            }}
        """)
        
        status_menu = QMenu("更改状态", menu)
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

    def show_today_summary(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        summary_lines = []

        for task in self.tasks:
            for st in task.sub_tasks:
                if today_str in st.records:
                    today_val = st.records[today_str]
                    prev_vals = []
                    for d_str, val in st.records.items():
                        try:
                            if datetime.strptime(d_str, "%Y-%m-%d") < datetime.strptime(today_str, "%Y-%m-%d"):
                                prev_vals.append((datetime.strptime(d_str, "%Y-%m-%d"), val))
                        except Exception:
                            continue
                    
                    prev_val = prev_vals[-1][1] if prev_vals else 0
                    pages_added = max(0, today_val - prev_val)

                    completed_before = 0
                    for other in task.sub_tasks:
                        other_prev_vals = []
                        for d_str, val in other.records.items():
                            try:
                                if datetime.strptime(d_str, "%Y-%m-%d") < datetime.strptime(today_str, "%Y-%m-%d"):
                                    other_prev_vals.append((datetime.strptime(d_str, "%Y-%m-%d"), val))
                            except Exception:
                                continue
                        if other_prev_vals:
                            completed_before += min(other_prev_vals[-1][1], other.total)

                    completed_after = 0
                    for other in task.sub_tasks:
                        latest_vals = []
                        for d_str, val in other.records.items():
                            try:
                                if datetime.strptime(d_str, "%Y-%m-%d") <= datetime.strptime(today_str, "%Y-%m-%d"):
                                    latest_vals.append((datetime.strptime(d_str, "%Y-%m-%d"), val))
                            except Exception:
                                continue
                        if latest_vals:
                            completed_after += min(latest_vals[-1][1], other.total)

                    total_required = task.total if task.total > 0 else 1
                    percent_before = (completed_before / total_required * 100)
                    percent_after = (completed_after / total_required * 100)

                    if pages_added > 0 or abs(percent_after - percent_before) > 1e-6:
                        line = f"【{task.name} - {st.name}】进度增加了 {pages_added}，总进度从 {percent_before:.2f}% 变为 {percent_after:.2f}%"
                        summary_lines.append(line)

        dlg = QDialog(self)
        dlg.setWindowTitle("今日总结")
        dlg_layout = QVBoxLayout()
        if summary_lines:
            list_widget = QListWidget()
            list_widget.setStyleSheet(f"font-size: {scaled_font_size(14)}px; border: none; background-color: #f8f9fa;")
            list_widget.addItems(summary_lines)
            dlg_layout.addWidget(list_widget)
        else:
            no_update_label = QLabel("今日没有任务进度更新")
            no_update_label.setAlignment(Qt.AlignCenter)
            no_update_label.setStyleSheet(f"font-size: {scaled_font_size(16)}px; color: #666;")
            dlg_layout.addWidget(no_update_label)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.setStyleSheet(f"QPushButton {{ font-size: {scaled_font_size(14)}px; padding: 8px 20px; border-radius: 8px; }}")
        btns.rejected.connect(dlg.reject)
        dlg_layout.addWidget(btns)
        dlg.setLayout(dlg_layout)
        dlg.resize(scaled_size(700), scaled_size(450))
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    SCALING_FACTOR = get_base_scaling_factor()
    
    window = ProgressManager()
    window.show()
    sys.exit(app.exec_())