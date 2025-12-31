import os
import json
from datetime import datetime
from src.reports.monthly_report import MonthlyReport

def generate_full_prompt():
    # 初始化月报生成器，时间范围设定为 2025年11月
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 30)
    report = MonthlyReport(start_date=start_date, end_date=end_date)
    
    # 1. 获取统计和所有数据
    stats = report._get_stats()
    
    # 2. 调用修改后的逻辑，获取包含全部原文的 JSON 数据
    ai_data = report._get_updates_for_ai(stats)
    
    # 3. 加载 Prompt 模板
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_file = os.path.join(project_root, 'src', 'analyzers', 'prompts', 'monthly_insight.prompt.txt')
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # 4. 组装 Prompt
    prompt = prompt_template.replace('{month_str}', '2025年11月')
    prompt = prompt.replace('{battleground_json}', ai_data['battleground_json'])
    prompt = prompt.replace('{blogs_json}', ai_data['blogs_json'])
    
    # 5. 写入文件
    output_path = 'data/november_report_prompt.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"完整 Prompt 已生成，共包含 {stats['total_count']} 条记录，保存至: {output_path}")
    print(f"文件大小约为: {os.path.getsize(output_path) / 1024:.2f} KB")

if __name__ == "__main__":
    generate_full_prompt()
