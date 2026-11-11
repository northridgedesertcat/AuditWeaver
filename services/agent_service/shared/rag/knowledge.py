"""知识库语料加载与切片(knowledge 路,对齐 RAG优化需求文档 §P0-1)。

语料格式:markdown + YAML frontmatter(resources/rag/knowledge/ 目录):
    ---
    doc_id: attack_types/sqli      # 全局唯一,chunk source_id = {doc_id}::{chunk_index}
    source: attack_types           # 语料大类(attack_types / remediation)
    attack_type: sql_injection     # 标量过滤字段(knowledge 必填;remediation 用 general)
    severity: critical
    ---
    # H1 标题
    ## H2 小节1
    正文...
    ## H2 小节2
    ...

切片策略(对齐原方案 §4.5.2 chunker 设计):
- 按 H2(## 小节)切片,1 小节 = 1 chunk(安全知识天然按主题分节,粒度合适)
- 每 chunk 带 H1 上下文前缀("# SQL 注入 (SQL Injection)\n\n## 原理\n..."),
  embedding 后小节标题可命中 H1 语义("SQL 注入"贯穿所有 chunk)
- frontmatter 字段透传为 corpus 文档元数据(attack_type 供 P1-2 元数据过滤)

不做的事:
- 不做 embedding(embed_batch 在 build 脚本统一做,单一出口)
- 不做段落级二次切片(当前语料单节均 <800 字,超长时在语料侧拆节)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# 知识语料根目录(项目根/resources/rag/knowledge/)
KNOWLEDGE_DIR = (
    Path(__file__).resolve().parents[4] / "resources" / "rag" / "knowledge"
)

_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass
class KnowledgeChunk:
    """知识库切片(语料侧中间结构,build 脚本转 corpus 文档后 embed)。"""

    source_id: str                      # {doc_id}::{chunk_index}(corpus _id 同值,upsert 幂等键)
    content: str                        # H1 上下文 + H2 小节正文
    attack_type: str                    # 标量过滤字段(knowledge 必填)
    source_type: str = "knowledge"      # 双路语料标记
    severity: str = ""                  # frontmatter severity
    doc_id: str = ""                    # 来源文档 ID
    section_title: str = ""             # H2 小节标题(观测用)
    raw: dict = field(default_factory=dict)

    def to_corpus_doc(self) -> dict:
        """转为 RAG 语料文档(与 case 路统一结构,build 脚本统一 embed + 写入)。"""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "attack_type": self.attack_type,
            "content": self.content,
            "raw": {
                "doc_id": self.doc_id,
                "section_title": self.section_title,
                "severity": self.severity,
            },
        }


def load_knowledge_chunks(knowledge_dir: Path | str | None = None) -> list[KnowledgeChunk]:
    """加载知识语料目录下全部 markdown,解析 frontmatter + H2 切片。

    Args:
        knowledge_dir: 语料目录,默认 resources/rag/knowledge/

    Returns:
        全部文档的全部 H2 切片;frontmatter 缺 doc_id/attack_type 的文档跳过并告警
        (显式不静默:语料是手动维护的,字段缺失应在建库时暴露)
    """
    root = Path(knowledge_dir) if knowledge_dir else KNOWLEDGE_DIR
    if not root.exists():
        logger.warning("[rag.knowledge] 知识语料目录不存在: %s", root)
        return []

    chunks: list[KnowledgeChunk] = []
    md_files = sorted(root.rglob("*.md"))
    for md in md_files:
        try:
            doc_chunks = _chunk_markdown_file(md)
        except Exception as e:
            logger.error("[rag.knowledge] 解析失败 %s: %s: %s", md, type(e).__name__, e)
            continue
        if doc_chunks:
            chunks.extend(doc_chunks)
            logger.info(
                "[rag.knowledge] %s → %d chunks (attack_type=%s)",
                md.relative_to(root), len(doc_chunks), doc_chunks[0].attack_type,
            )
    logger.info("[rag.knowledge] 知识语料加载完成: %d 个文件, %d 个 chunk", len(md_files), len(chunks))
    return chunks


def _chunk_markdown_file(path: Path) -> list[KnowledgeChunk]:
    """单文件解析:frontmatter + H1 提取 + H2 切片。"""
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)

    doc_id = str(frontmatter.get("doc_id", "")).strip()
    attack_type = str(frontmatter.get("attack_type", "")).strip()
    if not doc_id or not attack_type:
        raise ValueError(
            f"frontmatter 缺必填字段 doc_id/attack_type(doc_id={doc_id!r}, "
            f"attack_type={attack_type!r})"
        )
    severity = str(frontmatter.get("severity", "")).strip()

    # H1 上下文(全文第一个 # 标题;无 H1 时用 doc_id 兜底)
    h1_match = re.search(r"^#\s+(?P<title>.+?)\s*$", body, re.MULTILINE)
    h1_context = f"# {h1_match.group('title')}" if h1_match else f"# {doc_id}"

    # H2 切片:match 按出现顺序,section 正文 = 本 H2 行到下一个 H2 行(或文末)
    matches = list(_H2_RE.finditer(body))
    if not matches:
        raise ValueError(f"未找到 H2 小节(## )无法切片: {path.name}")

    chunks: list[KnowledgeChunk] = []
    for idx, m in enumerate(matches):
        section_body = body[m.start(): matches[idx + 1].start() if idx + 1 < len(matches) else len(body)]
        section_title = m.group("title")
        # chunk content = H1 上下文 + 该 H2 小节(含 ## 标题行)
        content = f"{h1_context}\n\n{section_body.strip()}"
        chunks.append(KnowledgeChunk(
            source_id=f"{doc_id}::{idx}",
            content=content,
            attack_type=attack_type,
            severity=severity,
            doc_id=doc_id,
            section_title=section_title,
            raw={"doc_id": doc_id, "section_title": section_title, "severity": severity},
        ))
    return chunks


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """拆分 YAML frontmatter(--- ... ---)与正文;无 frontmatter 返回 ({}, text)。"""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, text
    return fm, parts[2]
