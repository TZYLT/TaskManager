import sys
import random
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QProgressBar, QPushButton, QStackedWidget, QLineEdit, QFormLayout, QMenu,
    QAction, QMessageBox, QGroupBox, QComboBox, QDateEdit, QSpinBox, QInputDialog,
    QGraphicsSimpleTextItem, QDialog, QDialogButtonBox, QTextEdit, QScrollArea,
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PyQt5.QtGui import QColor, QPainter, QFont
from tasks import SubTask, Task, TaskManager


class TaskCard(QWidget):
    """任务卡片组件：在任务列表中显示单个任务的概览"""
    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.init_ui()

    def init_ui(self):
        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # 任务名称和状态
        header_layout = QHBoxLayout()
        self.name_label = QLabel(self.task.name)
        self.name_label.setStyleSheet("font-family: \"黑体\", sans-serif; font-weight: bold; font-size: 20px;")
        self.name_label.setWordWrap(True)

        # 检查进度是否为100%，如果是则显示"已完成"
        if self.task.progress >= 100:
            display_status = "已完成"
            display_color = QColor(0, 128, 0)  # 绿色表示已完成
        else:
            display_status = self.task.status
            display_color = Task.STATUS_COLORS.get(self.task.status, QColor(0, 0, 0))
        
        self.status_label = QLabel(display_status)
        self.status_label.setStyleSheet(
            f"font-family: \"黑体\", sans-serif; color: {display_color.name()}; font-size: 19px;"
        )

        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(round(self.task.progress))
        
        # 根据是否完成设置不同的格式和颜色
        if self.task.progress >= 100:
            self.progress_bar.setFormat(" 100.00%")
            self.progress_bar.setStyleSheet(
                f"""QProgressBar {{font-size:16px;}}
                   QProgressBar::chunk {{background-color: #32CD32;}}"""
            )
        else:
            self.progress_bar.setFormat(f" {self.task.progress:.2f}%")
            self.progress_bar.setStyleSheet(
                f"""QProgressBar {{font-size:16px;}}
                   QProgressBar::chunk {{background-color: {Task.STATUS_COLORS.get(self.task.status, QColor(0,0,0)).name()};}}"""
            )

        # 任务信息（剩余天数+预计完成日期）
        info_layout = QHBoxLayout()
        if self.task.progress >= 100:
            # 任务完成时显示完成信息
            days_text = "已完成"
        else:
            days_text = f"剩余天数: {self.task.remaining_days}天 | 预计完成: {self.task.estimated_date}"
        
        self.days_info = QLabel(days_text)
        if self.task.progress >= 100:
            self.days_info.setStyleSheet("font-size: 14px; color: #008000; font-weight: bold;")
        else:
            self.days_info.setStyleSheet("font-size: 14px; color: #000;")
        info_layout.addWidget(self.days_info)
        info_layout.addStretch()

        # 组装布局
        layout.addLayout(header_layout)
        layout.addWidget(self.progress_bar)
        layout.addLayout(info_layout)
        self.setLayout(layout)

        # 卡片样式
        self.setFixedHeight(100)
        if self.task.progress >= 100:
            self.setStyleSheet("""
                TaskCard {background-color: #f0fff0; border-radius: 8px; border: 2px solid #008000;}
                TaskCard:hover {border: 2px solid #006400;}
            """)
        elif self.task.status == "废止":
            self.setStyleSheet("""
                TaskCard {background-color: #f8f8f8; border-radius: 8px; border: 1px solid #ddd;}
                TaskCard:hover {border: 1px solid #aaa;}
            """)
        else:
            self.setStyleSheet("""
                TaskCard {background-color: white; border-radius: 8px; border: 1px solid #ddd;}
                TaskCard:hover {border: 1px solid #aaa;}
            """)

    def update_task(self, task: Task):
        """更新卡片显示的任务数据"""
        self.task = task
        
        # 检查进度是否为100%，如果是则显示"已完成"
        if task.progress >= 100:
            display_status = "已完成"
            display_color = QColor(0, 128, 0)  # 绿色表示已完成
        else:
            display_status = task.status
            display_color = Task.STATUS_COLORS.get(task.status, QColor(0, 0, 0))
        
        self.name_label.setText(task.name)
        self.status_label.setText(display_status)
        self.status_label.setStyleSheet(
            f"font-family: \"黑体\", sans-serif; color: {display_color.name()}; font-size: 19px;"
        )
        self.progress_bar.setValue(round(task.progress))
        
        # 根据是否完成设置不同的格式和颜色
        if task.progress >= 100:
            self.progress_bar.setFormat(" 100.00%")
            self.progress_bar.setStyleSheet(
                f"""QProgressBar {{font-size:16px;}}
                   QProgressBar::chunk {{background-color: #008000;}}"""
            )
        else:
            self.progress_bar.setFormat(f" {task.progress:.2f}%")
            self.progress_bar.setStyleSheet(
                f"""QProgressBar {{font-size:16px;}}
                   QProgressBar::chunk {{background-color: {Task.STATUS_COLORS.get(task.status, QColor(0,0,0)).name()};}}"""
            )
        
        # 更新剩余天数和预计日期
        if task.progress >= 100:
            days_text = "已完成"
            self.days_info.setStyleSheet("font-size: 14px; color: #008000; font-weight: bold;")
        else:
            days_text = f"剩余天数: {task.remaining_days}天 | 预计完成: {task.estimated_date}"
            self.days_info.setStyleSheet("font-size: 14px; color: #000;")
        
        self.days_info.setText(days_text)
        
        # 更新卡片样式
        if task.progress >= 100:
            self.setStyleSheet("""
                TaskCard {background-color: #f0fff0; border-radius: 8px; border: 2px solid #008000;}
                TaskCard:hover {border: 2px solid #006400;}
            """)
        elif task.status == "废止":
            self.setStyleSheet("""
                TaskCard {background-color: #f8f8f8; border-radius: 8px; border: 1px solid #ddd;}
                TaskCard:hover {border: 1px solid #aaa;}
            """)
        else:
            self.setStyleSheet("""
                TaskCard {background-color: white; border-radius: 8px; border: 1px solid #ddd;}
                TaskCard:hover {border: 1px solid #aaa;}
            """)


class TaskTreeWidget(QTreeWidget):
    """自定义树形控件，用于显示分类的任务"""
    taskSelected = pyqtSignal(int)  # 信号，传递任务索引
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(10)
        self.setAnimated(True)
        
        # 设置样式
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #f0f2f5;
                border: none;
                border-radius: 8px;
            }
            QTreeWidget::item {
                border-bottom: 1px solid #dee2e6;
            }
            QTreeWidget::item:selected {
                background-color: #e2e6ea;
            }
        """)
        
        # 创建分类项目
        self.active_category = QTreeWidgetItem(self)
        self.active_category.setText(0, "进行中")
        self.active_category.setExpanded(True)
        
        self.completed_category = QTreeWidgetItem(self)
        self.completed_category.setText(0, "已完成")
        self.completed_category.setExpanded(False)  # 默认折叠
        
        self.aborted_category = QTreeWidgetItem(self)
        self.aborted_category.setText(0, "已废止")
        self.aborted_category.setExpanded(False)  # 默认折叠
        
        # 为分类项目添加小三角形图标
        self.active_category.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        self.completed_category.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        self.aborted_category.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        
        # 连接选择信号
        self.itemSelectionChanged.connect(self.on_item_selected)
        
    def on_item_selected(self):
        """当项目被选中时触发"""
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        # 只有任务项（有数据的项）才发送信号
        if item.parent() is not None and hasattr(item, 'task_index'):
            self.taskSelected.emit(item.task_index)
    
    def clear_all_tasks(self):
        """清除所有任务项"""
        for i in range(self.active_category.childCount()):
            self.active_category.removeChild(self.active_category.child(0))
        for i in range(self.completed_category.childCount()):
            self.completed_category.removeChild(self.completed_category.child(0))
        for i in range(self.aborted_category.childCount()):
            self.aborted_category.removeChild(self.aborted_category.child(0))
    
    def add_task_item(self, task: Task, task_index: int, category: str):
        """添加任务项到指定分类"""
        if category == "active":
            parent = self.active_category
        elif category == "completed":
            parent = self.completed_category
        else:  # "aborted"
            parent = self.aborted_category
        
        item = QTreeWidgetItem(parent)
        item.task_index = task_index  # 存储任务索引
        
        # 创建卡片并设置到项目中
        card = TaskCard(task, self)
        self.setItemWidget(item, 0, card)
        
        # 设置项目大小以适应卡片
        item.setSizeHint(0, card.sizeHint())
        
        return item
    
    def find_task_item(self, task_index: int):
        """根据任务索引查找对应的项目"""
        # 在所有分类中查找
        for category_item in [self.active_category, self.completed_category, self.aborted_category]:
            for i in range(category_item.childCount()):
                child = category_item.child(i)
                if hasattr(child, 'task_index') and child.task_index == task_index:
                    return child
        return None
    
    def select_task(self, task_index: int):
        """选择指定索引的任务"""
        item = self.find_task_item(task_index)
        if item:
            self.setCurrentItem(item)
            self.scrollToItem(item)


class ProgressManager(QMainWindow):
    """主窗口：整合所有UI组件和交互逻辑"""
    def __init__(self, task_manager: TaskManager):
        super().__init__()
        self.task_manager = task_manager  # 依赖注入任务管理器
        self.current_task: Task = None    # 当前选中的任务
        self.current_task_id = None        # 记住当前任务的ID（用于恢复选择）
        self.current_subtask: SubTask = None  # 当前选中的子任务
        self.recent_x = self.task_manager.recent_x  # 同步配置
        self.chart_date_range = {}  # 存储每个任务的图表日期范围
        self.init_window()
        self.init_ui()

    def init_window(self):
        """初始化窗口基本属性"""
        self.setWindowTitle("任务进度管理器 by TZYLT&QianXiquq")
        self.setGeometry(100, 100, 1200, 800)
        self.setCentralWidget(QWidget())  # 初始化中心组件

    def init_ui(self):
        """构建完整UI布局"""
        main_layout = QHBoxLayout(self.centralWidget())

        # ---------------- 左侧任务树形面板 ----------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # 使用树形控件替代列表
        self.task_tree = TaskTreeWidget()
        self.task_tree.taskSelected.connect(self.on_task_selected)
        self.task_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_tree.customContextMenuRequested.connect(self.show_task_context_menu)
        self.populate_task_tree()

        # 添加任务按钮
        add_task_btn = QPushButton("添加新任务")
        add_task_btn.setStyleSheet("""
            QPushButton {background-color: #4CAF50; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold;}
            QPushButton:hover {background-color: #45a049;}
        """)
        add_task_btn.clicked.connect(self.add_new_task)

        # 组装左侧布局
        left_layout.addWidget(QLabel("任务列表"))
        left_layout.addWidget(self.task_tree)
        left_layout.addWidget(add_task_btn)

        # ---------------- 右侧功能面板 ----------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 模式切换与功能按钮行
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["详细信息", "图表分析"])
        self.mode_combo.currentIndexChanged.connect(self.switch_mode)

        # 今日总结按钮
        self.today_summary_btn = QPushButton("今日总结")
        self.today_summary_btn.setToolTip("显示今日有更新的任务总结")
        self.today_summary_btn.setStyleSheet("""
            QPushButton {background-color: #4CAF50; color: white; border: none; padding: 6px 10px; border-radius: 4px;}
            QPushButton:hover {background-color: #45a049;}
        """)
        self.today_summary_btn.clicked.connect(self.show_today_summary)

        # 设置按钮
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setToolTip("剩余天数计算的最近记录次数")
        self.settings_btn.setStyleSheet("""
            QPushButton {background-color: #1976D2; color: white; border: none; padding: 6px 10px; border-radius: 4px;}
            QPushButton:hover {background-color: #1565C0;}
        """)
        self.settings_btn.clicked.connect(self.open_settings_dialog)

        # 组装模式行
        mode_layout.addWidget(QLabel("显示模式:"))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.today_summary_btn)
        mode_layout.addWidget(self.settings_btn)
        mode_layout.addStretch()

        # 堆叠窗口（切换详细信息/图表模式）
        self.stacked_widget = QStackedWidget()
        self.init_detail_view()   # 详细信息面板
        self.init_chart_view()    # 图表分析面板
        self.stacked_widget.addWidget(self.detail_widget)
        self.stacked_widget.addWidget(self.chart_widget)

        # 组装右侧布局
        right_layout.addLayout(mode_layout)
        right_layout.addWidget(self.stacked_widget)

        # ---------------- 主布局整合 ----------------
        main_layout.addWidget(left_panel, 30)  # 左侧占30%宽度
        main_layout.addWidget(right_panel, 70) # 右侧占70%宽度

    def get_current_task_id(self):
        """获取当前任务的唯一标识符"""
        if self.current_task:
            # 使用任务在列表中的索引作为唯一标识符
            try:
                return self.task_manager.tasks.index(self.current_task)
            except ValueError:
                return None
        return None

    def populate_task_tree(self):
        """填充任务树形控件，按状态分类但保持原顺序"""
        # 清空所有任务项
        for i in range(self.task_tree.topLevelItemCount()):
            category_item = self.task_tree.topLevelItem(i)
            for j in range(category_item.childCount()):
                category_item.removeChild(category_item.child(0))
        
        # 添加任务，保持原有顺序
        for idx, task in enumerate(self.task_manager.tasks):
            # 确定任务所属的分类
            if task.progress >= 100:
                category = "completed"
            elif task.status == "废止":
                category = "aborted"
            else:
                category = "active"
            
            # 添加任务项到指定分类
            self.task_tree.add_task_item(task, idx, category)

    # ---------------- 详细信息面板 ----------------
    def init_detail_view(self):
        """初始化详细信息面板（任务概览+子任务+进度登记）"""
        self.detail_widget = QWidget()
        layout = QVBoxLayout(self.detail_widget)

        # 1. 任务概览
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

        # 2. 子任务列表
        self.subtask_list = QListWidget()
        self.subtask_list.setStyleSheet("""
            QListWidget {background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;}
        """)
        self.subtask_list.itemSelectionChanged.connect(self.on_subtask_selected)
        self.subtask_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.subtask_list.customContextMenuRequested.connect(self.show_subtask_context_menu)

        # 3. 进度登记
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

        # 组装进度登记布局
        progress_layout.addRow(QLabel("子任务:"), self.subtask_name_label)
        progress_layout.addRow(QLabel("日期:"), self.date_edit)
        progress_layout.addRow(QLabel("进度值:"), self.progress_input)
        progress_layout.addRow(QLabel("自动偏移:"), self.offset_input)
        progress_layout.addRow(self.register_btn)
        self.progress_group.setLayout(progress_layout)

        # 组装详细信息面板
        layout.addWidget(self.task_overview)
        layout.addWidget(QLabel("子任务列表"))
        layout.addWidget(self.subtask_list, 50)
        layout.addWidget(self.progress_group, 30)

    # ---------------- 图表分析面板 ----------------
    def init_chart_view(self):
        """初始化图表分析面板"""
        self.chart_widget = QWidget()
        layout = QVBoxLayout(self.chart_widget)

        # 图表类型和日期范围选择
        chart_control_layout = QHBoxLayout()
        
        # 图表模式选择
        chart_type_layout = QHBoxLayout()
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["总量模式", "增量模式"])
        self.chart_type_combo.currentIndexChanged.connect(self.update_chart)
        chart_type_layout.addWidget(QLabel("图表模式:"))
        chart_type_layout.addWidget(self.chart_type_combo)
        
        # 日期范围选择
        date_range_layout = QHBoxLayout()
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.dateChanged.connect(self.on_date_range_changed)
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.dateChanged.connect(self.on_date_range_changed)
        
        self.reset_date_range_btn = QPushButton("重置范围")
        self.reset_date_range_btn.setToolTip("重置为任务的全部日期范围")
        self.reset_date_range_btn.clicked.connect(self.reset_date_range)
        self.reset_date_range_btn.setStyleSheet("""
            QPushButton {background-color: #6c757d; color: white; border: none; padding: 4px 8px; border-radius: 4px;}
            QPushButton:hover {background-color: #5a6268;}
        """)
        
        date_range_layout.addWidget(QLabel("日期范围:"))
        date_range_layout.addWidget(self.start_date_edit)
        date_range_layout.addWidget(QLabel("到"))
        date_range_layout.addWidget(self.end_date_edit)
        date_range_layout.addWidget(self.reset_date_range_btn)
        
        # 组装控制行
        chart_control_layout.addLayout(chart_type_layout)
        chart_control_layout.addSpacing(20)
        chart_control_layout.addLayout(date_range_layout)
        chart_control_layout.addStretch()

        # 图表视图
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        # 组装图表面板
        layout.addLayout(chart_control_layout)
        layout.addWidget(self.chart_view)

    def on_date_range_changed(self):
        """日期范围改变时更新图表"""
        if self.current_task and self.stacked_widget.currentIndex() == 1:
            # 保存当前任务的日期范围设置
            task_id = id(self.current_task)
            self.chart_date_range[task_id] = {
                'start': self.start_date_edit.date().toString("yyyy-MM-dd"),
                'end': self.end_date_edit.date().toString("yyyy-MM-dd")
            }
            self.update_chart()

    def reset_date_range(self):
        """重置日期范围为任务的全部记录范围"""
        if not self.current_task:
            return
            
        # 收集所有记录日期
        all_dates = set()
        for st in self.current_task.sub_tasks:
            all_dates.update(st.records.keys())
        
        if not all_dates:
            return
            
        # 计算日期范围
        sorted_date_strs = sorted(all_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
        min_date = datetime.strptime(sorted_date_strs[0], "%Y-%m-%d")
        max_date = datetime.strptime(sorted_date_strs[-1], "%Y-%m-%d")
        
        # 设置日期控件
        self.start_date_edit.setDate(QDate(min_date.year, min_date.month, min_date.day))
        self.end_date_edit.setDate(QDate(max_date.year, max_date.month, max_date.day))

    def get_task_date_range(self, task):
        """获取任务的日期范围"""
        task_id = id(task)
        if task_id in self.chart_date_range:
            return self.chart_date_range[task_id]
        return None

    # ---------------- 事件处理 ----------------
    def on_task_selected(self, task_index):
        """任务树形控件选中事件：更新详细信息和图表"""
        if 0 <= task_index < len(self.task_manager.tasks):
            self.current_task = self.task_manager.tasks[task_index]
            self.current_task_id = task_index
            self.update_detail_view()
        else:
            self.current_task = None
            self.current_task_id = None
            self.update_detail_view()

    def on_subtask_selected(self):
        """子任务列表选中事件：更新进度登记面板"""
        if not self.current_task:
            self.current_subtask = None
            self.subtask_name_label.setText("选择子任务")
            return

        selected_items = self.subtask_list.selectedItems()
        if not selected_items:
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
        """登记子任务进度"""
        if not self.current_task or not self.current_subtask:
            QMessageBox.warning(self, "错误", "请先选择任务和子任务")
            return

        # 获取输入数据
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        progress = self.progress_input.value() - self.offset_input.value()
        self.current_subtask.add_record(date_str, progress)
        self.current_subtask.auto_offset = self.offset_input.value()

        # 保存并更新UI
        self.task_manager.save_tasks()
        
        # 记住当前任务ID
        current_task_id = self.get_current_task_id()
        
        # 刷新任务树
        self.populate_task_tree()
        
        # 恢复选择
        if current_task_id is not None:
            self.task_tree.select_task(current_task_id)
            self.current_task = self.task_manager.tasks[current_task_id]
        
        # 更新详细视图
        self.update_detail_view()

    def switch_mode(self, index):
        """切换显示模式（详细信息/图表）"""
        self.stacked_widget.setCurrentIndex(index)
        if index == 1:  # 切换到图表模式时更新图表
            self.update_chart()

    def update_detail_view(self):
        """更新详细信息面板"""
        if not self.current_task:
            # 清空面板
            self.task_name_label.setText("")
            self.task_progress_bar.setValue(0)
            self.task_info_label.setText("")
            self.subtask_list.clear()
            self.subtask_name_label.setText("选择子任务")
            return

        # 更新任务概览
        self.task_name_label.setText(self.current_task.name)
        self.task_progress_bar.setValue(round(self.current_task.progress))
        
        # 根据是否完成设置不同的格式
        if self.current_task.progress >= 100:
            self.task_progress_bar.setFormat("100.00%")
            status_display = "已完成"
        else:
            self.task_progress_bar.setFormat(f"{self.current_task.progress:.2f}%")
            status_display = self.current_task.status
            
        self.task_info_label.setText(
            f"状态: {status_display} | 剩余天数: {self.current_task.remaining_days} | 预计完成: {self.current_task.estimated_date}"
        )

        # 更新子任务列表
        self.subtask_list.clear()
        for subtask in self.current_task.sub_tasks:
            item = QListWidgetItem()
            card = self.create_subtask_card(subtask)
            item.setSizeHint(card.sizeHint())
            self.subtask_list.addItem(item)
            self.subtask_list.setItemWidget(item, card)

        # 初始化日期范围控件
        self.init_date_range_controls()
        
        # 更新图表（确保图表与当前任务同步）
        self.update_chart()

    def init_date_range_controls(self):
        """初始化日期范围控件"""
        if not self.current_task:
            return
            
        # 收集所有记录日期
        all_dates = set()
        for st in self.current_task.sub_tasks:
            all_dates.update(st.records.keys())
        
        if not all_dates:
            # 如果没有记录，设置默认范围（当前日期前后各30天）
            today = QDate.currentDate()
            self.start_date_edit.setDate(today.addDays(-30))
            self.end_date_edit.setDate(today.addDays(30))
            return
            
        # 计算日期范围
        sorted_date_strs = sorted(all_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
        min_date = datetime.strptime(sorted_date_strs[0], "%Y-%m-%d")
        max_date = datetime.strptime(sorted_date_strs[-1], "%Y-%m-%d")
        
        # 检查是否有保存的日期范围设置
        saved_range = self.get_task_date_range(self.current_task)
        if saved_range:
            try:
                start_date = datetime.strptime(saved_range['start'], "%Y-%m-%d")
                end_date = datetime.strptime(saved_range['end'], "%Y-%m-%d")
                self.start_date_edit.setDate(QDate(start_date.year, start_date.month, start_date.day))
                self.end_date_edit.setDate(QDate(end_date.year, end_date.month, end_date.day))
            except ValueError:
                # 如果保存的格式有问题，使用默认范围
                self.start_date_edit.setDate(QDate(min_date.year, min_date.month, min_date.day))
                self.end_date_edit.setDate(QDate(max_date.year, max_date.month, max_date.day))
        else:
            # 使用任务的完整日期范围
            self.start_date_edit.setDate(QDate(min_date.year, min_date.month, min_date.day))
            self.end_date_edit.setDate(QDate(max_date.year, max_date.month, max_date.day))

    def update_chart(self):
        """更新图表数据"""
        if not self.current_task:
            self.chart_view.setChart(QChart())
            return

        chart = QChart()
        chart.setTitle(f"{self.current_task.name} - 进度分析")
        chart.legend().setVisible(True)
        chart.setAnimationOptions(QChart.SeriesAnimations)

        # 坐标轴
        axis_x = QDateTimeAxis()
        axis_x.setFormat("yyyy-MM-dd")
        axis_x.setTitleText("日期")
        axis_y = QValueAxis()
        axis_y.setTitleText("进度 (%)")

        # 获取日期范围
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        
        # 收集指定日期范围内的记录
        filtered_dates = set()
        for st in self.current_task.sub_tasks:
            for date_str in st.records.keys():
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if start_date <= date_obj <= end_date:
                        filtered_dates.add(date_str)
                except ValueError:
                    continue
        
        if not filtered_dates:
            # 如果没有数据，显示空图表
            self.chart_view.setChart(chart)
            return

        # 日期排序
        sorted_date_strs = sorted(filtered_dates, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
        sorted_date_objs = [datetime.strptime(d, "%Y-%m-%d") for d in sorted_date_strs]
        axis_x.setRange(min(sorted_date_objs), max(sorted_date_objs) + timedelta(days=1))

        # 总进度序列
        total_series = QLineSeries()
        total_series.setName("总进度")
        total_series.setColor(QColor(0, 0, 0))
        total_series.setPointsVisible(True)

        # 子任务进度序列
        subtask_series = []
        for i, st in enumerate(self.current_task.sub_tasks):
            series = QLineSeries()
            series.setName(st.name)
            series.setColor(QColor(random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)))
            series.setPointsVisible(True)
            subtask_series.append(series)

        # 根据图表模式计算数据
        chart_mode = self.chart_type_combo.currentText()
        current_st_progress = [0] * len(self.current_task.sub_tasks)

        if chart_mode == "增量模式":
            # 增量模式：显示每日进度变化
            prev_total = 0
            prev_st_progress = [0] * len(self.current_task.sub_tasks)
            max_increment = 0

            for date_str in sorted_date_strs:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                timestamp = date_obj.timestamp() * 1000

                # 更新子任务当前进度
                for i, st in enumerate(self.current_task.sub_tasks):
                    if date_str in st.records:
                        current_st_progress[i] = min(st.records[date_str], st.total)

                # 计算总进度和增量
                total_completed = sum(current_st_progress)
                total_percent = (total_completed / self.current_task.total * 100) if self.current_task.total > 0 else 0
                total_delta = total_percent - prev_total
                total_series.append(timestamp, max(0, total_delta))
                prev_total = total_percent

                # 计算子任务增量
                for i, st in enumerate(self.current_task.sub_tasks):
                    st_percent = (current_st_progress[i] / st.total * 100) if st.total > 0 else 0
                    st_delta = st_percent - prev_st_progress[i]
                    subtask_series[i].append(timestamp, max(0, st_delta))
                    prev_st_progress[i] = st_percent
                    max_increment = max(max_increment, max(0, st_delta), max(0, total_delta))

            # 设置Y轴范围（增量模式）
            axis_y.setRange(0, max_increment * 1.2 if max_increment > 0 else 10)
            axis_y.setTickCount(6)

        else:
            # 总量模式：显示累计进度
            for date_str in sorted_date_strs:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                timestamp = date_obj.timestamp() * 1000

                # 更新子任务当前进度
                for i, st in enumerate(self.current_task.sub_tasks):
                    if date_str in st.records:
                        current_st_progress[i] = min(st.records[date_str], st.total)

                # 计算总进度
                total_completed = sum(current_st_progress)
                total_percent = (total_completed / self.current_task.total * 100) if self.current_task.total > 0 else 0
                total_series.append(timestamp, total_percent)

                # 计算子任务进度
                for i, st in enumerate(self.current_task.sub_tasks):
                    st_percent = (current_st_progress[i] / st.total * 100) if st.total > 0 else 0
                    subtask_series[i].append(timestamp, st_percent)

            # 设置Y轴范围（总量模式）
            axis_y.setRange(0, 100)
            axis_y.setTickCount(11)

        # 组装图表
        chart.addSeries(total_series)
        for series in subtask_series:
            chart.addSeries(series)
        chart.addAxis(axis_x, Qt.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignLeft)
        for series in [total_series] + subtask_series:
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

        self.chart_view.setChart(chart)
        # 延迟添加数据标签（确保图表渲染完成）
        QTimer.singleShot(100, self.add_chart_data_labels)

    def add_chart_data_labels(self):
        """为图表添加数据标签"""
        chart = self.chart_view.chart()
        scene = self.chart_view.scene()
        if not chart or not scene:
            return

        # 清除旧标签
        for item in list(scene.items()):
            if isinstance(item, QGraphicsSimpleTextItem):
                scene.removeItem(item)

        # 为每个数据点添加标签
        for series in chart.series():
            try:
                points = series.pointsVector()
            except Exception:
                continue
            for point in points:
                scene_point = chart.mapToPosition(point)
                label = QGraphicsSimpleTextItem(f"{point.y():.2f}")
                # 调整标签位置（避免超出图表范围）
                label.setPos(scene_point.x() + 5, scene_point.y() - 15)
                plot_area = chart.plotArea()
                if label.pos().y() < plot_area.top():
                    label.moveBy(0, 25)
                # 标签样式
                label.setBrush(QColor(0, 0, 0))
                font = label.font()
                font.setPointSize(8)
                label.setFont(font)
                scene.addItem(label)

    # ---------------- 右键菜单 ----------------
    def show_task_context_menu(self, pos):
        """任务列表右键菜单：状态修改、重命名、删除等"""
        item = self.task_tree.itemAt(pos)
        if not item:
            return
        
        # 确保选中的是任务项，而不是分类项
        if item.parent() is None:
            return
            
        idx = item.task_index
        if idx < 0 or idx >= len(self.task_manager.tasks):
            return
        task = self.task_manager.tasks[idx]

        # 如果任务已完成，不提供状态修改选项
        if task.progress >= 100:
            # 构建菜单（只提供重命名和删除）
            menu = QMenu(self)
            
            # 上下移动
            move_up_act = menu.addAction("上移")
            move_up_act.triggered.connect(lambda: self.move_task(idx, -1))
            move_up_act.setEnabled(idx > 0)

            move_down_act = menu.addAction("下移")
            move_down_act.triggered.connect(lambda: self.move_task(idx, 1))
            move_down_act.setEnabled(idx < len(self.task_manager.tasks) - 1)

            menu.addSeparator()
            
            # 不提供状态修改，已完成任务状态固定
            menu.addAction("重命名", lambda: self.rename_task(task))
            menu.addAction("添加子任务", lambda: self.add_subtask(task))
            menu.addAction("删除任务", lambda: self.delete_task(task))
            
            # 显示菜单
            menu.exec_(self.task_tree.mapToGlobal(pos))
            return

        # 构建菜单
        menu = QMenu(self)

        # 上下移动
        move_up_act = menu.addAction("上移")
        move_up_act.triggered.connect(lambda: self.move_task(idx, -1))
        move_up_act.setEnabled(idx > 0)

        move_down_act = menu.addAction("下移")
        move_down_act.triggered.connect(lambda: self.move_task(idx, 1))
        move_down_act.setEnabled(idx < len(self.task_manager.tasks) - 1)

        menu.addSeparator()

        # 状态修改（不包含已完成，因为已完成是自动设置的）
        status_menu = menu.addMenu("更改状态")
        for status in ["进行中", "暂停", "废止"]:
            act = status_menu.addAction(status)
            act.triggered.connect(lambda _, s=status: self.change_task_status(task, s))

        # 其他操作
        menu.addAction("重命名", lambda: self.rename_task(task))
        menu.addAction("添加子任务", lambda: self.add_subtask(task))
        menu.addAction("删除任务", lambda: self.delete_task(task))

        # 显示菜单
        menu.exec_(self.task_tree.mapToGlobal(pos))

    def show_subtask_context_menu(self, pos):
        """子任务列表右键菜单：重命名、修改总量、删除等"""
        if not self.current_task:
            return

        item = self.subtask_list.itemAt(pos)
        if not item:
            return

        idx = self.subtask_list.row(item)
        if idx < 0 or idx >= len(self.current_task.sub_tasks):
            return

        # 构建菜单
        menu = QMenu(self)

        # 上下移动
        move_up_act = menu.addAction("上移")
        move_up_act.triggered.connect(lambda: self.move_subtask(idx, -1))
        move_up_act.setEnabled(idx > 0)

        move_down_act = menu.addAction("下移")
        move_down_act.triggered.connect(lambda: self.move_subtask(idx, 1))
        move_down_act.setEnabled(idx < len(self.current_task.sub_tasks) - 1)

        menu.addSeparator()

        # 其他操作
        menu.addAction("重命名子任务", lambda: self.rename_subtask(idx))
        menu.addAction("修改任务总量", lambda: self.change_subtask_total(idx))
        menu.addAction("删除子任务", lambda: self.delete_subtask(idx))

        # 显示菜单
        menu.exec_(self.subtask_list.mapToGlobal(pos))

    # ---------------- 任务/子任务操作 ----------------
    def move_task(self, idx, direction):
        """移动任务位置（direction: -1=上移，1=下移）"""
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.task_manager.tasks):
            return
        
        # 交换位置
        self.task_manager.tasks[idx], self.task_manager.tasks[new_idx] = self.task_manager.tasks[new_idx], self.task_manager.tasks[idx]
        self.task_manager.save_tasks()
        
        # 记住移动后任务索引
        current_task_id = new_idx
        
        # 刷新任务树
        self.populate_task_tree()
        
        # 恢复选择
        if current_task_id is not None:
            self.task_tree.select_task(current_task_id)
            self.current_task = self.task_manager.tasks[current_task_id]
        
        # 更新详细视图
        self.update_detail_view()

    def change_task_status(self, task: Task, status: str):
        """修改任务状态"""
        # 如果任务进度已达到100%，不允许修改状态
        if task.progress >= 100:
            QMessageBox.information(self, "提示", "任务已完成，无法修改状态")
            return
        
        # 记住当前任务ID
        current_task_id = self.get_current_task_id()
        
        task.status = status
        self.task_manager.save_tasks()
        
        # 刷新任务树
        self.populate_task_tree()
        
        # 恢复选择
        if current_task_id is not None:
            self.task_tree.select_task(current_task_id)
            self.current_task = self.task_manager.tasks[current_task_id]
        
        if task == self.current_task:
            self.update_detail_view()

    def rename_task(self, task: Task):
        """重命名任务"""
        new_name, ok = QInputDialog.getText(self, "重命名任务", "输入新任务名称:", text=task.name)
        if ok and new_name.strip():
            # 记住当前任务ID
            current_task_id = self.get_current_task_id()
            
            task.name = new_name.strip()
            self.task_manager.save_tasks()
            
            # 刷新任务树
            self.populate_task_tree()
            
            # 恢复选择
            if current_task_id is not None:
                self.task_tree.select_task(current_task_id)
                self.current_task = self.task_manager.tasks[current_task_id]
            
            if task == self.current_task:
                self.update_detail_view()

    def add_subtask(self, task: Task):
        """为任务添加子任务"""
        # 如果任务已完成，不允许添加子任务
        if task.progress >= 100:
            QMessageBox.information(self, "提示", "任务已完成，无法添加子任务")
            return
        
        # 输入子任务名称
        name, ok = QInputDialog.getText(self, "添加子任务", "输入子任务名称:")
        if not (ok and name.strip()):
            return
        # 输入子任务总量
        total, ok = QInputDialog.getInt(self, "设置子任务总量", "输入任务总量:", value=100, min=1)
        if not ok:
            return
        
        # 记住当前任务ID
        current_task_id = self.get_current_task_id()
        
        # 添加子任务
        task.add_subtask(SubTask(name.strip(), total))
        self.task_manager.save_tasks()
        
        # 刷新任务树
        self.populate_task_tree()
        
        # 恢复选择
        if current_task_id is not None:
            self.task_tree.select_task(current_task_id)
            self.current_task = self.task_manager.tasks[current_task_id]
        
        if task == self.current_task:
            self.update_detail_view()

    def delete_task(self, task: Task):
        """删除任务"""
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除任务 '{task.name}' 及其所有子任务吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 检查删除的是否是当前任务
            is_current = (task == self.current_task)
            
            # 删除任务
            self.task_manager.tasks.remove(task)
            self.task_manager.save_tasks()
            
            # 刷新任务树
            self.populate_task_tree()
            
            if is_current:
                # 如果删除的是当前任务，清空详细视图
                self.current_task = None
                self.current_task_id = None
                self.update_detail_view()
            else:
                # 否则，重新选中当前任务（因为索引可能改变，所以需要重新查找）
                if self.current_task:
                    # 重新获取当前任务在列表中的索引
                    try:
                        index = self.task_manager.tasks.index(self.current_task)
                        self.task_tree.select_task(index)
                    except ValueError:
                        # 如果当前任务不在列表中（这不应该发生，除非有bug），清空
                        self.current_task = None
                        self.current_task_id = None
                        self.update_detail_view()

    def move_subtask(self, idx, direction):
        """移动子任务位置（direction: -1=上移，1=下移）"""
        if not self.current_task:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.current_task.sub_tasks):
            return
        # 交换位置
        self.current_task.sub_tasks[idx], self.current_task.sub_tasks[new_idx] = self.current_task.sub_tasks[new_idx], self.current_task.sub_tasks[idx]
        self.task_manager.save_tasks()
        self.update_detail_view()
        # 重新选中子任务
        self.subtask_list.setCurrentRow(new_idx)

    def rename_subtask(self, idx: int):
        """重命名子任务"""
        if not self.current_task:
            return
        subtask = self.current_task.sub_tasks[idx]
        new_name, ok = QInputDialog.getText(self, "重命名子任务", "输入新子任务名称:", text=subtask.name)
        if ok and new_name.strip():
            subtask.name = new_name.strip()
            self.task_manager.save_tasks()
            self.update_detail_view()

    def change_subtask_total(self, idx: int):
        """修改子任务总量"""
        if not self.current_task:
            return
        subtask = self.current_task.sub_tasks[idx]
        new_total, ok = QInputDialog.getInt(
            self, "修改子任务总量", "输入新的总量:", value=subtask.total, min=1
        )
        if ok:
            subtask.total = new_total
            self.task_manager.save_tasks()
            self.update_detail_view()

    def delete_subtask(self, idx: int):
        """删除子任务"""
        if not self.current_task:
            return
        subtask = self.current_task.sub_tasks[idx]
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除子任务 '{subtask.name}' 吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 清除当前选中的子任务（如果是被删除的）
            if self.current_subtask == subtask:
                self.current_subtask = None
                self.subtask_name_label.setText("选择子任务")
            # 删除并保存
            self.current_task.sub_tasks.pop(idx)
            self.task_manager.save_tasks()
            self.update_detail_view()

    # ---------------- 辅助功能 ----------------
    def add_new_task(self):
        """添加新任务"""
        name, ok = QInputDialog.getText(self, "添加新任务", "输入任务名称:")
        if ok and name.strip():
            # 创建新任务
            new_task = Task(name.strip())
            self.task_manager.tasks.append(new_task)
            self.task_manager.save_tasks()
            
            # 设置当前任务为新任务
            self.current_task = new_task
            
            # 记住当前任务ID
            current_task_id = len(self.task_manager.tasks) - 1
            
            # 刷新任务树
            self.populate_task_tree()
            
            # 选择新任务
            if current_task_id is not None:
                self.task_tree.select_task(current_task_id)
                self.current_task = self.task_manager.tasks[current_task_id]
            
            # 更新详细视图
            self.update_detail_view()

    def show_today_summary(self):
        """显示今日任务更新总结"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        summary = []

        # 遍历所有任务收集今日更新
        for task in self.task_manager.tasks:
            task_summary = []
            total_before = 0  # 今日前总完成量
            total_after = 0   # 今日后总完成量
            st_updates = []   # 子任务更新记录

            # 处理每个子任务
            for st in task.sub_tasks:
                # 今日前的最新记录
                prev_records = [(d, p) for d, p in st.records.items() if d < today_str]
                prev_val = max(prev_records, key=lambda x: x[0])[1] if prev_records else 0
                total_before += min(prev_val, st.total)

                # 今日及之前的最新记录
                all_records = [(d, p) for d, p in st.records.items() if d <= today_str]
                curr_val = max(all_records, key=lambda x: x[0])[1] if all_records else 0
                total_after += min(curr_val, st.total)

                # 检查是否有今日更新
                if today_str in st.records:
                    change = max(0, curr_val - prev_val)
                    prev_pct = (min(prev_val, st.total) / st.total * 100) if st.total > 0 else 0
                    curr_pct = (min(curr_val, st.total) / st.total * 100) if st.total > 0 else 0
                    if change > 0 or abs(curr_pct - prev_pct) > 1e-6:
                        st_updates.append(f"    {st.name} : {change}, {prev_pct:.2f}% -> {curr_pct:.2f}%")

            # 任务整体更新
            total_pct_before = (total_before / task.total * 100) if task.total > 0 else 0
            total_pct_after = (total_after / task.total * 100) if task.total > 0 else 0
            total_change = total_after - total_before

            # 只有有更新的任务才加入总结
            if st_updates or total_change > 0 or abs(total_pct_after - total_pct_before) > 1e-6:
                task_summary.append(f"{task.name} : {total_change}, {total_pct_before:.2f}% -> {total_pct_after:.2f}%")
                task_summary.extend(st_updates)
                summary.extend(task_summary)
                summary.append("")  # 空行分隔任务

        # 显示总结弹窗
        dlg = QDialog(self)
        dlg.setWindowTitle("今日总结")
        dlg_layout = QVBoxLayout(dlg)

        if summary:
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText("\n".join(summary).strip())
            dlg_layout.addWidget(text_edit)
        else:
            dlg_layout.addWidget(QLabel("今日没有任务更新"))

        # 关闭按钮
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        dlg_layout.addWidget(btns)

        dlg.resize(700, 500)
        dlg.exec_()

    def open_settings_dialog(self):
        """打开设置对话框（修改recent_x）"""
        dlg = QDialog(self)
        dlg.setWindowTitle("设置")
        dlg_layout = QVBoxLayout(dlg)

        # 滚动区域（支持未来扩展更多设置）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form_layout = QFormLayout(content)
        scroll.setWidget(content)

        # 最近记录次数设置
        x_spin = QSpinBox()
        x_spin.setRange(1, 365)
        x_spin.setValue(self.task_manager.recent_x)
        form_layout.addRow(QLabel("剩余天数计算的最近记录次数："), x_spin)

        dlg_layout.addWidget(scroll)

        # 确认/取消按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dlg_layout.addWidget(btns)

        # 确认逻辑
        def on_ok():
            new_x = x_spin.value()
            if new_x == self.task_manager.recent_x:
                dlg.accept()
                return

            # 更新配置
            self.task_manager.recent_x = new_x
            self.task_manager.save_config()
            Task.RECENT_X = new_x  # 立即生效
            self.recent_x = new_x

            # 记住当前任务ID
            current_task_id = self.get_current_task_id()
            
            # 刷新任务树
            self.populate_task_tree()
            
            # 恢复选择
            if current_task_id is not None:
                self.task_tree.select_task(current_task_id)
                self.current_task = self.task_manager.tasks[current_task_id]
            
            if self.current_task:
                self.update_detail_view()
                self.select_current_task_in_tree()

            dlg.accept()

        btns.accepted.connect(on_ok)
        btns.rejected.connect(dlg.reject)

        dlg.resize(480, 320)
        dlg.exec_()

    def refresh_task_cards(self):
        """刷新所有任务卡片数据"""
        # 在刷新前记住当前选中的任务
        current_task_id = self.get_current_task_id()
        
        # 刷新任务树
        self.populate_task_tree()
        
        # 恢复选择
        if current_task_id is not None and 0 <= current_task_id < len(self.task_manager.tasks):
            # 恢复当前任务对象
            self.current_task = self.task_manager.tasks[current_task_id]
            # 在树中选择对应的项
            self.task_tree.select_task(current_task_id)
            # 更新详细视图
            self.update_detail_view()
        elif self.task_manager.tasks:
            # 如果没有之前的选择但有任务，选择第一个
            self.task_tree.select_task(0)
            self.current_task = self.task_manager.tasks[0]
            self.update_detail_view()
        else:
            # 没有任务时清空
            self.current_task = None
            self.update_detail_view()

    def select_current_task_in_tree(self):
        """在任务树中选中当前任务"""
        if not self.current_task:
            return
        
        # 查找当前任务在列表中的索引
        try:
            task_index = self.task_manager.tasks.index(self.current_task)
            self.task_tree.select_task(task_index)
        except ValueError:
            pass

    def create_subtask_card(self, subtask: SubTask):
        """创建子任务卡片（用于子任务列表）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)

        # 子任务名称
        name_label = QLabel(subtask.name)
        name_label.setStyleSheet("font-family: \"黑体\", sans-serif; font-weight: bold;")
        layout.addWidget(name_label)

        # 子任务进度条
        progress = (subtask.completed / subtask.total * 100) if subtask.total > 0 else 0
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(round(progress))
        progress_bar.setFormat(f"{progress:.2f}% ({subtask.completed}/{subtask.total})")
        layout.addWidget(progress_bar)

        return widget