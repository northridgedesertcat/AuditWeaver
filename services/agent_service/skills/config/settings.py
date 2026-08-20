"""Skills 专属配置(索引名 / 条数上限)。

索引名沿用 ``common.env`` 的全局默认,可通过 ``AE_SKILL_ES_INDEX_*`` 覆盖,
这样 Skills 与 Django 侧共用同一份 ES 索引配置,避免漂移。
"""
from common.env import (
    get_env,
    ES_INDEX_NGINX_RAW,
    ES_INDEX_ANALYSIS_REPORTS,
    ES_INDEX_MATCHED_LOGS,
)

# 索引名(可被 .env 的 AE_SKILL_ES_INDEX_* 覆盖)
ES_INDEX_RAW = get_env('AE_SKILL_ES_INDEX_RAW', ES_INDEX_NGINX_RAW)
ES_INDEX_REPORTS = get_env('AE_SKILL_ES_INDEX_REPORTS', ES_INDEX_ANALYSIS_REPORTS)
ES_INDEX_EVENTS = get_env('AE_SKILL_ES_INDEX_EVENTS', ES_INDEX_MATCHED_LOGS)

# 返回条数上限(Skill 只读,限制单次返回体量)
MAX_SIZE_RAW = 200
MAX_SIZE_REPORTS = 100
MAX_SIZE_EVENTS = 200
