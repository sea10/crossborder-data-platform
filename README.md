# 跨境电商智能数据中台

> 以跨境电商为背景的数据基础设施实战项目：
> **RPA 采集 × 经营分析 × AI 选品 Agent** 全链路，无人值守自动运行。

## 项目简介

以跨境电商为业务背景，实现「数据采集自动化 -> 数据仓库建模 -> 经营分析可视化 -> AI 智能报告」的完整闭环：

1. **① RPA 采集层**：Playwright 浏览器自动化定时采集亚马逊 Best Sellers 榜单与竞品数据，模拟人工导出店铺订单报表并自动入库；失败自动重试，全程无人值守
2. **② 数据层**：MySQL 维度建模（商品 / 快照 / 订单），pandas 清洗与 ETL，构建 20+ 项经营指标体系
3. **③ 分析层**：Streamlit 经营大屏，自动生成日报推送飞书群
4. **④ AI 层**：基于 LLM Function Calling 手写 Agent 循环，自动解读经营异动、结合竞品数据输出选品报告

## 项目亮点

- **全链路闭环**：采集 → 清洗 → 入库 → 指标体系 → 可视化 → 日报推送 → AI 解读，无人值守自动运行
- **工程化细节**：幂等设计（唯一约束 + upsert）、异常隔离（调度器各步骤互不影响）、18 项测试覆盖核心逻辑
- **数据质量治理**：修复复购率失真（SKU 池规模）、价格-销量耦合、跨类目对比错位等真实问题（见 docs/指标字典.md）
- **手写 Agent 循环**：不依赖框架，工具调用过程全程可溯；换模型只改 settings.yaml 一处配置

## 架构

```
┌─────────── ① RPA 采集层 (collectors/) ─────────────┐
│  · amazon_bestseller.py  Playwright 榜单/竞品采集   │
│  · order_importer.py     订单 CSV 清洗入库          │
│  · scheduler.py          APScheduler 定时调度       │
└──────────────────────┬─────────────────────────────┘
                       ▼
┌─────────── ② 数据层 (database/) ───────────────────┐
│  MySQL 维度建模: dim_product / fact_snapshot /      │
│                 fact_order                         │
│  pandas 清洗 ETL -> 指标体系                        │
└──────────────────────┬─────────────────────────────┘
                       ▼
┌─────────── ③ 分析层 (analytics/) ──────────────────┐
│  Streamlit 经营大屏 / 自动日报 -> 飞书推送          │
└──────────────────────┬─────────────────────────────┘
                       ▼
┌─────────── ④ AI 层 (agent/) ───────────────────────┐
│  LLM Agent: 经营解读 + 选品报告                     │
└────────────────────────────────────────────────────┘
```

## 目录结构

```
crossborder-data-platform/
├── collectors/      # ① RPA 采集层
├── database/        # ② 数据层（模型 + 连接 + 初始化）
├── analytics/       # ③ 分析层（大屏 + 报表推送）
├── agent/           # ④ AI 层（LLM Agent）
├── scripts/         # 工具脚本（模拟数据生成等）
├── config/          # 全局配置 settings.yaml
├── docs/            # 指标字典等文档
└── data/            # raw 原始数据 / processed 中间数据 / reports 报告输出
```

## 技术栈

Python 3.12 · Playwright · MySQL 8 · SQLAlchemy 2.x · pandas · APScheduler · Streamlit · DeepSeek API

## 快速开始

```bash
# 0. 一键启动：定时调度 + 经营大屏 + 自动打开浏览器（双击「启动.bat」也可以）
python start_all.py

# 1. 安装依赖（建议在项目虚拟环境中）
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium

# 2. 编辑 config/settings.yaml，填入你的 MySQL 密码

# 3. 初始化数据库（自动建库建表）
.venv/Scripts/python -m database.init_db

# 4. 跑一次采集（约 2-3 分钟，落库并留存原始 HTML）
.venv/Scripts/python -m collectors.amazon_bestseller

# 5. 生成模拟订单并导入（模拟 RPA 后台导出 -> 入库）
.venv/Scripts/python -m scripts.make_sample_orders
.venv/Scripts/python -m collectors.order_importer data/raw/sample_orders.csv

# 6. 定时调度（或加 --once 立即执行一次）
.venv/Scripts/python -m collectors.scheduler

# 7. 输出经营分析报告（18 项指标体系）
.venv/Scripts/python -m database.metrics

# 8. 经营大屏（启动后浏览器打开 http://localhost:8501）
.venv/Scripts/python -m streamlit run analytics/dashboard.py

# 9. 日报推送飞书（--dry 只打印不推送；调度器已自动集成此步骤）
.venv/Scripts/python -m analytics.report_pusher

# 10. AI 经营解读 / 选品报告（需先设置 DEEPSEEK_API_KEY 环境变量）
.venv/Scripts/python -m agent.insight_agent
.venv/Scripts/python -m agent.selection_agent

# 11. 运行测试（18 项，覆盖解析/清洗/指标口径/Agent 工具）
.venv/Scripts/python -m pytest tests/ -v
```

> 以上命令均在项目根目录执行。调试采集时用 `--headful` 显示浏览器窗口。

## 环境迁移（换电脑部署）

代码随仓库克隆即可；敏感配置与数据不在仓库中，需在新环境按以下步骤重建。

**前提**：新电脑已安装 Python 3.12+ 与 MySQL 8。

**① 克隆与安装**

```bash
git clone https://github.com/sea10/crossborder-data-platform.git
cd crossborder-data-platform
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium
```

**② 重建本地配置**（敏感信息不进入仓库，故需手动重建）

```bash
copy config\settings.example.yaml config\settings.yaml
```

编辑 `settings.yaml`：填入新电脑 MySQL 的密码与飞书机器人 webhook 地址；LLM 的 API key 走环境变量（下一步），不写入文件。

**③ 配置 API key 环境变量**（DeepSeek）

```cmd
setx DEEPSEEK_API_KEY "sk-你的key"
```

配置后需重开终端窗口生效。

**④ 初始化数据库与数据**

```bash
.venv/Scripts/python -m database.init_db
.venv/Scripts/python -m scripts.make_sample_orders
.venv/Scripts/python -m collectors.order_importer data/raw/sample_orders.csv
```

订单为模拟数据、榜单数据重新采集即可，全部可再生，无需迁移旧库。

**⑤ 验证**

```bash
.venv/Scripts/python -m pytest tests/ -v
```

全部通过后双击 `启动.bat` 即可使用。若新电脑需要推送代码，首次 push 时登录 GitHub 即可；使用代理上网的环境需单独为 git 配置代理。

## 常见问题

- **采集被亚马逊拦截（Robot Check）**：属正常反爬现象，代码会自动退避重试。若持续被拦：调大 `delay_seconds`、减少 `max_pages`、换网络环境；备选方案是切换到反爬更宽松的速卖通页面
- **解析不出商品**：亚马逊改版导致选择器失效，原始 HTML 已存档在 `data/raw/`，用 `--headful` 模式检查新 DOM 结构并更新选择器常量即可

## 后续规划

- 广告数据接入（新增 fact_ad 表，支持广告 ROI 指标）
- 评论采集与情感分析
- 榜单快照数据归档与保留策略
- 采集批次健康监控（数据断流自动告警）

## 日志与排错

运行日志按模块记录在 `data/logs/` 目录（控制台同步输出），单文件 2MB 自动轮转、保留 5 份历史：

| 日志文件 | 记录内容 |
|---------|---------|
| collector.log | 采集流程：每页解析数量、反爬拦截与退避重试、落库统计 |
| scheduler.log | 定时任务：任务开始/完成、失败堆栈 |
| importer.log | 订单导入：清洗统计、入库行数 |
| report.log | 日报生成与飞书推送结果 |
| agent.log | AI Agent 的工具调用链与执行过程 |
| startup.log | 一键启动/停止事件 |

**排错方法**：
1. 按时间定位：打开对应模块日志，搜索 `[ERROR]` 行
2. 异常均记录完整堆栈，最后一行是错误根因
3. 采集问题额外排查 `data/raw/` 存档的原始 HTML

## 合规声明

本项目仅采集亚马逊公开页面数据，控制请求频率并遵守 robots.txt，数据仅用于学习与个人项目演示，不用于任何商业用途。
