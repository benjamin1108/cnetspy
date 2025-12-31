
import os
import sys
from datetime import datetime

# 添加项目路径到系统路径
sys.path.append(os.getcwd())

from src.reports import WeeklyReport
from src.scheduler.jobs.report_job import _send_report

def run_real_report():
    print("=" * 50)
    print("正在基于真实数据生成 2025-W47 周报...")
    print("=" * 50)
    
    # 设定统计周期 (2025-11-17 到 2025-11-23)
    start_date = datetime(2025, 11, 17)
    end_date = datetime(2025, 11, 23)
    
    try:
        # 1. 调用真实的 WeeklyReport 生成引擎
        report = WeeklyReport(start_date=start_date, end_date=end_date)
        content = report.generate()
        
        if not content:
            print("错误：生成的报告内容为空。请检查数据库中是否有对应日期的 analyzed 数据。")
            return

        # 2. 保存报告到本地
        filepath = report.save()
        print(f"✅ 报告生成成功并已保存: {filepath}")
        
        # 3. 通过真实渠道推送
        # 注意：这里会调用我们重构后的 _send_report，它会发送带有 ActionCard 按钮的消息
        print("🚀 正在推送至钉钉...")
        _send_report(report, content, ["dingtalk"], "周报")
        
        print("\n任务完成！请检查您的钉钉。")
        
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_real_report()
