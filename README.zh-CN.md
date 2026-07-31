# AuditWeaver

> 一个基于 AI 和 Dify 的日志分析平台。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg "License")](#license)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg "Python")]()
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg "Docker")]()

[English](README.md) | 简体中文

***

## 📖 概述

AuditWeaver 是一个基于 AI 的日志分析系统，专为分布式集群环境设计。它从多个服务器收集日志数据，并通过规则匹配、异常检测和大型语言模型（LLM）分析智能处理日志。该系统能够识别潜在的安全风险、攻击活动、攻击过程和攻击意图，帮助安全分析师快速定位安全事件。通过自动化日志分析和安全监控，AuditWeaver 提高了安全运营效率，增强了分布式系统的整体防护能力。

***

## ✨ 功能特性

- 📥 从分布式服务器收集日志
- 🔍 通过规则匹配检测已知攻击（SQL 注入、XSS、命令注入、路径遍历等）
- 🤖 使用孤立森林（Isolation Forest）识别异常行为
- ⚖️ 自动评估安全风险
- 🧠 使用 LLM（Dify Workflow）分析可疑日志
- 📄 生成结构化安全报告
- 🔄 基于 Kafka + Kafka Connect 的实时数据管道
- 🐳 支持 Docker 部署，一键启动
- 🔐 通过环境变量管理配置

***

## 🏗 架构

当前架构：
![Architecture](docs/develop/system-design/architecture/current.drawio.png "Architecture")

***

## 🛠 技术栈

| 类别 | 技术 |
| :------------ | :------------ |
| 后端 | Django + Django REST Framework |
| 前端 | Next.js + TypeScript |
| AI 分析 | Dify Workflow / Ollama |
| 规则引擎 | Python Regex + YAML 规则配置 |
| 异常检测 | Isolation Forest (scikit-learn) |
| 消息队列 | Apache Kafka |
| 数据集成 | Kafka Connect (Elasticsearch Sink) |
| 日志管道 | Logstash |
| 搜索与存储 | Elasticsearch |
| 可视化 | Kibana |
| 容器化 | Docker Compose |

***

## 📂 项目结构

```text
AuditWeaver/
├── common/              # 公共代码和资源
│   ├── env.py           # 环境变量配置
│   └── time_utils.py    # 时区工具（多时区支持）
├── docker/              # Docker 配置
│   ├── config/
│   │   ├── elasticsearch/   # ES 映射与初始化
│   │   ├── kafka/           # Kafka Topic 配置
│   │   ├── kafka-connect/   # Kafka Connect 连接器
│   │   └── logstash/        # Logstash 管道
│   └── docker-compose.yml
├── docs/                # 项目文档
├── resources/           # Dify 工作流资源
├── scripts/             # 启动/管理脚本
│   ├── config.py        # 服务配置
│   ├── docker_manager.py # Docker 生命周期管理器
│   └── utils.py         # 通用工具函数
├── services/            # 微服务
│   ├── agent/           # AI 分析模块（Dify 集成）
│   ├── ruleEngine/      # 规则匹配引擎
│   ├── isolationForest/ # 异常检测模型
│   ├── riskAssessment/  # 风险评估模块
│   └── website/         # Web 平台（Django + Next.js）
├── .env.example         # 环境变量模板
├── start.py             # 一键启动脚本（Python）
├── start.bat            # 一键启动脚本（Windows）
├── stop.bat             # 停止脚本（Windows）
├── requirements.txt
├── README.md
└── .gitignore
```

***

## 🚀 快速开始

### 1. 环境依赖

在开始之前，请确保已安装以下依赖：

- Python 3.11+
- Node.js 18+（Next.js 前端开发需要）
- Docker & Docker Compose
- 运行中的 Dify 平台（或本地 LLM Ollama）

### 2. 克隆仓库

```bash
git clone https://github.com/yourname/AuditWeaver.git
cd AuditWeaver
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 安装前端依赖（可选，开发时需要）

```bash
cd services/website/frontend/v1
npm install
cd ../../..
```

### 5. 配置 Dify 平台

将工作流文件上传至 Dify 平台：

```
resources/dify/logs analysis.yml
```

### 6. 创建环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下内容：
- `DIFY_API_KEY`：你的 Dify API 密钥
- `DIFY_BASE_URL`：Dify API 地址
- 根据需要调整其他服务端口

### 7. 启动所有服务

**Windows（推荐）：**

```bash
start.bat
```

**Windows（Python 方式）：**

```bash
python start.py
```

**Linux：**

```bash
# 先启动 Docker 服务
cd docker
docker compose up -d

# 再启动 Python 服务
python start.py
```

启动脚本会自动完成以下步骤：
1. 启动所有 Docker Compose 服务（Kafka、Elasticsearch、Kibana、Logstash、Kafka Connect）
2. 等待 Elasticsearch 和 Kafka 就绪
3. 初始化 Kafka Topics 和 Elasticsearch 索引
4. 初始化 Kafka Connect 连接器
5. 启动规则引擎、Agent 模块、Django 后端和 Next.js 前端

启动完成后，访问：
- 仪表板前端: http://localhost:3000
- Django 后端 API: http://localhost:8000
- Kibana: http://localhost:5601

***

## ⚙ 配置说明

### 核心环境变量

| 变量 | 描述 | 默认值 |
| :------------------------ | :----------------------------------- | :---------- |
| DJANGO_SECRET_KEY         | Django 密钥 | -           |
| DJANGO_DEBUG              | Django 调试模式 | True        |
| DJANGO_PORT               | Django 后端端口 | 8000        |
| ES_HOST                   | Elasticsearch 主机 | localhost   |
| ES_PORT                   | Elasticsearch 端口 | 19200       |
| KAFKA_BROKERS             | Kafka 代理地址 | localhost:29092 |
| KAFKA_CONNECT_HOST        | Kafka Connect 主机 | localhost   |
| KAFKA_CONNECT_PORT        | Kafka Connect REST API 端口 | 8083        |
| KAFKA_TOPIC_RAW           | 原始日志 Kafka Topic | log.raw     |
| KAFKA_TOPIC_STRUCTURED    | 结构化日志 Kafka Topic | log.structured |
| KAFKA_TOPIC_ANALYSIS      | 分析结果 Kafka Topic | log.analysis |
| KAFKA_TOPIC_RISK          | 风险评估 Kafka Topic | log.risk    |
| DIFY_BASE_URL             | Dify API 地址 | http://localhost/v1 |
| DIFY_API_KEY              | Dify API 密钥 | -           |
| NEXT_PUBLIC_API_BASE      | 前端 API 基础地址 | http://localhost:8000 |

> 更多完整选项请参阅 `.env.example`。

### Kafka Topics 说明

| Topic | 描述 |
| :-------------------- | :--------------------------------------------- |
| log.raw               | 原始日志数据输入                             |
| log.structured        | 结构化/解析后的日志（通过 Logstash）           |
| log.audit             | 待规则引擎处理的日志                        |
| log.analysis          | 规则引擎分析结果                           |
| agent.event.save      | Agent AI 分析结果（ES Sink 目标）     |
| rule.event.save       | 规则引擎事件（ES Sink 目标）            |

> Topics 通过 `docker/config/kafka/topics/topics.yaml` 和 `create-init-topics.py` 自动初始化。

### Elasticsearch 索引说明

| 索引 | 描述 |
| :----------------------- | :--------------------------------------- |
| nginx-log-raw            | 原始 Nginx 日志                           |
| matched_logs             | 规则匹配的日志                    |
| log_analysis_reports     | AI 生成的分析报告            |

***

## 📸 系统截图

仪表盘

![Dashboard](docs/images/dashboard.png "Dashboard")

分析报告

![Report](docs/images/report1.png "Report")
![Report](docs/images/report2.png "Report")

***

## 🤝 贡献

欢迎贡献代码！

1. Fork 本项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

***

## 📄 许可证

本项目基于 Apache 2.0 许可证。

***

## 🙏 致谢

- [Dify](https://github.com/langgenius/dify) - LLM 应用平台
- [Elasticsearch](https://www.elastic.co/) - 搜索与分析
- [Kafka](https://kafka.apache.org/) - 分布式消息队列
- [Logstash](https://www.elastic.co/logstash) - 数据处理管道
- [Django](https://www.djangoproject.com/) - Python Web 框架
- [Next.js](https://nextjs.org/) - React 框架
- [scikit-learn](https://scikit-learn.org/) - 孤立森林异常检测

***

## ⭐ 支持

如果您觉得本项目有用，请考虑在 GitHub 上给它一个 ⭐。
