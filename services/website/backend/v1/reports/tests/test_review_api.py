"""报告审核 API 测试（规格 §8 共 22 条）。

覆盖：认证、字段校验、事务双写回滚、改判留痕、Agent UPSERT 不冲掉审核结论、
状态过滤/排序白名单、认领机制（幂等/冲突/超时接管/释放）、详情/历史/统计。
"""
import json
from datetime import timedelta
from unittest import mock

from django.db import connection
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from reports.models import AnalysisReport, ReportReview, ReportReviewHistory

PWD = 'Admin!pass123'

# Agent 管线同款 UPSERT（services/agent/repository/mysql_report_repository.py）。
# 测试 #9 用它锁定关键行为：同 event_id 重新分析只覆盖业务列，审核/认领列原样保留。
_UPSERT_SQL = """
INSERT INTO analysis_report (
    event_id, ip, path, method, status, user_agent, detect_type,
    risk_level, risk_score, attack_type_ai, summary,
    reasoning, recommendations,
    log_timestamp, analysis_timestamp, ingestion_time,
    raw_response, original_log,
    created_at, updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s,
    %s, %s, %s,
    %s, %s,
    %s, %s
)
ON DUPLICATE KEY UPDATE
    ip = VALUES(ip),
    path = VALUES(path),
    method = VALUES(method),
    status = VALUES(status),
    user_agent = VALUES(user_agent),
    detect_type = VALUES(detect_type),
    risk_level = VALUES(risk_level),
    risk_score = VALUES(risk_score),
    attack_type_ai = VALUES(attack_type_ai),
    summary = VALUES(summary),
    reasoning = VALUES(reasoning),
    recommendations = VALUES(recommendations),
    log_timestamp = VALUES(log_timestamp),
    analysis_timestamp = VALUES(analysis_timestamp),
    ingestion_time = VALUES(ingestion_time),
    raw_response = VALUES(raw_response),
    original_log = VALUES(original_log),
    updated_at = VALUES(updated_at)
"""


def _upsert_params(event_id, summary='重放后的新摘要'):
    """与 MySQLReportRepository.upsert 的参数构造保持一致（显式 18 业务列 + 时间列）。"""
    now = timezone.now()
    return (
        event_id,
        '10.0.0.8', '/api/health', 'GET', 200, 'upsert-replay', 'sql_injection',
        'high', 88, 'SQL注入', summary,
        json.dumps(['重放推理'], ensure_ascii=False),
        json.dumps(['封禁IP'], ensure_ascii=False),
        now, now, now,
        None, None,
        now, now,
    )


def make_report(event_id='evt-1', risk_level='high', risk_score=80,
                summary='初始摘要', minutes_ago=10):
    """构造一份报告（时间错开保证列表顺序可断言）。"""
    ts = timezone.now() - timedelta(minutes=minutes_ago)
    return AnalysisReport.objects.create(
        event_id=event_id,
        ip='10.0.0.8', path='/admin?id=1', method='GET', status=200,
        user_agent='pytest', detect_type='sql_injection',
        risk_level=risk_level, risk_score=risk_score,
        attack_type_ai='SQL注入', summary=summary,
        reasoning=['步骤1'], recommendations=['封禁IP'],
        log_timestamp=ts, analysis_timestamp=ts, ingestion_time=ts,
    )


class ReviewTestsBase(APITestCase):
    """公共基类：两个管理员 + 默认审核请求体。"""

    def setUp(self):
        self.root = User.objects.create_user(
            username='root', password=PWD, role=User.Role.ROOT_ADMIN,
            display_name='管理员甲',
        )
        self.admin = User.objects.create_user(
            username='secops', password=PWD, role=User.Role.ADMIN,
            display_name='张三',
        )
        self.review_payload = {
            'verdict': 'false_positive',
            'category': 'normal_business',
            'actions': ['ignored'],
            'comment': '内部健康检查被规则命中，属正常业务流量',
        }

    def auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def claim(self, event_id, user):
        self.auth(user)
        return self.client.post(f'/api/v1/reports/{event_id}/claim/')

    def review(self, event_id, user, payload=None):
        self.auth(user)
        return self.client.post(
            f'/api/v1/reports/{event_id}/review/', payload or self.review_payload,
            format='json')


class AuthPermissionTests(ReviewTestsBase):
    """#1 未认证拒绝。"""

    def test_unauthenticated_rejected(self):
        make_report('evt-auth')
        self.assertEqual(
            self.client.post('/api/v1/reports/evt-auth/review/',
                             self.review_payload, format='json').status_code, 401)
        self.assertEqual(
            self.client.post('/api/v1/reports/evt-auth/claim/').status_code, 401)


class ReviewSubmitTests(ReviewTestsBase):
    """#2/#3/#4/#5/#6/#7/#8/#9/#10/#19 提交/改判/校验/事务。"""

    def test_first_review_success(self):
        """#2 首次审核：201，双表落库，报告置 processed，认领字段清空。"""
        make_report('evt-a')
        make_report('evt-b', risk_score=95)  # 用于断言自动下一条
        resp = self.review('evt-a', self.admin)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['reviewStatus'], 'processed')
        self.assertEqual(resp.data['review']['verdict'], 'false_positive')
        self.assertEqual(resp.data['review']['verdictLabel'], '误报')
        self.assertEqual(resp.data['review']['categoryLabel'], '正常业务')
        self.assertEqual(resp.data['review']['actionLabels'], ['忽略/关闭'])
        self.assertEqual(resp.data['review']['changeType'], 'created')
        self.assertEqual(resp.data['review']['reviewerDisplayName'], '张三')
        self.assertEqual(resp.data['nextEventId'], 'evt-b')  # 风险评分更高者优先

        report = AnalysisReport.objects.get(event_id='evt-a')
        self.assertEqual(report.review_status, 'processed')
        self.assertEqual(report.reviewed_by, self.admin)
        self.assertIsNotNone(report.reviewed_at)
        self.assertIsNone(report.claimed_by)
        self.assertIsNone(report.claimed_at)

        review = ReportReview.objects.get(report=report)
        self.assertEqual(review.verdict, 'false_positive')
        self.assertEqual(review.reviewer, self.admin)
        self.assertEqual(ReportReviewHistory.objects.filter(report=report).count(), 1)

    def test_reviewer_taken_from_auth_user(self):
        """#3 reviewer 取自认证用户，请求体伪造被忽略。"""
        make_report('evt-fake')
        payload = dict(self.review_payload, reviewer=self.root.id)
        resp = self.review('evt-fake', self.admin, payload)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(ReportReview.objects.get().reviewer, self.admin)

    def test_invalid_enum_fields(self):
        """#4 非法 verdict/category/actions → 400 字段级定位。"""
        make_report('evt-enum')
        cases = [
            (dict(self.review_payload, verdict='bogus'), 'verdict'),
            (dict(self.review_payload, category='bogus'), 'category'),
            (dict(self.review_payload, actions=['nuke']), 'actions'),
        ]
        for payload, field in cases:
            resp = self.review('evt-enum', self.admin, payload)
            self.assertEqual(resp.status_code, 400, payload)
            self.assertIn(field, resp.data)

    def test_comment_required_and_min_length(self):
        """#5 comment 缺失 / 去空格后过短 → 400。"""
        make_report('evt-comment')
        for payload in (
            {k: v for k, v in self.review_payload.items() if k != 'comment'},
            dict(self.review_payload, comment='abc'),
            dict(self.review_payload, comment='   '),
        ):
            resp = self.review('evt-comment', self.admin, payload)
            self.assertEqual(resp.status_code, 400, payload)
            self.assertIn('comment', resp.data)

    def test_uncertain_soft_validation(self):
        """#6 uncertain + 确定性处置动作 → 400 软校验。"""
        make_report('evt-soft')
        payload = dict(self.review_payload,
                       verdict='uncertain', actions=['ip_blocked'])
        resp = self.review('evt-soft', self.admin, payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('actions', resp.data)

    def test_rollback_when_history_create_fails(self):
        """#7 流水落库失败时整体回滚：当前态/流水均无残留，报告状态不变。"""
        make_report('evt-rb')
        self.auth(self.admin)
        with mock.patch.object(ReportReviewHistory.objects, 'create',
                               side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/v1/reports/evt-rb/review/',
                                 self.review_payload, format='json')
        self.assertEqual(ReportReview.objects.count(), 0)
        self.assertEqual(ReportReviewHistory.objects.count(), 0)
        self.assertEqual(AnalysisReport.objects.get(event_id='evt-rb').review_status,
                         'pending')

    def test_revise_updates_review_and_appends_history(self):
        """#8 改判：200，Review 仍 1 行且结论更新，History 2 行且 revised 在前。"""
        make_report('evt-rev')
        self.assertEqual(self.review('evt-rev', self.admin).status_code, 201)

        payload = dict(self.review_payload,
                       verdict='correct', category='real_attack',
                       actions=['ip_blocked', 'notified'])
        resp = self.review('evt-rev', self.root, payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['review']['changeType'], 'revised')

        report = AnalysisReport.objects.get(event_id='evt-rev')
        self.assertEqual(ReportReview.objects.filter(report=report).count(), 1)
        review = ReportReview.objects.get(report=report)
        self.assertEqual(review.verdict, 'correct')
        self.assertEqual(review.reviewer, self.root)  # 改判人更新
        self.assertEqual(report.reviewed_by, self.root)

        history = ReportReviewHistory.objects.filter(report=report)
        self.assertEqual(history.count(), 2)
        self.assertEqual([h.change_type for h in history], ['revised', 'created'])

    def test_agent_upsert_preserves_review(self):
        """#9 Agent 管线 UPSERT 重放：内容列更新，审核/认领列原样保留。"""
        make_report('evt-up', summary='原始摘要')
        self.assertEqual(self.review('evt-up', self.admin).status_code, 201)

        with connection.cursor() as cur:
            cur.execute(_UPSERT_SQL, _upsert_params('evt-up'))

        report = AnalysisReport.objects.get(event_id='evt-up')
        self.assertEqual(report.summary, '重放后的新摘要')   # 内容列被覆盖
        self.assertEqual(report.review_status, 'processed')  # 审核列保留
        self.assertEqual(report.reviewed_by, self.admin)
        review = ReportReview.objects.get(report=report)
        self.assertEqual(review.verdict, 'false_positive')
        self.assertEqual(review.reviewer, self.admin)

    def test_report_not_found(self):
        """#10 review/claim/history 三端点对不存在报告均 404。"""
        self.auth(self.admin)
        self.assertEqual(
            self.client.post('/api/v1/reports/no-such/review/',
                             self.review_payload, format='json').status_code, 404)
        self.assertEqual(
            self.client.post('/api/v1/reports/no-such/claim/').status_code, 404)
        self.assertEqual(
            self.client.get('/api/v1/reports/no-such/review/history/').status_code, 404)

    def test_pending_can_submit_without_claim(self):
        """#19 宽容设计：pending 未认领直接提交 → 201。"""
        make_report('evt-direct')
        resp = self.review('evt-direct', self.admin)
        self.assertEqual(resp.status_code, 201)


class ListFilterTests(ReviewTestsBase):
    """#11/#12 列表状态过滤与排序白名单。"""

    def test_review_status_filter_and_reviewed_by_me(self):
        """#11 review_status 过滤正确；reviewed_by=me 只看自己处理过的。"""
        make_report('evt-p', minutes_ago=30)              # 保持 pending
        make_report('evt-pr-root', minutes_ago=20)        # root 处理
        make_report('evt-pr-admin', minutes_ago=10)       # admin 处理
        self.review('evt-pr-root', self.root)
        self.review('evt-pr-admin', self.admin)

        self.auth(self.root)
        resp = self.client.get('/api/v1/reports/list/',
                               {'review_status': 'pending'})
        self.assertEqual([r['id'] for r in resp.data['data']], ['evt-p'])

        resp = self.client.get('/api/v1/reports/list/',
                               {'review_status': 'processed'})
        self.assertEqual(resp.data['total'], 2)

        resp = self.client.get('/api/v1/reports/list/',
                               {'review_status': 'processed', 'reviewed_by': 'me'})
        items = resp.data['data']
        self.assertEqual([r['id'] for r in items], ['evt-pr-root'])
        self.assertEqual(items[0]['reviewStatus'], 'processed')
        self.assertEqual(items[0]['reviewedBy'], '管理员甲')

    def test_ordering_whitelist(self):
        """#12 非法 ordering 400；-risk_score 生效。"""
        make_report('evt-lo', risk_score=10)
        make_report('evt-hi', risk_score=99)
        self.auth(self.root)
        resp = self.client.get('/api/v1/reports/list/', {'ordering': "risk_score;--"})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.get('/api/v1/reports/list/', {'ordering': '-risk_score'})
        self.assertEqual(resp.data['data'][0]['id'], 'evt-hi')


class ClaimTests(ReviewTestsBase):
    """#13~#18 认领机制。"""

    def test_claim_success(self):
        """#13 认领成功：claimed + 认领人/时间写入。"""
        make_report('evt-c')
        resp = self.claim('evt-c', self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['takenOver'])
        self.assertEqual(resp.data['claimedBy'], '张三')
        report = AnalysisReport.objects.get(event_id='evt-c')
        self.assertEqual(report.review_status, 'claimed')
        self.assertEqual(report.claimed_by, self.admin)
        self.assertIsNotNone(report.claimed_at)

    def test_claim_idempotent_keeps_claimed_at(self):
        """#14 自己重复认领幂等，claimed_at 不刷新（断言行为固定）。"""
        make_report('evt-idem')
        self.claim('evt-idem', self.admin)
        past = timezone.now() - timedelta(minutes=5)
        AnalysisReport.objects.filter(event_id='evt-idem').update(claimed_at=past)

        resp = self.claim('evt-idem', self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['takenOver'])
        report = AnalysisReport.objects.get(event_id='evt-idem')
        self.assertEqual(report.claimed_at, past)  # 未漂移

    def test_claim_conflict_shows_claimer(self):
        """#15 他人认领未超时 → 409 且错误信息含认领人显示名。"""
        make_report('evt-conflict')
        self.claim('evt-conflict', self.admin)
        resp = self.claim('evt-conflict', self.root)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('张三', resp.data['error'])

    def test_claim_takeover_after_timeout(self):
        """#16 超时接管：claimed_at 置 31 分钟前，他人 claim → takenOver=true。"""
        make_report('evt-stale')
        self.claim('evt-stale', self.admin)
        AnalysisReport.objects.filter(event_id='evt-stale').update(
            claimed_at=timezone.now() - timedelta(minutes=31))

        resp = self.claim('evt-stale', self.root)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['takenOver'])
        report = AnalysisReport.objects.get(event_id='evt-stale')
        self.assertEqual(report.claimed_by, self.root)

    def test_release_by_claimer_and_by_other(self):
        """#17 认领人释放成功回 pending；非认领人 403。"""
        make_report('evt-rel')
        self.claim('evt-rel', self.admin)  # 认领人 = admin
        self.auth(self.root)               # 切换为非认领人
        resp = self.client.post('/api/v1/reports/evt-rel/release/')
        self.assertEqual(resp.status_code, 403)

        self.auth(self.admin)
        resp = self.client.post('/api/v1/reports/evt-rel/release/')
        self.assertEqual(resp.status_code, 200)
        report = AnalysisReport.objects.get(event_id='evt-rel')
        self.assertEqual(report.review_status, 'pending')
        self.assertIsNone(report.claimed_by)
        self.assertIsNone(report.claimed_at)

    def test_review_conflict_when_claimed_by_other(self):
        """#18 他人有效认领时提交 → 409，报告状态与数据不被改变。"""
        make_report('evt-lock')
        self.claim('evt-lock', self.admin)
        resp = self.review('evt-lock', self.root)
        self.assertEqual(resp.status_code, 409)
        self.assertIn('张三', resp.data['error'])
        report = AnalysisReport.objects.get(event_id='evt-lock')
        self.assertEqual(report.review_status, 'claimed')
        self.assertFalse(ReportReview.objects.exists())


class DetailHistoryStatsTests(ReviewTestsBase):
    """#20/#21/#22 详情、历史与统计。"""

    def test_detail_review_fields_and_deleted_reviewer(self):
        """#20 详情返回 review/认领信息；处理人删除后仍 200 且 reviewer=null。"""
        make_report('evt-d')
        resp = self.client.get('/api/v1/reports/evt-d/')
        self.auth(self.root)
        resp = self.client.get('/api/v1/reports/evt-d/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reviewStatus'], 'pending')
        self.assertIsNone(resp.data['review'])
        self.assertIsNone(resp.data['claimedBy'])

        worker = User.objects.create_user(username='worker', password=PWD,
                                          display_name='临时工')
        self.assertEqual(self.review('evt-d', worker).status_code, 201)
        worker.delete()  # SET_NULL：审核记录保留，处理人置空

        self.auth(self.root)
        resp = self.client.get('/api/v1/reports/evt-d/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reviewStatus'], 'processed')
        self.assertIsNotNone(resp.data['review'])
        self.assertIsNone(resp.data['review']['reviewer'])
        self.assertIsNone(resp.data['reviewedBy'])

    def test_history_endpoint_order_and_auth(self):
        """#21 历史端点：最新在前；未认证 401。"""
        make_report('evt-h')
        resp = self.client.get('/api/v1/reports/evt-h/review/history/')
        self.assertEqual(resp.status_code, 401)

        self.review('evt-h', self.admin)
        self.review('evt-h', self.root,
                    dict(self.review_payload, verdict='correct'))
        self.auth(self.admin)
        resp = self.client.get('/api/v1/reports/evt-h/review/history/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['eventId'], 'evt-h')
        self.assertEqual(resp.data['total'], 2)
        self.assertEqual([h['changeType'] for h in resp.data['history']],
                         ['revised', 'created'])
        self.assertEqual(resp.data['history'][0]['verdictLabel'], '报告正确')
        self.assertEqual(resp.data['history'][1]['verdictLabel'], '误报')

    def test_stats_new_keys(self):
        """#22 stats 新键计数正确且现有四键保留。"""
        make_report('evt-s1', minutes_ago=40)
        make_report('evt-s2', minutes_ago=30)
        make_report('evt-s3', minutes_ago=20)
        make_report('evt-s4', minutes_ago=10)
        self.claim('evt-s3', self.admin)
        self.review('evt-s4', self.admin)

        self.auth(self.root)
        resp = self.client.get('/api/v1/reports/stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 4)
        self.assertEqual(resp.data['pendingReview'], 2)
        self.assertEqual(resp.data['claimedCount'], 1)
        self.assertEqual(resp.data['todayProcessed'], 1)
        for key in ('highRisk', 'mediumRisk', 'todayNew'):
            self.assertIn(key, resp.data)
