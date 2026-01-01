#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from src.reports.weekly_report import WeeklyReport

def main():
    print("Starting Debug Weekly Report Generation...")
    
    # Use a date range where we know there is data
    start_date = datetime(2025, 12, 13)
    end_date = datetime(2025, 12, 19)
    
    report = WeeklyReport(start_date=start_date, end_date=end_date)
    content = report.generate()
    
    print("\nReport Generation Complete.")

if __name__ == "__main__":
    main()

