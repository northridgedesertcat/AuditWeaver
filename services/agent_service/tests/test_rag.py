"""RAG P0-3 单元测试(对齐设计 §3.4)。

覆盖:
- RRF 纯函数:单路 / 两路同 source_id 合并 / 两路不同 / 空输入 / top_k 截断 /
  确定性排序 / source_id 为空兜底
- evidence_from_es_hit:标准命中 / source_id 优先级 / 无 content 走 fallback / source_type 优先取
- retriever 编排:两路融合 / 单路降级(BM25-only / Vector-only) / 两路失败 / embed 失败抛错

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_rag
"""
import os
import sys
import unittest
from unittest.mock import patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.llm.exceptions import LLMConfigError
from shared.rag.result import Evidence, EvidencePack, evidence_from_es_hit
from shared.rag.rrf import rrf_fusion


def _mk_ev(sid: str, content: str = "x", score: float = 0.5, source_type: str = "rag") -> Evidence:
    return Evidence(
        content=content, source_id=sid, score=score, source_type=source_type
    )


class TestRRFFusion(unittest.TestCase):
    """RRF 纯函数测试(无 IO,确定性)。"""

    def test_single_route_passthrough(self):
        """单路:输出顺序与输入一致,score=1/(k+rank)。"""
        evs = [_mk_ev("1", "a"), _mk_ev("2", "b"), _mk_ev("3", "c")]
        result = rrf_fusion([evs], k=60)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].source_id, "1")
        self.assertEqual(result[1].source_id, "2")
        self.assertEqual(result[2].source_id, "3")
        # rank 从 1 开始:score = 1/(60+1), 1/(60+2), 1/(60+3)
        self.assertAlmostEqual(result[0].score, 1.0 / 61, places=6)
        self.assertAlmostEqual(result[1].score, 1.0 / 62, places=6)
        self.assertAlmostEqual(result[2].score, 1.0 / 63, places=6)

    def test_two_routes_same_id_merges(self):
        """两路同 source_id:合并,score 累加。"""
        ev1 = [_mk_ev("1", "a")]
        ev2 = [_mk_ev("1", "a")]  # 同 source_id 不同路
        result = rrf_fusion([ev1, ev2], k=60)
        self.assertEqual(len(result), 1)
        # 两路都排第一,score = 1/61 + 1/61
        self.assertAlmostEqual(result[0].score, 2.0 / 61, places=6)

    def test_two_routes_different_ids_no_merge(self):
        """两路不同 source_id:不合并,各算各的。"""
        ev1 = [_mk_ev("1", "a")]
        ev2 = [_mk_ev("2", "b")]
        result = rrf_fusion([ev1, ev2], k=60)
        self.assertEqual(len(result), 2)
        # 都是 rank=1,score=1/61,次级按 source_id 字典序
        self.assertEqual(result[0].source_id, "1")
        self.assertEqual(result[1].source_id, "2")
        self.assertAlmostEqual(result[0].score, 1.0 / 61, places=6)

    def test_empty_input_returns_empty(self):
        """空输入:返回 []。"""
        self.assertEqual(rrf_fusion([]), [])
        self.assertEqual(rrf_fusion([[]]), [])
        self.assertEqual(rrf_fusion([[], []]), [])

    def test_top_k_truncation(self):
        """top_k 截断:输入 10 条,返回 3 条。"""
        evs = [_mk_ev(str(i), f"c{i}") for i in range(10)]
        result = rrf_fusion([evs], k=60, top_k=3)
        self.assertEqual(len(result), 3)
        # 截断的是 rank 最高的前 3 条
        self.assertEqual(result[0].source_id, "0")
        self.assertEqual(result[1].source_id, "1")
        self.assertEqual(result[2].source_id, "2")

    def test_deterministic_same_input_same_output(self):
        """同输入必同输出(分数 + 顺序都一致)。"""
        ev1 = [_mk_ev("1", "a"), _mk_ev("2", "b")]
        ev2 = [_mk_ev("3", "c")]
        r1 = rrf_fusion([ev1, ev2], k=60)
        r2 = rrf_fusion([ev1, ev2], k=60)
        self.assertEqual([e.source_id for e in r1], [e.source_id for e in r2])
        self.assertEqual([e.score for e in r1], [e.score for e in r2])

    def test_same_score_breaks_tie_by_source_id(self):
        """分数相同:按 source_id 字典序做次级排序(确定性)。"""
        # 两路各自排第一,score 都 = 1/61
        ev1 = [_mk_ev("b", "b")]
        ev2 = [_mk_ev("a", "a")]
        result = rrf_fusion([ev1, ev2], k=60)
        # 分数相同,source_id "a" 字典序在前
        self.assertEqual(result[0].source_id, "a")
        self.assertEqual(result[1].source_id, "b")

    def test_empty_source_id_fallback_to_content_key(self):
        """source_id 为空:用 content+route+rank 兜底,不 crash,不合并。"""
        ev1 = [_mk_ev("", "aaa")]
        ev2 = [_mk_ev("", "aaa")]  # 同 content 但不同路
        result = rrf_fusion([ev1, ev2], k=60)
        # 空 sid 用 route+rank+content key 唯一化,不合并
        self.assertEqual(len(result), 2)

    def test_three_routes_merges_across_all(self):
        """三路融合:同 source_id 在三路都出现,score 累加 3 次。"""
        ev1 = [_mk_ev("X", "a")]
        ev2 = [_mk_ev("X", "a")]
        ev3 = [_mk_ev("X", "a")]
        result = rrf_fusion([ev1, ev2, ev3], k=60)
        self.assertEqual(len(result), 1)
        # 三路都 rank=1,score = 3 * (1/61)
        self.assertAlmostEqual(result[0].score, 3.0 / 61, places=6)


class TestEvidenceFromESHit(unittest.TestCase):
    """evidence_from_es_hit:ES hit → Evidence 转换。"""

    def test_standard_hit_with_content_field(self):
        """标准命中:_source.content 存在,source_id 优先 event_id。"""
        hit = {
            "_id": "abc",
            "_score": 1.5,
            "_source": {
                "content": "SQL 注入攻击",
                "event_id": "evt-001",
                "source_type": "matched_logs",
            },
        }
        ev = evidence_from_es_hit(hit, source_type="rag-corpus")
        self.assertEqual(ev.content, "SQL 注入攻击")
        self.assertEqual(ev.source_id, "evt-001")
        self.assertEqual(ev.score, 1.5)
        # source_type 优先从 _source 取,否则用传入的兜底
        self.assertEqual(ev.source_type, "matched_logs")

    def test_source_id_priority_event_id_first(self):
        """source_id 优先级:event_id > source_id > _id。"""
        hit = {
            "_id": "abc",
            "_source": {"event_id": "evt-001", "source_id": "sid-002"},
        }
        ev = evidence_from_es_hit(hit, source_type="idx")
        self.assertEqual(ev.source_id, "evt-001")

    def test_source_id_fallback_to_id(self):
        """无 event_id/source_id:用 _id。"""
        hit = {"_id": "abc", "_source": {}}
        ev = evidence_from_es_hit(hit, source_type="idx")
        self.assertEqual(ev.source_id, "abc")

    def test_fallback_content_from_business_fields(self):
        """无 content 字段:从 attack_type/ip/method 拼描述(_fallback_content)。"""
        hit = {
            "_id": "abc",
            "_source": {
                "attack_type": "sql_injection",
                "rule_id": "rule-001",
                "log_context": {
                    "ip": "1.2.3.4",
                    "method": "GET",
                    "path": "/login",
                    "status": 200,
                },
            },
        }
        ev = evidence_from_es_hit(hit, source_type="matched_logs")
        self.assertIn("sql_injection", ev.content)
        self.assertIn("1.2.3.4", ev.content)
        self.assertIn("GET", ev.content)
        self.assertIn("rule-001", ev.content)

    def test_source_type_fallback_to_index_name(self):
        """_source 无 source_type 字段:用传入的索引名兜底。"""
        hit = {"_id": "abc", "_source": {"content": "x"}}
        ev = evidence_from_es_hit(hit, source_type="my-index")
        self.assertEqual(ev.source_type, "my-index")

    def test_score_override(self):
        """显式 score 优先于 hit['_score']。"""
        hit = {"_id": "abc", "_score": 1.0, "_source": {"content": "x"}}
        ev = evidence_from_es_hit(hit, source_type="idx", score=99.9)
        self.assertEqual(ev.score, 99.9)


class TestRetriever(unittest.TestCase):
    """retriever 编排测试:mock embed/bm25/knn,验证融合与降级。"""

    @patch("shared.rag.retriever.knn_search")
    @patch("shared.rag.retriever.bm25_search")
    @patch("shared.rag.retriever.embed_query")
    def test_both_routes_success_fused(
        self, mock_embed, mock_bm25, mock_knn
    ):
        """两路都成功 → RRF 融合(fused=True, sources 含 bm25+vector)。"""
        from shared.rag.retriever import retrieve

        mock_embed.return_value = [0.1] * 8  # 维度无所谓,mock 不到 ES
        # BM25 路:1 在前,2 在后
        mock_bm25.return_value = [_mk_ev("1", "bm25-a"), _mk_ev("2", "bm25-b")]
        # Vector 路:2 在前,3 在后(2 在两路都靠前,RRF 后应排第一)
        mock_knn.return_value = [_mk_ev("2", "vec-b"), _mk_ev("3", "vec-c")]

        pack = retrieve("test query", top_k=5)

        self.assertTrue(pack.fused)
        self.assertEqual(set(pack.sources), {"bm25", "vector"})
        # source_id="2" 在两路都出现且排名靠前,RRF 累计分数最高
        self.assertEqual(pack.evidences[0].source_id, "2")
        self.assertLessEqual(len(pack.evidences), 5)

    @patch("shared.rag.retriever.knn_search")
    @patch("shared.rag.retriever.bm25_search")
    @patch("shared.rag.retriever.embed_query")
    def test_only_bm25_success_degrades(
        self, mock_embed, mock_bm25, mock_knn
    ):
        """只 BM25 成功 → 单路降级(fused=False, sources=['bm25'])。"""
        from shared.rag.retriever import retrieve

        mock_embed.return_value = [0.1] * 8
        mock_bm25.return_value = [_mk_ev("1"), _mk_ev("2")]
        mock_knn.return_value = []  # vector 失败

        pack = retrieve("test", top_k=5)

        self.assertFalse(pack.fused)
        self.assertEqual(pack.sources, ["bm25"])
        self.assertEqual(len(pack.evidences), 2)
        # 截断到 top_k(2 < 5,不截断)
        self.assertEqual(pack.evidences[0].source_id, "1")

    @patch("shared.rag.retriever.knn_search")
    @patch("shared.rag.retriever.bm25_search")
    @patch("shared.rag.retriever.embed_query")
    def test_only_vector_success_degrades(
        self, mock_embed, mock_bm25, mock_knn
    ):
        """只 Vector 成功 → 单路降级(fused=False, sources=['vector'])。"""
        from shared.rag.retriever import retrieve

        mock_embed.return_value = [0.1] * 8
        mock_bm25.return_value = []
        mock_knn.return_value = [_mk_ev("1"), _mk_ev("2"), _mk_ev("3")]

        pack = retrieve("test", top_k=2)  # top_k=2 触发截断

        self.assertFalse(pack.fused)
        self.assertEqual(pack.sources, ["vector"])
        self.assertEqual(len(pack.evidences), 2)  # 截断到 2

    @patch("shared.rag.retriever.knn_search")
    @patch("shared.rag.retriever.bm25_search")
    @patch("shared.rag.retriever.embed_query")
    def test_both_routes_fail_empty_pack(
        self, mock_embed, mock_bm25, mock_knn
    ):
        """两路都失败 → 空 EvidencePack(sources=[])。"""
        from shared.rag.retriever import retrieve

        mock_embed.return_value = [0.1] * 8
        mock_bm25.return_value = []
        mock_knn.return_value = []

        pack = retrieve("test", top_k=5)

        self.assertTrue(pack.is_empty)
        self.assertFalse(pack.fused)
        self.assertEqual(pack.sources, [])

    @patch("shared.rag.retriever.embed_query")
    def test_embed_failure_raises_no_degrade(self, mock_embed):
        """embed_query 失败 → 抛错,不降级(配置问题应显式报错)。"""
        from shared.rag.retriever import retrieve

        mock_embed.side_effect = LLMConfigError("missing api_key")

        with self.assertRaises(LLMConfigError):
            retrieve("test", top_k=5)

    def test_empty_query_returns_empty_pack(self):
        """空查询:直接返回空 pack,不调 embed/bm25/knn。"""
        from shared.rag.retriever import retrieve

        pack = retrieve("")
        self.assertTrue(pack.is_empty)
        self.assertFalse(pack.fused)
        self.assertEqual(pack.sources, [])
        self.assertEqual(pack.query, "")


class TestEvidencePack(unittest.TestCase):
    """EvidencePack 容器属性测试。"""

    def test_source_ids_property(self):
        pack = EvidencePack(
            query="q",
            evidences=[_mk_ev("1"), _mk_ev("2"), _mk_ev("3")],
            fused=True,
            sources=["bm25", "vector"],
        )
        self.assertEqual(pack.source_ids, ["1", "2", "3"])

    def test_is_empty_property(self):
        empty_pack = EvidencePack(query="q", evidences=[])
        self.assertTrue(empty_pack.is_empty)
        non_empty = EvidencePack(
            query="q", evidences=[_mk_ev("1")]
        )
        self.assertFalse(non_empty.is_empty)


if __name__ == "__main__":
    unittest.main()
