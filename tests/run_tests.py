#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CI/CD 测试运行器

用法：
    python tests/run_tests.py [--quick|--full|--coverage]
    
选项：
    --quick     快速测试（仅关键路径）
    --full      完整测试（所有用例）
    --coverage  带覆盖率报告
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)


def run_command(cmd: list, description: str) -> tuple:
    """运行命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"🔹 {description}")
    print(f"{'='*60}")
    print(f"$ {' '.join(cmd)}")
    
    start_time = datetime.now()
    result = subprocess.run(cmd, capture_output=False)
    duration = (datetime.now() - start_time).total_seconds()
    
    status = "✅ PASS" if result.returncode == 0 else "❌ FAIL"
    print(f"\n{status} ({duration:.2f}s)")
    
    return result.returncode, duration


def check_dependencies():
    """检查测试依赖"""
    print("\n📦 检查测试依赖...")
    
    try:
        import pytest
        print(f"  pytest: {pytest.__version__}")
    except ImportError:
        print("  ❌ pytest 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "-q"])
    
    try:
        import pytest_cov
        print(f"  pytest-cov: 已安装")
    except ImportError:
        print("  ⚠️  pytest-cov 未安装（覆盖率报告不可用）")


def run_quick_tests():
    """运行快速测试（关键路径）"""
    return run_command(
        [sys.executable, "-m", "pytest", 
         "tests/test_database_crud.py::TestUpdatesCRUD",
         "tests/test_analysis.py::TestAnalysisOperations",
         "tests/test_quality_tracking.py::TestQualityIssueTracking::test_insert_quality_issue",
         "tests/test_module_integration.py::TestModuleImports",
         "-v", "--tb=short"],
        "快速测试 - 关键路径"
    )


def run_full_tests():
    """运行完整测试"""
    return run_command(
        [sys.executable, "-m", "pytest", 
         "tests/",
         "-v", "--tb=short",
         "--ignore=tests/run_tests.py"],
        "完整测试 - 所有用例"
    )


def run_coverage_tests():
    """运行带覆盖率的测试"""
    return run_command(
        [sys.executable, "-m", "pytest", 
         "tests/",
         "-v", "--tb=short",
         "--ignore=tests/run_tests.py",
         "--cov=src",
         "--cov-report=term-missing",
         "--cov-report=html:coverage_report"],
        "覆盖率测试"
    )


def run_module_tests():
    """运行模块导入测试"""
    return run_command(
        [sys.executable, "-m", "pytest", 
         "tests/test_module_integration.py",
         "-v", "--tb=short"],
        "模块导入测试"
    )


def run_database_tests():
    """运行数据库测试"""
    return run_command(
        [sys.executable, "-m", "pytest", 
         "tests/test_database_crud.py",
         "tests/test_analysis.py",
         "tests/test_task_management.py",
         "tests/test_quality_tracking.py",
         "-v", "--tb=short"],
        "数据库层测试"
    )


def main():
    parser = argparse.ArgumentParser(description='CI/CD 测试运行器')
    parser.add_argument('--quick', action='store_true', help='快速测试')
    parser.add_argument('--full', action='store_true', help='完整测试')
    parser.add_argument('--coverage', action='store_true', help='覆盖率测试')
    parser.add_argument('--modules', action='store_true', help='模块导入测试')
    parser.add_argument('--database', action='store_true', help='数据库层测试')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🚀 CNetSpy CI/CD 测试运行器")
    print("="*60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    check_dependencies()
    
    results = []
    
    if args.quick:
        results.append(run_quick_tests())
    elif args.coverage:
        results.append(run_coverage_tests())
    elif args.modules:
        results.append(run_module_tests())
    elif args.database:
        results.append(run_database_tests())
    elif args.full:
        results.append(run_full_tests())
    else:
        # 默认运行快速测试
        results.append(run_quick_tests())
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    total_time = sum(r[1] for r in results)
    failed = any(r[0] != 0 for r in results)
    
    if failed:
        print("❌ 测试失败")
        sys.exit(1)
    else:
        print(f"✅ 所有测试通过 (总耗时: {total_time:.2f}s)")
        sys.exit(0)


if __name__ == "__main__":
    main()
