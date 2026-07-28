# LogSentinel 时间系统重构规范

## 一、重构背景

LogSentinel 是一个 AI 日志分析平台，系统流程为：

```
日志生成 → Kafka → Rule Matching → AI(Dify Workflow) → Elasticsearch → Django API → Next.js Dashboard
```

由于开发过程中不断迭代，时间处理出现混乱，存在以下问题：

- `datetime.now()` 和 `datetime.utcnow()` 混杂使用
- ISO 字符串、epoch 秒、epoch 毫秒多种格式并存
- 手动 UTC+8 转换散落在各处
- Django 时区配置为 Asia/Shanghai，与国际化目标冲突
- 前端时间格式化逻辑散落各处

## 二、最终规范

整个项目统一采用：**UTC + epoch_millis** 作为唯一的时间存储格式。

## 三、时间字段职责

### 3.1 log_timestamp

- **含义**: 日志真正发生时间（Event Time）
- **用途**:
  - Dashboard 统计
  - 今日攻击
  - 趋势图
  - 风险统计
  - 时间过滤
- **不得用于**: AI 耗时统计

### 3.2 ingestion_time

- **含义**: 日志进入系统时间
- **用途**:
  - Kafka 消费监控
  - 系统监控
  - 数据进入平台时间记录

### 3.3 analysis_timestamp

- **含义**: AI 分析完成时间
- **用途**:
  - AI 报告排序
  - AI 耗时统计
  - 系统性能统计
- **不得用于**: 业务统计（否则 AI 积压会导致昨天日志今天统计）

## 四、Python 统一规则

### 禁止使用
- `datetime.now()`
- `datetime.utcnow()`
- 手动 UTC+8 计算
- `timezone(timedelta(hours=8))`
- 写死中国时间

### 统一使用
- `datetime.now(timezone.utc)` - 获取当前 UTC 时间
- `int(datetime.now(timezone.utc).timestamp() * 1000)` - 获取 epoch_millis

## 五、新增文件

### 5.1 Python 时间工具模块

**路径**: `services/common/time_utils.py`

提供统一的时间处理工具函数：

| 函数名 | 功能 | 返回类型 |
|--------|------|----------|
| `now_utc()` | 获取当前 UTC 时间 | `datetime` |
| `to_epoch_millis(dt)` | 转换任意时间格式为 epoch_millis | `int` |
| `epoch_millis_now()` | 获取当前 epoch_millis | `int` |
| `format_for_filename()` | 生成文件名时间格式 | `str` |
| `format_for_directory()` | 生成目录时间格式 | `tuple` |

### 5.2 TypeScript 时间工具模块

**路径**: `services/website/frontend/v1/lib/time.ts`

提供前端统一的时间格式化函数：

| 函数名 | 功能 | 返回类型 |
|--------|------|----------|
| `formatTimestamp(epochMs)` | 格式化完整时间戳 | `string` |
| `formatRelative(epochMs)` | 格式化相对时间 | `string` |
| `formatDate(epochMs)` | 格式化日期 | `string` |
| `formatTimeOnly(epochMs)` | 格式化时间部分 | `string` |

## 六、修改文件列表

### 6.1 Python 后端

| 文件路径 | 修改内容 | 影响范围 |
|----------|----------|----------|
| `services/website/backend/v1/backend/settings.py` | TIME_ZONE 改为 UTC | Django 全局 |
| `services/rulesMatching/dataTransfer/data_saver.py` | 使用 TimeUtils 替换直接时间调用 | 规则匹配数据保存 |
| `services/rulesMatching/utils.py` | timestamp 改为 epoch_millis | 检测结果 |
| `services/rulesMatching/main.py` | 启动时间改为 UTC 格式 | 日志输出 |
| `services/agent/config/elastic_mapping_config.py` | 使用 TimeUtils，移除冗余函数 | ES 文档构建 |
| `docker/config/elasticsearch/creatMapping.py` | 时间字段格式改为 epoch_millis | ES Mapping |
| `services/website/backend/v1/api/views.py` | 使用 TimeUtils，移除 format_time 方法 | API 响应 |
| `services/website/backend/v1/api/mock_data.py` | 时间字段改为 epoch_millis | 测试数据 |

### 6.2 TypeScript 前端

| 文件路径 | 修改内容 | 影响范围 |
|----------|----------|----------|
| `services/website/frontend/v1/components/dashboard/log-volume-chart.tsx` | 使用 formatTimeOnly，移除本地时间生成 | 日志趋势图 |
| `services/website/frontend/v1/app/alerts/page.tsx` | 使用 formatRelative，时间字段改为 epoch_millis | 告警列表 |
| `services/website/frontend/v1/app/reports/page.tsx` | 使用 formatRelative，时间字段改为 epoch_millis | 报告列表 |
| `services/website/frontend/v1/app/agent/page.tsx` | 时间字段改为 epoch_millis | AI 助手消息 |

## 七、各模块修改详情

### 7.1 Django 配置

```python
# 修改前
TIME_ZONE = 'Asia/Shanghai'

# 修改后
TIME_ZONE = 'UTC'
```

### 7.2 rulesMatching 模块

**data_saver.py**:
- `datetime.utcnow().strftime(...)` → `format_for_directory()`
- `datetime.now().strftime(...)` → `format_for_filename()`
- `datetime.now().isoformat()` → `epoch_millis_now()`
- `datetime.utcnow().isoformat()` → `epoch_millis_now()`

**utils.py**:
- `'timestamp': datetime.utcnow().isoformat()` → `'timestamp': epoch_millis_now()`

**main.py**:
- `datetime.now().strftime(...)` → `now_utc().strftime('%Y-%m-%d %H:%M:%S UTC')`

### 7.3 agent 模块

**elastic_mapping_config.py**:
- 移除本地 `normalize_datetime()` 和 `to_epoch_millis()` 函数
- 使用 TimeUtils 的 `epoch_millis_now()` 和 `to_epoch_millis()`
- `analysis_timestamp` 使用 `epoch_millis_now()`

### 7.4 ES Mapping

**creatMapping.py**:
- `@timestamp` 格式增加 `epoch_millis||` 前缀
- `ingestion_time` 格式改为 `epoch_millis`

### 7.5 Django API

**views.py**:
- 导入 TimeUtils 替换 `datetime` 直接调用
- 所有 ES 查询时间范围使用 epoch_millis
- 移除 `format_time()` 方法，直接返回 epoch_millis
- 趋势图时间字段返回 epoch_millis

### 7.6 前端组件

**log-volume-chart.tsx**:
- 移除 `generateTimeLabels()` 本地时间生成函数
- 使用 `formatTimeOnly()` 格式化 X 轴和 Tooltip 时间

**alerts/page.tsx**:
- 导入 `formatRelative`
- mock 数据 `timestamp` 改为 `Date.now() - offset` 格式
- 显示时调用 `formatRelative(timestamp)`

**reports/page.tsx**:
- 导入 `formatRelative`
- `Report` 接口 `generatedAt` 类型改为 `number`
- mock 数据时间改为 epoch_millis
- 显示时调用 `formatRelative(generatedAt)`

**agent/page.tsx**:
- 导入 `formatRelative`
- `Message` 接口 `timestamp` 类型改为 `number`
- 消息时间使用 `Date.now()`

### 7.7 测试数据

**mock_data.py**:
- 添加 `import time` 和 `_now = int(time.time() * 1000)`
- 所有时间字段改为 `_now - offset` 格式
- 移除 UTC+8 相关字符串

## 八、国际化支持

### 8.1 后端
- 全部使用 UTC
- 数据库存储 UTC
- ES 存储 UTC (epoch_millis)
- API 返回 UTC (epoch_millis)

### 8.2 前端
- 接收 epoch_millis
- 使用浏览器本地时区自动转换
- 支持中国、日本、美国、欧洲等任何时区

### 8.3 时区转换流程

```
后端 (UTC epoch_millis)
        ↓
    API 传输 (int)
        ↓
前端 (new Date(epochMs)) → 自动转为本地时区
        ↓
    formatRelative() / formatTimestamp()
        ↓
   用户看到本地时间
```

## 九、影响评估

### 9.1 业务影响
- **无影响**：业务逻辑不变，仅修改时间存储和传输格式

### 9.2 数据库影响
- **无影响**：本项目主要使用 Elasticsearch，MySQL 仅存储配置数据，无时间敏感字段

### 9.3 ES Mapping 影响
- **需要重新创建索引**：修改了 `ingestion_time` 和 `@timestamp` 的 format，新数据将使用 epoch_millis，旧数据仍可查询（兼容模式）

### 9.4 API 影响
- **破坏性变更**：API 返回的时间字段从字符串变为整数（epoch_millis），前端必须更新

### 9.5 前端影响
- **需要同步更新**：所有页面必须使用 `lib/time.ts` 的工具函数，不能再使用 `new Date()` 或 `toLocaleString()`

## 十、迁移策略

### 10.1 步骤

1. **创建工具模块** → `time_utils.py` 和 `time.ts`
2. **修改后端模块** → 按依赖顺序修改
3. **修改 ES Mapping** → 更新 creatMapping.py
4. **修改 Django API** → 返回 epoch_millis
5. **修改前端组件** → 使用工具函数
6. **重建 ES 索引** → 应用新的 mapping
7. **测试验证** → 端到端测试

### 10.2 兼容性考虑

- ES 的 `@timestamp` 使用 `epoch_millis||strict_date_optional_time||yyyy-MM-dd HH:mm:ss` 格式，兼容旧数据
- 新数据全部使用 epoch_millis

## 十一、规范检查清单

- [x] 禁止 `datetime.now()`
- [x] 禁止 `datetime.utcnow()`
- [x] 禁止手动 UTC+8
- [x] 禁止 `timezone(timedelta(hours=8))`
- [x] 统一使用 `datetime.now(timezone.utc)`
- [x] ES 时间字段使用 epoch_millis
- [x] API 返回 epoch_millis
- [x] 前端使用统一工具函数
- [x] Django TIME_ZONE = UTC
- [x] 时间字段职责清晰

## 十二、代码审查要点

1. **Python 代码审查**:
   - 是否存在 `datetime.now()` 或 `datetime.utcnow()`
   - 是否使用了 `timezone(timedelta(hours=8))`
   - 时间字段是否使用 epoch_millis 存储
   - 是否导入并使用了 TimeUtils

2. **TypeScript 代码审查**:
   - 是否存在散落的 `new Date()` 或 `toLocaleString()`
   - 是否使用了 `lib/time.ts` 的工具函数
   - 时间字段类型是否为 `number` (epoch_millis)

3. **ES Mapping 审查**:
   - 时间字段是否设置了 `format: epoch_millis`
   - 是否兼容旧数据格式

4. **API 审查**:
   - 响应中时间字段是否为整数
   - 是否包含任何时间格式化逻辑

## 十三、异常处理

### 13.1 时间转换异常

`to_epoch_millis()` 函数内置了完善的类型检测和异常处理：

- `datetime` 对象：直接转换
- `int/float`：视为 epoch 秒或毫秒
- `str`：尝试 ISO 格式解析
- `None`：返回 0

### 13.2 前端时间处理

前端工具函数对无效输入返回安全默认值（如 `"--"`），避免页面崩溃。

## 十四、性能考虑

- epoch_millis 是整数，传输和存储效率高于字符串
- 前端 `new Date(epochMs)` 是 O(1) 操作，性能优异
- 避免了时区转换的 CPU 开销

## 十五、监控建议

建议在系统监控中增加以下指标：

1. **ingestion_time 延迟**: 日志从生成到进入系统的时间
2. **analysis_time 延迟**: 从进入系统到 AI 分析完成的时间
3. **时间一致性检查**: 确保 `log_timestamp <= ingestion_time <= analysis_timestamp`

---

**文档版本**: v1.0  
**生成时间**: 2026-03-18  
**适用项目**: LogSentinel AI 日志分析平台