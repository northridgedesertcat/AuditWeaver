# 日志冷热存储

CK 保存完整原文及规则事件，ES 保存事件时间在最近 168 小时内的检索副本。默认仍使用旧 ES 查询；不会自动停用旧 connector，不会修改或删除现有数据。开发方案和实施记录保存在 Git 忽略的 `document/develop/database/`。

## 初始化

在本 worktree 根目录执行，先配置 `.env.example` 中的连接项和三个不同 CK 密码。查询账号只授予 SELECT，写入账号只授予 SELECT/INSERT；管理员用于初始化和备份。

```powershell
python -m pip install -r requirements.txt
docker compose --env-file .env -f docker/docker-compose.yml --profile log-storage up -d clickhouse
python services/website/backend/v1/manage.py migrate
python -m services.log_storage init
python docker/config/kafka/topics/create-init-topics.py --dry-run --apply-configs
# 容量检查通过后才应用已有 topic 的保留配置：
python docker/config/kafka/topics/create-init-topics.py --apply-configs
```

`init` 幂等建库、建表、授权和安装 ES 模板，不轮换已有账号密码。初始化不会清空表，也不会重置 Kafka group。输入 topic 的分区数、来源代次必须保持稳定；扩分区、重建 topic 或重置 offset 应按专门迁移处理。存储 group 默认从 earliest 开始，记录实际起点；Kafka 已清理的数据依靠旧 ES 回填。存量 Kafka 消息允许没有 key；一旦发现同业务键跨分区则阻止归档，应离线修复，不能直接跳 offset。新的 Logstash 输出固定使用 event_id 作为 key。

## 影子写入与启停

设置 `STORAGE_ENABLED=true`，保持 `LOG_QUERY_MODE=es_legacy`、`ES_CLEANUP_ENABLED=false`。`start.py` 会在 Django 迁移后隐藏启动存储管理进程；也可单独运行：

```powershell
python -m services.log_storage supervise
python -m services.log_storage status
python -m services.log_storage stop
```

管理进程启动四个独立 worker，CK/ES、原始日志/事件分别使用不同 group。日志位于 `logs/log-storage/`。失败后延迟重启，未提交批次重放。也可逐个调试：

```powershell
python -m services.log_storage worker --sink ck --kind raw
python -m services.log_storage worker --sink ck --kind events
python -m services.log_storage worker --sink es --kind raw
python -m services.log_storage worker --sink es --kind events
```

消息解析失败时保留原始字节到 `log.storage.quarantine`、登记 gap，停止消费且不提交失败位置。修复生产者或恢复原消息后重放相同位置，成功写入会将该 gap 标为 resolved。对于不可修复消息，应保留证据并补齐相同业务键；不可直接跳 offset 清除缺口。CK/ES 批次失败和元数据失败同样不提交 Kafka。

## 回填与切换

1. 先确认四个 group 都已追平。记录旧两个 connector 的最终 **next offset** 向量后停止它们，设置 `STORAGE_LEGACY_CONNECTORS_ENABLED=false` 防止启动脚本重建；死信 connector 保留。不要复用本工具去自动猜测或清空 connector offset。
2. 对旧 `nginx-log-raw`、`matched_logs` 使用 ES add index block API 设写阻塞并 refresh，完成 flush。这个操作应在连接真实部署并审阅进度之后单独执行。
3. 将实际记录的向量保存为 JSON。例如原始日志 `{"log.structured:0":123,"log.structured:1":456}`；事件使用 `rule.event.save`。向量中的数值是 next offset，不是最后一条 offset。
4. 分日/月回填旧索引。中断后重跑相同范围，版本 1 不会覆盖实时版本；不可跨 PIT 复用 `_shard_doc`。

```powershell
python -m services.log_storage backfill --index nginx-log-raw --kind raw --start 2026-01-01T00:00:00Z --end 2026-12-01T00:00:00Z --copy-hot --source-bounds document/raw-handoff.json
python -m services.log_storage backfill --index matched_logs --kind events --start 2026-01-01T00:00:00Z --end 2026-12-01T00:00:00Z --copy-hot --source-bounds document/events-handoff.json
python -m services.log_storage certify-hot --kind raw --handoff document/raw-handoff.json
python -m services.log_storage certify-hot --kind events --handoff document/events-handoff.json
```

先切 `LOG_QUERY_MODE=transition`：热数据查新 alias，冷数据查旧固定索引。热窗口未认证或 consumer 落后会拒绝返回完整结果。回填完成后认证历史：

```powershell
python -m services.log_storage certify-coverage --kind raw --handoff document/raw-handoff.json
python -m services.log_storage certify-coverage --kind events --handoff document/events-handoff.json
```

认证对整个封存旧索引逐键校验，并核对 Kafka 连续接续，不仅比较记录数。缺失或非法事件时间、同键不同正文、缺来源证明的更新都会阻止认证。确认后切 `LOG_QUERY_MODE=hybrid` 并重启调用方。旧固定索引暂保留只读，不属于日索引清理范围。

## 查询

- `/api/v1/logs/` 支持 `start_time`、`end_time`（带时区 ISO/毫秒）、`ip/method/status/path/q`、`size/cursor`，默认最近 24 小时。
- `path` 为字面子串；`q` 匹配精确 IP、精确 Event ID 或路径子串。不会把 `%/_/*/?` 当作用户提供的通配语法。
- 明细冷热区间不相交，游标固定时间和分界；`total=null` 表示列表没有执行全量计数。精确统计在 hybrid 下仅查询 CK 全量且使用 FINAL，避免重复累计和局部 Top N 错误。
- 统计默认所选时间范围；仪表盘 total 为完整历史。历史未认证、缺口未修复或 checkpoint 超过 30 秒未更新时，返回 503 和 `coverage.complete=false`。
- 报告主体仍在 MySQL，原文状态区分 found / original_missing / not_found / unavailable。CK 暂无自动删除，不会假装能判断一个未设置的过期策略。
- RAG 案例重建流式遍历完整窗口；hybrid/transition 首次增量同步扫描案例窗口，此后消费与归档 checkpoint 同事务保存的 MySQL outbox，读取 CK 最新事件。语料仍在 ES，过期案例单独删除。

## 清理

```powershell
python -m services.log_storage cleanup --index auditweaver-raw-hot-2026.11.01
```

默认纯计划，不封存、不改数据库、不删除。执行需要设置 `ES_CLEANUP_ENABLED=true`、`ES_CLEANUP_DRY_RUN=false`，并传入备份证据 JSON：`backup_id`、`covered_until`、`restore_tested_at`（均使用带时区时间）。证据来自实际备份与恢复演练，工具不会代替备份系统产生证明。

```powershell
python -m services.log_storage cleanup --index auditweaver-raw-hot-2026.11.01 --execute --backup-evidence document/backup-evidence.json
```

执行会获取 MySQL 独占锁，等待索引写阻塞生效、refresh、逐键校验 CK 正文和版本、核对 checkpoint，删除前重新检查索引 UUID、写阻塞和覆盖状态。只允许精确日索引名；任何校验失败保留索引并记录 BLOCKED。开启清理时管理进程每小时运行一次，备份证据文件用 `ES_CLEANUP_BACKUP_EVIDENCE` 指定。建议先保持 dry-run，观察至少 72 小时后再启用真实删除。

## 测试

```powershell
python -m unittest discover -s services/log_storage/tests -v
$env:PYTHONPATH=(Get-Location).Path
python services/website/backend/v1/manage.py test log_storage_meta --settings=services.log_storage.test_settings
docker compose -p auditweaver-storage-test -f docker/compose.log-storage-test.yml up -d
# 先对 localhost:23306 的独立 storage_test 数据库执行 Django migrations。
$env:STORAGE_INTEGRATION_TEST="1"
python -m services.log_storage.tests.integration
docker compose -p auditweaver-storage-test -f docker/compose.log-storage-test.yml down
```

集成测试强制独立端口，数据库名称含随机标识，数据使用 tmpfs；测试使用的备份标识仅为测试夹具，不能用于生产。测试集会停止自身 worker，不触碰原部署。生产容量、峰值并发、备份恢复和实际历史质量仍需部署环境验收。
