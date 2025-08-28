import sys
import json
import random
from datetime import datetime, timedelta
from collections import defaultdict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QProgressBar, QPushButton, QStackedWidget, QLineEdit, QFormLayout, QMenu,
    QAction, QMessageBox, QGroupBox, QComboBox, QDateEdit, QSpinBox, QInputDialog, QGraphicsSimpleTextItem,
    QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PyQt5.QtGui import QColor, QPainter

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
        
        # 收集所有子任务记录
        all_records = []
        for st in self.sub_tasks:
            for date, progress in st.records.items():
                all_records.append((datetime.strptime(date, "%Y-%m-%d"), progress))
        
        if not all_records: 
            return 0
        
        # 按日期排序
        all_records.sort(key=lambda x: x[0])
        last_date = all_records[-1][0]
        
        # 获取最近7天有记录的数据（忽略无记录日）
        recent_records = []
        for record_date, progress in all_records:
            if (last_date - record_date).days <= 5:
                recent_records.append((record_date, progress))
        
        # 如果记录不足2个，无法计算
        if len(recent_records) < 2:
            return 0
        
        # 计算平均日增量（基于实际有记录的天数）
        total_increase = recent_records[-1][1] - recent_records[0][1]
        
        # 计算实际有记录的天数跨度
        date_span = (recent_records[-1][0] - recent_records[0][0]).days
        if date_span == 0:
            return 0
        
        avg_daily = total_increase / date_span
        remaining = max(0, self.total - self.completed)
        
        return max(1, round(remaining / avg_daily)) if avg_daily > 0 else 0
    
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
        task = cls(data["name"])
        task.status = data["status"]
        task.start_date = data.get("start_date", datetime.now().strftime("%Y-%m-%d"))
        task.sub_tasks = [SubTask.from_dict(st) for st in data["sub_tasks"]]
        return task

class TaskCard(QWidget):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.parent = parent
        
        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 任务名称和状态
        header_layout = QHBoxLayout()
        self.name_label = QLabel(task.name)
        self.name_label.setStyleSheet("font-family: \"黑体\", sans-serif; font-weight: bold; font-size: 20px;")
        self.name_label.setWordWrap(True)
        
        self.status_label = QLabel(task.status)
        self.status_label.setStyleSheet(f"font-family: \"黑体\", sans-serif; color: {Task.STATUS_COLORS[task.status].name()}; font-size: 19px;")
        
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
                background-color: {Task.STATUS_COLORS[task.status].name()};
            }}
        """)
        
        # 任务信息（剩余天数和预计完成日期）
        info_layout = QHBoxLayout()
        
        # 创建剩余天数标签
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
        self.setFixedHeight(100)
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
        
    def update_task(self, task):
        """更新卡片显示的任务数据"""
        self.task = task
        self.name_label.setText(task.name)
        self.status_label.setText(task.status)
        self.status_label.setStyleSheet(f"font-family: \"黑体\", sans-serif; color: {Task.STATUS_COLORS[task.status].name()}; font-size: 19px;")
        self.progress_bar.setValue(round(task.progress))
        self.progress_bar.setFormat(f" {task.progress:.2f}%")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
            font-size:16px;
            }}
            QProgressBar::chunk {{
                background-color: {Task.STATUS_COLORS[task.status].name()};
            }}
        """)
        
        # 更新剩余天数和预计完成日期
        days_text = f"剩余天数: {task.remaining_days}天 | 预计完成: {task.estimated_date}"
        self.days_info.setText(days_text)


class ProgressManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("任务进度管理器 by TZYLT&QianXiquq")
        self.setGeometry(100, 100, 1200, 800)
        self.tasks = []
        self.current_task = None
        self.current_subtask = None
        self.data_file = "tasks.json"
        
        self.load_data()
        self.init_ui()
    
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
        
        # 左侧任务列表
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        self.task_list = QListWidget()
        self.task_list.setStyleSheet("""
            QListWidget {
                background-color: #f0f2f5;
                border: none;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                border-bottom: 1px solid #dee2e6;
            }
            QListWidget::item:selected {
                background-color: #e2e6ea;
            }
        """)
        self.task_list.itemSelectionChanged.connect(self.on_task_selected)
        self.populate_task_list()
        
        # 添加任务按钮
        add_task_btn = QPushButton("添加新任务")
        add_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_task_btn.clicked.connect(self.add_new_task)
        
        left_layout.addWidget(QLabel("任务列表"))
        left_layout.addWidget(self.task_list)
        left_layout.addWidget(add_task_btn)
        left_panel.setLayout(left_layout)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # 模式切换
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["详细信息", "图表分析"])
        self.mode_combo.currentIndexChanged.connect(self.switch_mode)
        
        mode_layout.addWidget(QLabel("显示模式:"))
        mode_layout.addWidget(self.mode_combo)
        
        # --- 新增：今日总结按钮（放在模式选择旁） ---
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
        mode_layout.addWidget(self.today_summary_btn)
        # --- 新增结束 ---
        
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
        
        # 设置右键菜单
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_task_context_menu)
    
    def populate_task_list(self):
        self.task_list.clear()
        for task in self.tasks:
            item = QListWidgetItem()
            widget = TaskCard(task)
            item.setSizeHint(widget.sizeHint())
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, widget)
    
    def init_detail_ui(self):
        layout = QVBoxLayout()
        
        # 任务概览
        self.task_overview = QGroupBox("任务概览")
        overview_layout = QVBoxLayout()
        
        self.task_name_label = QLabel("")
        self.task_name_label.setStyleSheet("font-family: \"黑体\", sans-serif; font-size: 18px; font-weight: bold;")
        
        self.task_progress_bar = QProgressBar()
        self.task_progress_bar.setRange(0, 100)
        
        self.task_info_label = QLabel("")
        self.task_info_label.setStyleSheet("font-size: 12px; color: #555;")
        
        overview_layout.addWidget(self.task_name_label)
        overview_layout.addWidget(self.task_progress_bar)
        overview_layout.addWidget(self.task_info_label)
        self.task_overview.setLayout(overview_layout)
        
        # 子任务列表
        self.subtask_list = QListWidget()
        self.subtask_list.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        self.subtask_list.itemSelectionChanged.connect(self.on_subtask_selected)
        
        # 进度登记
        self.progress_group = QGroupBox("进度登记")
        progress_layout = QFormLayout()
        
        self.subtask_name_label = QLabel("选择子任务")
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        
        self.progress_input = QSpinBox()
        self.progress_input.setRange(0, 100000)
        self.progress_input.setValue(0)
        
        self.offset_input = QSpinBox()
        self.offset_input.setRange(-1000, 1000)
        self.offset_input.setValue(0)
        
        self.register_btn = QPushButton("登记进度")
        self.register_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.register_btn.clicked.connect(self.register_progress)
        
        progress_layout.addRow(QLabel("子任务:"), self.subtask_name_label)
        progress_layout.addRow(QLabel("日期:"), self.date_edit)
        progress_layout.addRow(QLabel("进度值:"), self.progress_input)
        progress_layout.addRow(QLabel("自动偏移:"), self.offset_input)
        progress_layout.addRow(self.register_btn)
        self.progress_group.setLayout(progress_layout)
        
        layout.addWidget(self.task_overview)
        layout.addWidget(QLabel("子任务列表"))
        layout.addWidget(self.subtask_list, 50)
        layout.addWidget(self.progress_group, 30)
        self.detail_widget.setLayout(layout)
    
    def init_chart_ui(self):
        layout = QVBoxLayout()
        
        # 图表类型选择
        chart_type_layout = QHBoxLayout()
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["总量模式", "增量模式"])
        self.chart_type_combo.currentIndexChanged.connect(self.update_chart)
        
        chart_type_layout.addWidget(QLabel("图表模式:"))
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
        self.current_task = self.tasks[idx]
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
        if not selected_items: return
        
        idx = self.task_list.row(selected_items[0])
        item = self.task_list.item(idx)
        widget = self.task_list.itemWidget(item)
        if widget:
            widget.update_task(self.current_task)

    def select_current_task_in_list(self):
        """确保当前任务在列表中被选中"""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget and widget.task == self.current_task:
                self.task_list.setCurrentItem(item)
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
        self.task_info_label.setText(
            f"状态: {self.current_task.status} | 剩余天数: {self.current_task.remaining_days} | "
            f"预计完成: {self.current_task.estimated_date}"
        )
        
        # 更新子任务列表
        self.subtask_list.clear()
        for subtask in self.current_task.sub_tasks:
            item = QListWidgetItem()
            widget = self.create_subtask_card(subtask)
            item.setSizeHint(widget.sizeHint())
            self.subtask_list.addItem(item)
            self.subtask_list.setItemWidget(item, widget)
    
        # 更新图表
        self.update_chart()
        
        # 刷新当前任务卡片（重要更新）
        self.refresh_current_task_card()
    
    def create_subtask_card(self, subtask):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 子任务名称
        name_label = QLabel(subtask.name)
        name_label.setStyleSheet("font-family: \"黑体\", sans-serif; font-weight: bold;")
        layout.addWidget(name_label)
        
        # 进度条
        progress = (subtask.completed / subtask.total * 100) if subtask.total > 0 else 0
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(round(progress))
        progress_bar.setFormat(f"{progress:.2f}% ({subtask.completed}/{subtask.total})")
        layout.addWidget(progress_bar)
        
        widget.setLayout(layout)
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
        
        # 更新UI
        self.update_detail_view()
        self.save_data()
        
        # 刷新任务列表
        self.refresh_task_cards()
        
        # 如果当前任务在列表中选中，更新其显示
        if self.current_task:
            self.select_current_task_in_list()
    
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
        
        # 创建坐标轴
        axisX = QDateTimeAxis()
        axisX.setFormat("yyyy-MM-dd")
        axisX.setTitleText("日期")
        
        axisY = QValueAxis()
        axisY.setTitleText("进度 (%)")
        
        # 检查当前图表模式
        chart_mode = self.chart_type_combo.currentText()
        
        # 收集所有日期
        all_dates = set()
        for subtask in self.current_task.sub_tasks:
            all_dates.update(subtask.records.keys())
        
        if not all_dates:
            self.chart_view.setChart(chart)
            return
        
        # 转换日期并排序
        sorted_dates = sorted(all_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
        date_objs = [datetime.strptime(d, "%Y-%m-%d") for d in sorted_dates]
        min_date = min(date_objs)
        max_date = max(date_objs)
        
        # 设置X轴范围
        axisX.setRange(min_date, max_date + timedelta(days=1))
        
        # 添加任务总进度
        total_series = QLineSeries()
        total_series.setName("总进度")
        total_series.setColor(QColor(0, 0, 0))
        total_series.setPointsVisible(True)
        
        # 添加子任务进度
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
        
        # 按日期填充数据
        # 初始化当前进度数组（用于增量模式和总量模式）
        current_subtask_progress = [0] * len(self.current_task.sub_tasks)
        
        if chart_mode == "增量模式":
            # 初始化前一个总进度和子任务进度
            prev_total_progress = 0
            prev_subtask_progress = [0] * len(self.current_task.sub_tasks)
            max_increment_value = 0
            
            for date in sorted_dates:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                timestamp = date_obj.timestamp() * 1000
                
                # 更新当前进度：对于每个子任务，如果当天有记录，则更新进度
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    if date in subtask.records:
                        current_subtask_progress[i] = min(subtask.records[date], subtask.total)
                
                # 计算总完成量和总量
                total_completed = sum(current_subtask_progress)
                total_required = sum(subtask.total for subtask in self.current_task.sub_tasks)
                total_progress = (total_completed / total_required * 100) if total_required > 0 else 0
                
                # 计算总进度增量
                total_delta = total_progress - prev_total_progress
                total_series.append(timestamp, max(0, total_delta))
                prev_total_progress = total_progress
                
                # 更新最大值
                max_increment_value = max(max_increment_value, max(0, total_delta))
                
                # 对于每个子任务，计算增量
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    # 当前进度百分比
                    subtask_percent = (current_subtask_progress[i] / subtask.total * 100) if subtask.total > 0 else 0
                    delta = subtask_percent - prev_subtask_progress[i]
                    delta_value = max(0, delta)
                    subtask_series[i].append(timestamp, delta_value)
                    prev_subtask_progress[i] = subtask_percent
                    max_increment_value = max(max_increment_value, delta_value)
            
            # 设置Y轴范围
            upper_bound = max_increment_value * 1.2 if max_increment_value > 0 else 10
            axisY.setRange(0, upper_bound)
            axisY.setTickCount(6)
        else:
            # 总量模式
            for date in sorted_dates:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                timestamp = date_obj.timestamp() * 1000
                
                # 更新每个子任务的当前进度值
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    if date in subtask.records:
                        current_subtask_progress[i] = min(subtask.records[date], subtask.total)
                
                total_completed = sum(current_subtask_progress)
                total_required = sum(subtask.total for subtask in self.current_task.sub_tasks)
                total_progress = (total_completed / total_required * 100) if total_required > 0 else 0
                total_series.append(timestamp, total_progress)
                
                # 计算子任务进度
                for i, subtask in enumerate(self.current_task.sub_tasks):
                    progress = current_subtask_progress[i]
                    percent = (progress / subtask.total * 100) if subtask.total > 0 else 0
                    subtask_series[i].append(timestamp, percent)
            
            # 总量模式下保持0-100的范围
            axisY.setRange(0, 100)
            axisY.setTickCount(11)
        
        # 添加到图表
        chart.addSeries(total_series)
        for series in subtask_series:
            chart.addSeries(series)
        
        chart.addAxis(axisX, Qt.AlignBottom)
        chart.addAxis(axisY, Qt.AlignLeft)
        
        for series in [total_series] + subtask_series:
            series.attachAxis(axisX)
            series.attachAxis(axisY)
        
        # 设置图表视图
        self.chart_view.setChart(chart)
        
        # 添加数据点标签
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self.add_data_labels)

    
    def add_data_labels(self):
        """添加数据点标签到图表"""
        chart = self.chart_view.chart()
        if not chart:
            return
            
        scene = self.chart_view.scene()
        if not scene:
            return
            
        # 清除现有标签
        for item in scene.items():
            if isinstance(item, QGraphicsSimpleTextItem):
                scene.removeItem(item)
        
        # 获取所有系列
        series_list = chart.series()
        if not series_list:
            return
            
        # 为每个系列添加标签
        for series in series_list:
            points = series.pointsVector()
            for point in points:
                # 将图表坐标转换为场景坐标
                scene_point = chart.mapToPosition(point)
                
                # 格式化数值为两位小数
                value_text = f"{point.y():.2f}"
                
                # 创建标签
                label = QGraphicsSimpleTextItem(value_text)
                
                # 计算标签位置（数据点右上方）
                label_x = scene_point.x() + 5
                label_y = scene_point.y() - 15
                
                # 确保标签不会超出图表区域
                plot_area = chart.plotArea()
                if label_y < plot_area.top():
                    label_y = scene_point.y() + 10  # 如果太靠上，放在下方
                
                label.setPos(label_x, label_y)
                label.setBrush(QColor(0, 0, 0))
                
                # 设置字体大小
                font = label.font()
                font.setPointSize(8)
                label.setFont(font)
                
                scene.addItem(label)

    def show_task_context_menu(self, pos):
        item = self.task_list.itemAt(pos)
        if not item: return
        
        idx = self.task_list.row(item)
        task = self.tasks[idx]
        
        menu = QMenu()
        
        # 状态菜单
        status_menu = menu.addMenu("更改状态")
        for status in ["进行中", "暂停", "废止"]:
            action = status_menu.addAction(status)
            action.triggered.connect(lambda _, s=status, t=task: self.change_task_status(t, s))
        
        # 重命名
        rename_action = menu.addAction("重命名")
        rename_action.triggered.connect(lambda _, t=task: self.rename_task(t))
        
        # 添加子任务
        add_sub_action = menu.addAction("添加子任务")
        add_sub_action.triggered.connect(lambda _, t=task: self.add_subtask(t))
        
        # 删除任务
        delete_action = menu.addAction("删除任务")
        delete_action.triggered.connect(lambda _, t=task: self.delete_task(t))
        
        menu.exec_(self.task_list.mapToGlobal(pos))
    
    def change_task_status(self, task, status):
        task.status = status
        self.save_data()
        self.populate_task_list()
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
            self.tasks.remove(task)
            self.save_data()
            self.populate_task_list()
            if task == self.current_task:
                self.current_task = None
                self.update_detail_view()
    
    def add_new_task(self):
        name, ok = QInputDialog.getText(
            self, "添加新任务", "输入任务名称:"
        )
        if ok and name:
            self.tasks.append(Task(name))
            self.save_data()
            self.populate_task_list()

    # ---------------- 新增：今日总结功能 ----------------
    def show_today_summary(self):
        """弹出窗口显示今日有更新的任务总结，按指定格式显示"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        summary_lines = []
        
        for task in self.tasks:
            task_has_update = False
            task_lines = []
            
            # 计算任务整体今日前后的完成量和百分比
            total_before = 0
            total_after = 0
            
            # 先收集所有子任务的信息
            subtask_info = []
            for st in task.sub_tasks:
                # 今日是否有记录
                if today_str in st.records:
                    today_val = st.records[today_str]
                    
                    # 找到此前最新的记录（日期 < today）
                    prev_vals = []
                    for d_str, val in st.records.items():
                        try:
                            d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                        except Exception:
                            continue
                        if d_obj < datetime.strptime(today_str, "%Y-%m-%d"):
                            prev_vals.append((d_obj, val))
                    
                    if prev_vals:
                        prev_vals.sort(key=lambda x: x[0])
                        prev_val = prev_vals[-1][1]
                    else:
                        prev_val = 0
                    
                    # 计算变化量
                    change = max(0, today_val - prev_val)
                    
                    # 计算子任务百分比
                    prev_percent = (min(prev_val, st.total) / st.total * 100) if st.total > 0 else 0
                    curr_percent = (min(today_val, st.total) / st.total * 100) if st.total > 0 else 0
                    
                    # 累加到任务总量
                    total_before += min(prev_val, st.total)
                    total_after += min(today_val, st.total)
                    
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
            from PyQt5.QtWidgets import QTextEdit
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


    def switch_mode(self, index):
        self.stacked_widget.setCurrentIndex(index)
        if index == 1:  # 图表模式
            self.update_chart()

    # (注意：前面定义过 switch_mode，这里保留一个定义以防意外覆盖)
    # 其余方法保持不变（上文已定义）

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProgressManager()
    window.show()
    sys.exit(app.exec_())
