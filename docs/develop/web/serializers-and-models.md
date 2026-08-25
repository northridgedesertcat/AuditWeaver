# 序列化器字段与数据模型

> 源码:
> - [api/serializers.py](../../../services/website/backend/v1/api/serializers.py)
> - [accounts/serializers.py](../../../services/website/backend/v1/accounts/serializers.py)
> - [accounts/models.py](../../../services/website/backend/v1/accounts/models.py)

## 1. 业务序列化器（api.serializers）

### 1.1 AlertSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CharField | 告警 ID |
| `title` | CharField | 标题 |
| `description` | CharField | 描述 |
| `severity` | CharField | 严重等级 |
| `status` | CharField | 状态 |
| `source` | CharField | 来源 |
| `timestamp` | CharField | 时间戳 |
| `count` | IntegerField | 命中次数 |

### 1.2 AlertRuleSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | IntegerField | 规则 ID |
| `name` | CharField | 规则名称 |
| `enabled` | BooleanField | 是否启用 |
| `severity` | CharField | 严重等级 |
| `notifications` | BooleanField | 是否通知 |

### 1.3 IncidentSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CharField | 事件 ID |
| `title` | CharField | 标题 |
| `description` | CharField | 描述 |
| `severity` | CharField | 严重等级 |
| `status` | CharField | 状态 |
| `assignee` | CharField (allow_null) | 负责人 |
| `createdAt` | CharField | 创建时间 |
| `updatedAt` | CharField | 更新时间 |
| `progress` | IntegerField | 进度 |
| `affectedSystems` | ListField<Char> | 受影响系统 |
| `timeline` | ListField<Dict> | 时间线 |

### 1.4 AnomalySerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CharField | 异常 ID |
| `type` | CharField | 异常类型 |
| `title` | CharField | 标题 |
| `description` | CharField | 描述 |
| `severity` | CharField | 严重等级 |
| `score` | IntegerField | 异常分 |
| `timestamp` | CharField | 时间戳 |
| `source` | CharField | 来源 |
| `details` | DictField | 详情 |
| `status` | CharField | 状态 |

### 1.5 ServerSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CharField | 服务器 ID |
| `name` | CharField | 名称 |
| `type` | CharField | 类型 |
| `status` | CharField | 状态 |
| `cpu` | IntegerField | CPU 占用 (%) |
| `memory` | IntegerField | 内存占用 (%) |
| `disk` | IntegerField | 磁盘占用 (%) |
| `network` | CharField | 网络状态 |
| `uptime` | CharField | 运行时长 |
| `location` | CharField | 位置 |

### 1.6 ThreatSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CharField | 威胁 ID |
| `indicator` | CharField | 指标值 |
| `type` | CharField | 类型 |
| `category` | CharField | 分类 |
| `severity` | CharField | 严重等级 |
| `source` | CharField | 来源 |
| `firstSeen` | CharField | 首次发现 |
| `lastSeen` | CharField | 最近发现 |
| `country` | CharField | 国家 |
| `tags` | ListField<Char> | 标签 |

### 1.7 AIModelSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | CharField | 模型 ID |
| `name` | CharField | 名称 |
| `type` | CharField | 类型 |
| `status` | CharField | 状态 |
| `accuracy` | FloatField | 准确率 |
| `latency` | CharField | 延迟 |
| `lastTrained` | CharField | 上次训练时间 |
| `tasksProcessed` | IntegerField | 已处理任务数 |

### 1.8 DashboardStatsSerializer

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `logVolume` | CharField | 今日日志量（带 K/M 后缀） |
| `attackLogs` | IntegerField | 今日攻击日志数 |
| `highSeverityAlerts` | IntegerField | 今日高危告警数 |
| `riskIps` | IntegerField | 风险 IP 数（占位 0） |
| `totalLogs` | IntegerField | 总日志数 |
| `avgResponseTime` | CharField | 平均响应时间（占位 "0ms"） |

## 2. 认证序列化器（accounts.serializers）

源码: [accounts/serializers.py](../../../services/website/backend/v1/accounts/serializers.py)

### 2.1 LoginSerializer

```python
class LoginSerializer(TokenObtainPairSerializer):
    """复用 simplejwt 的 username/password 校验，返回 access + refresh"""
    pass
```

- 继承 simplejwt 的 `TokenObtainPairSerializer`，默认校验 `username` + `password`
- 成功后 `validated_data` 含 `access` 和 `refresh`
- 失败返回 simplejwt 标准 401 错误结构

### 2.2 UserSerializer

```python
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'display_name', 'is_active']
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | AutoField (int) | 用户 ID |
| `username` | CharField | 用户名 |
| `email` | CharField | 邮箱 |
| `role` | CharField | 角色 (`admin`/`analyst`/`viewer`) |
| `display_name` | CharField | 显示名称 |
| `is_active` | BooleanField | 是否启用 |

## 3. User 数据模型

源码: [accounts/models.py](../../../services/website/backend/v1/accounts/models.py)

```python
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN    = 'admin',    '管理员'
        ANALYST  = 'analyst',  '分析师'
        VIEWER   = 'viewer',   '只读'

    role         = models.CharField(max_length=16, choices=Role.choices, default=Role.ADMIN)
    display_name = models.CharField(max_length=64, blank=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.username
```

继承自 `AbstractUser`，自动拥有 `username`、`password`、`email`、`is_active`、`is_staff`、`is_superuser`、`last_login`、`date_joined` 等字段。

| 自定义字段 | 类型 | 默认 | 选项 |
| --- | --- | --- | --- |
| `role` | CharField(16) | `admin` | `admin` / `analyst` / `viewer` |
| `display_name` | CharField(64) | `""` | - |
| `updated_at` | DateTimeField(auto_now) | 自动 | 每次保存自动更新 |

- 在 [settings.py:73](../../../services/website/backend/v1/backend/settings.py) 通过 `AUTH_USER_MODEL = 'accounts.User'` 注册。
- 初始迁移: [accounts/migrations/0001_initial.py](../../../services/website/backend/v1/accounts/migrations/0001_initial.py)
- 初始管理员创建: [accounts/management/commands/init_admin.py](../../../services/website/backend/v1/accounts/management/commands/init_admin.py) (`python manage.py init_admin`)

## 4. 未走 Serializer 的接口

下列接口直接构造 dict 返回，未经过 Serializer：

| 接口 | 视图 | 返回结构来源 |
| --- | --- | --- |
| `GET /health/` | `HealthCheckView` | 手工 dict |
| `GET /dashboard/threat-distribution/` | `ThreatDistributionView` | 手工 dict + ES agg |
| `GET /dashboard/recent-alerts/` | `RecentAlertsView` | 手工 list + ES hits |
| `GET /logs/` | `LogsView` | ES `_source` 原文 |
| `GET /logs/stats/` | `LogStatsView` | 手工 dict + ES agg |
| `GET /logs/trend/` | `LogTrendView` | 手工 list + ES date_histogram |
| `GET /threats/feeds/` | `ThreatFeedsView` | 直接返回 `MOCK_THREAT_FEEDS` |
| `GET /ai/analyses/` | `RecentAnalysesView` | 直接返回 `MOCK_RECENT_ANALYSES` |
| `GET /reports/stats/` | `ReportStatsView` | 手工 dict + ES count |
| `GET /reports/list/` | `ReportListView` | 手工 list + ES hits |
| `GET /reports/<id>/` | `ReportDetailView` | 手工 dict + ES get + 原始日志查询 |
| `POST /agent/*` | `AgentProxyView` | 透传 FastAPI |

## 5. Elasticsearch 字段对照

> 完整 ES 索引定义在 `services/common/env.py` 的 `ES_INDEX_*` 常量。

### 5.1 nginx-log-raw（原始日志索引）

| 字段 | 用途 | 视图 |
| --- | --- | --- |
| `@timestamp` (epoch_millis) | 日志时间 | LogsView / LogStatsView / LogTrendView / DashboardStatsView |
| `ip` | 客户端 IP | LogsView (filter) / LogStatsView (agg) |
| `method` | HTTP 方法 | LogsView (filter) |
| `status` | HTTP 状态码 | LogsView (filter) / LogStatsView (agg) |
| `path` | 请求路径 | LogsView (wildcard) / LogStatsView (agg) |
| `event_id` | 事件 ID | ReportDetailView (回查原文) |
| `event.original` | 原始日志行 | ReportDetailView |

### 5.2 log_analysis_reports（分析报告索引）

| 字段 | 用途 | 视图 |
| --- | --- | --- |
| `analysis_timestamp` (epoch_millis) | 分析时间 | DashboardStatsView / ReportStatsView / ReportListView / ThreatDistributionView |
| `ingestion_time` | 入库时间 | RecentAlertsView |
| `risk_level` | 风险等级 (`Critical`/`High`/`Medium`/`Low`/`Normal`) | DashboardStatsView / ReportStatsView / ReportListView / ThreatDistributionView |
| `risk_score` | 风险分 (0-100) | ReportListView / ReportDetailView |
| `attack_type_ai` | AI 判定的攻击类型 | RecentAlertsView / ReportListView / ReportDetailView |
| `summary` | 分析总结 | ReportDetailView |
| `reasoning` (array) | 原因分析 | ReportDetailView |
| `recommendations` (array) | 处置建议 | ReportDetailView |
| `event_id` | 关联原始日志 | ReportDetailView |
| `ip` / `path` / `user_agent` / `status` / `log_timestamp` | 被攻击的请求信息 | ReportDetailView |
| `original_log` (object) | 原始日志字段集合 (ip/path/user_agent/status/@timestamp) | RecentAlertsView / ReportListView / ReportDetailView |
