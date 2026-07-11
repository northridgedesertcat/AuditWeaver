# LogSentinel

> 一个基于 AI 和 Dify 的日志分析平台。

[![License](https://img.shields.io/badge/license-MIT-blue.svg "License")](#license)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg "Python")]()
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg "Docker")]()

[English](README.md) | 简体中文

***

## 📖 概述

LogSentinel 是一个基于 AI 的日志分析系统，专为分布式集群环境设计。它从多个服务器收集日志数据，并通过规则匹配、异常检测和大型语言模型（LLM）分析智能处理日志。该系统能够识别潜在的安全风险、攻击活动、攻击过程和攻击意图，帮助安全分析师快速定位安全事件。通过自动化日志分析和安全监控，LogSentinel 提高了安全运营效率，增强了分布式系统的整体防护能力。

***

## ✨ 功能特性

- 📥 从分布式服务器收集日志
- 🔍 通过规则匹配检测已知攻击
- 🤖 使用孤立森林识别异常行为
- ⚖️ 自动评估安全风险
- 🧠 使用 LLM（Dify）分析可疑日志
- 📄 生成结构化安全报告
- 🐳 支持 Docker 部署
- 🔐 通过环境变量管理配置

## 🏗 架构

当前架构：
![Architecture](docs/images/current.png "Architecture")

1.0.0 版本架构：
![Architecture](docs/images/version.png "Architecture")

## 🛠 技术栈

| 类别 | 技术 |
| :------------ | :------------ |
| 后端 | Django |
| 前端 | Next.js |
| AI | Dify / Ollama |
| 消息队列 | Kafka |
| 搜索 | Elasticsearch |
| 可视化 | Kibana |
| 容器化 | Docker |

***

## 📂 项目结构

```text
logsentinel/
├── common/     # 公共代码和资源
├── docker/     # Docker 配置
├── resources/  # 依赖资源
├── services/   # 服务代码
├── .env.example
├── start.bat
├── stop.bat
├── README.md
└── .gitignore
```

***

## 🚀 快速开始

### 1. 服务器依赖

在开始之前，请确保已安装以下依赖：
- Python 3.11+
- Docker
- ollama
- dify 平台

### 2. 克隆仓库

```bash
git clone https://github.com/yourname/project.git
cd logsentinel
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置 Dify 平台

将工作流文件添加到 Dify 平台：
resources/dify/logs analysis.yml

### 5. 创建环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件。

### 6. 启动服务

Windows 用户：

```bash
start.bat
```

Linux 用户：

```bash
cd docker
docker compose up -d
```

然后启动 services 目录中的所有应用程序，包括 Agent、Backend、Frontend 和规则匹配服务。

Linux 启动脚本将在未来版本中提供。

***

## ⚙ 配置

| 变量 | 描述 |
| :------------------------ | :---------------- |
| ES_HOST | Elasticsearch 地址 |
| KAFKA_BOOTSTRAP_SERVERS | Kafka 服务器 |
| DIFY_API_KEY | Dify API 密钥 |
| DIFY_BASE_URL | Dify 地址 |

有关所有可用选项，请参阅 `.env.example`。

***

## 📸 截图

仪表盘

![Dashboard](docs/images/dashboard.png "Dashboard")

分析报告

![Report](docs/images/report1.png "Report")
![Report](docs/images/report2.png "Report")

***

## 🤝 贡献

欢迎贡献！

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 打开 Pull Request

***

## 📄 许可证

本项目采用 Apache 2.0 许可证。

***

## 🙏 致谢

- Dify
- Elasticsearch
- Kafka
- Django
- Next.js

***

## ⭐ 支持

如果您发现此项目有用，请考虑在 GitHub 上给它一个 ⭐。