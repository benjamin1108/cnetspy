
import os
import sys
from datetime import datetime

# 添加项目路径到系统路径
sys.path.append(os.getcwd())

from src.utils.config import get_config
from src.notification.manager import NotificationManager
from src.notification.base import NotificationChannel

def test_push():
    config = get_config()
    manager = NotificationManager(config.get('notification', {}))
    
    title = "【极致测试】云技术周报 2025-W47"
    
    content = """## 网络安全与成本优化深度洞察

本周云厂商在 re:Invent 期间呈现出爆发式更新。核心聚焦于 AI 基础设施的性能突破以及跨区域的网络安全治理。

### 🌟 核心亮点 (Key Updates)
- **[[AWS] EC2 P5en Instances](https://cnetspy.site/next/updates/test-1)**
  - **痛点:** 大型语言模型训练对网络带宽的极致渴求。
  - **价值:** 提供 400Gbps 的聚合网络带宽，显著提升集群训练效率。
  - **点评:** 算力竞赛的底层支柱，目前行业最强性能基准。

### ⚡️ 快速浏览 (Quick Scan)
- **AWS**
  - ✨ [CloudFront 推出全新安全仪表盘](https://cnetspy.site/next/updates/test-2)
  - [VPC Lattice 支持跨账号资源共享](https://cnetspy.site/next/updates/test-3)
  - [PrivateLink 节点启动速度优化 30%](https://cnetspy.site/next/updates/test-4)
- **Azure**
  - ✨ [ExpressRoute 高可用性架构升级](https://cnetspy.site/next/updates/test-5)
  - [Azure Firewall 支持新的威胁过滤规则](https://cnetspy.site/next/updates/test-6)

### 📚 精选博客 (Featured Blogs)
- **[AWS] [零信任网络设计模式在企业级的落地实践](https://aws.amazon.com/blog/test)**
  - **推荐理由:** 详细拆解了身份识别与网络微隔离的深度结合方案。

---
由云竞争情报分析平台自动汇总。"""

    online_url = "https://cnetspy.site/next/reports?type=weekly&year=2025&week=47"
    
    print("正在发送 ActionCard 到钉钉...")
    result = manager.send_dingtalk(
        title=title,
        content=content,
        single_url=online_url,
        single_title="查看在线完整版",
        robot_names=["TEST-BOT"]
    )
    
    if result.success:
        print("发送成功！请检查您的钉钉。")
    else:
        print(f"发送失败: {result.message}")

if __name__ == "__main__":
    test_push()
