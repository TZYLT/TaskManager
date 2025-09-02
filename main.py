import sys
from PyQt5.QtWidgets import QApplication
from ui import ProgressManager
from tasks import TaskManager


if __name__ == "__main__":
    # 1. 初始化Qt应用
    app = QApplication(sys.argv)
    
    # 2. 初始化任务管理器（加载数据和配置）
    task_manager = TaskManager()
    
    # 3. 初始化主窗口（注入任务管理器）
    window = ProgressManager(task_manager)
    
    # 4. 显示窗口并启动事件循环
    window.show()
    sys.exit(app.exec_())
