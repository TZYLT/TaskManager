import json
from datetime import datetime, timedelta
from PyQt5.QtGui import QColor


class SubTask:
    """子任务数据类：存储子任务信息及进度记录"""
    def __init__(self, name, total=100, auto_offset=0):
        self.name = name
        self.total = total
        self.auto_offset = auto_offset
        self.records = {}  # {date_str: progress_value}

    @property
    def progress(self):
        """获取最新进度值"""
        if not self.records:
            return 0
        last_date = max(self.records.keys())
        return self.records[last_date]

    @property
    def completed(self):
        """获取已完成量（不超过总量）"""
        return min(self.progress, self.total)

    def add_record(self, date, progress):
        """添加进度记录"""
        self.records[date] = progress

    def to_dict(self):
        """序列化为字典（用于保存）"""
        return {
            "name": self.name,
            "total": self.total,
            "auto_offset": self.auto_offset,
            "records": self.records
        }

    @classmethod
    def from_dict(cls, data):
        """从字典反序列化为SubTask实例（用于加载）"""
        subtask = cls(
            data.get("name", ""),
            data.get("total", 100),
            data.get("auto_offset", 0)
        )
        subtask.records = {k: v for k, v in data.get("records", {}).items()}
        return subtask


class Task:
    """任务数据类：包含多个子任务，计算整体进度和预估时间"""
    # 状态颜色映射
    STATUS_COLORS = {
        "进行中": QColor(50, 205, 50),    # 绿色
        "暂停": QColor(255, 215, 0),      # 黄色
        "废止": QColor(220, 20, 60)       # 红色
    }
    # 计算剩余天数时使用的最近样本数（默认5）
    RECENT_X = 5

    def __init__(self, name):
        self.name = name
        self.status = "进行中"
        self.sub_tasks = []
        self.start_date = datetime.now().strftime("%Y-%m-%d")

    def add_subtask(self, subtask):
        """添加子任务"""
        self.sub_tasks.append(subtask)

    @property
    def total(self):
        """任务总目标量（所有子任务总量之和）"""
        return sum(st.total for st in self.sub_tasks)

    @property
    def completed(self):
        """任务总完成量（所有子任务完成量之和）"""
        return sum(st.completed for st in self.sub_tasks)

    @property
    def progress(self):
        """任务整体进度百分比"""
        return (self.completed / self.total * 100) if self.total > 0 else 0

    @property
    def remaining_days(self):
        """估算剩余天数（基于最近RECENT_X次记录）"""
        if not self.sub_tasks:
            return 0

        # 收集所有子任务的记录日期
        all_dates = set()
        for st in self.sub_tasks:
            all_dates.update(st.records.keys())
        if not all_dates:
            return 0

        # 日期排序并构建每日总完成量快照
        try:
            sorted_date_objs = sorted(datetime.strptime(d, "%Y-%m-%d") for d in all_dates)
        except Exception:
            return 0

        snapshots = []
        for date_obj in sorted_date_objs:
            date_str = date_obj.strftime("%Y-%m-%d")
            daily_total = 0
            for st in self.sub_tasks:
                # 取当前日期及之前的最新记录
                valid_dates = [d for d in st.records.keys() if d <= date_str]
                if valid_dates:
                    daily_total += min(st.records[max(valid_dates)], st.total)
            snapshots.append((date_obj, daily_total))

        # 取最近RECENT_X个样本（不足则取全部）
        sample_count = min(Task.RECENT_X, len(snapshots))
        if sample_count < 2:
            return 0
        samples = snapshots[-sample_count:]

        # 计算平均日增量并估算剩余天数
        oldest_val = samples[0][1]
        newest_val = samples[-1][1]
        change = newest_val - oldest_val
        avg_daily = change / sample_count  # 按样本数计算日均增量

        if avg_daily <= 0:
            return 0
        remaining = max(0, self.total - newest_val)
        return max(1, round(remaining / avg_daily))

    @property
    def estimated_date(self):
        """基于过去7天记录预测完成日期"""
        if not self.sub_tasks:
            return "N/A"

        all_dates = set()
        for st in self.sub_tasks:
            all_dates.update(st.records.keys())
        if not all_dates:
            return "N/A"

        # 日期处理与时间范围计算
        sorted_dates = sorted(datetime.strptime(d, "%Y-%m-%d") for d in all_dates)
        now = datetime.now()
        start_date = max(min(sorted_dates), now - timedelta(days=7))

        # 计算起始和当前完成量
        start_completion = 0
        end_completion = 0
        for st in self.sub_tasks:
            # 起始日期前的最新记录
            start_records = [p for d, p in st.records.items() if datetime.strptime(d, "%Y-%m-%d") <= start_date]
            start_completion += max(start_records) if start_records else 0
            # 当前完成量
            end_completion += st.completed

        # 计算预估日期
        days_span = (now - start_date).days
        if days_span <= 0 or end_completion - start_completion <= 0:
            return "N/A"
        avg_daily = (end_completion - start_completion) / days_span
        remaining = max(0, self.total - end_completion)
        remaining_days = max(1, round(remaining / avg_daily))
        return (now + timedelta(days=remaining_days)).strftime("%Y-%m-%d")

    def to_dict(self):
        """序列化为字典（用于保存）"""
        return {
            "name": self.name,
            "status": self.status,
            "start_date": self.start_date,
            "sub_tasks": [st.to_dict() for st in self.sub_tasks]
        }

    @classmethod
    def from_dict(cls, data):
        """从字典反序列化为Task实例（用于加载）"""
        task = cls(data.get("name", ""))
        task.status = data.get("status", "进行中")
        task.start_date = data.get("start_date", datetime.now().strftime("%Y-%m-%d"))
        task.sub_tasks = [SubTask.from_dict(st) for st in data.get("sub_tasks", [])]
        return task


class TaskManager:
    """任务管理器：负责任务数据的加载、保存和配置同步"""
    def __init__(self):
        self.data_path = "tasks.json"    # 任务数据文件
        self.config_path = "config.json" # 配置文件
        self._tasks = []                 # 任务列表
        self.recent_x = Task.RECENT_X    # 剩余天数计算的样本数

        # 初始化时加载配置和任务
        self.load_config()
        self.load_tasks()

    @property
    def tasks(self):
        """获取任务列表（只读访问，修改后需调用save_tasks保存）"""
        return self._tasks

    def load_tasks(self):
        """从文件加载任务数据"""
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._tasks = [Task.from_dict(t) for t in data]
        except FileNotFoundError:
            self._tasks = []
        except Exception:
            self._tasks = []

    def save_tasks(self):
        """将任务数据保存到文件"""
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self._tasks], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_config(self):
        """从文件加载配置（主要是recent_x）"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self.recent_x = int(cfg.get("recent_x", self.recent_x))
        except Exception:
            self.recent_x = Task.RECENT_X
        # 同步配置到Task类（确保剩余天数计算用最新值）
        Task.RECENT_X = self.recent_x

    def save_config(self):
        """将配置保存到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"recent_x": self.recent_x}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
