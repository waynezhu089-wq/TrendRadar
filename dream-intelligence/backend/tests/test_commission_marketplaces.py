import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from app.connectors.commissions import candidates, detail, CommissionConnector, SOURCES, fetch_public
from app.db.models import CommissionLead
from app.research.commissions import lead_output

TAHOU_LIST='''<a class="earn-card" href="/earn/220633831788337157"><span class="title">招商宣传短视频制作</span>
<div class="price-value">￥4.8W</div><div class="status">招募中</div></a>
<a class="earn-card" href="/earn/2"><span class="title">海外AI漫剧</span><div class="status">招募中</div></a>'''
TAHOU_DETAIL='''<div class="hero-title">招商宣传短视频制作</div><div class="tag-row">AI短视频 视频交付物</div>
<div class="meta-item"><span class="meta-label">发布时间</span><span class="meta-val">2026/10/21 11:05</span></div>
<div class="indicator-item"><span class="indicator-label">商单预算</span><span class="budget-val">￥48,000</span></div>
<div class="indicator-item"><span class="indicator-label">报名截止日期</span><span class="indicator-val">2026/10/28 14:00:00</span></div>
<div class="indicator-item"><span class="indicator-label">交付截止日期</span><span class="indicator-val">2026/11/05 00:00:00</span></div>
<div class="indicator-item"><span class="indicator-label">当前状态</span><span class="status-text">报名中</span></div>
<section><h3>需求描述</h3><p>制作AI视频，呈现商城招商场景。</p></section>
<script type="application/ld+json">{"@type":"JobPosting","hiringOrganization":{"name":"塔猴"},"jobLocation":{"address":{"addressCountry":"CN"}}}</script>'''

def zbj_detail(title='带AR/XR效果AI视频生成服务采购', description='需要制作AI视频，具备AR和XR效果。', budget='需人才报价'):
    return f'''<div class="title-label-box"><div class="title-label-ing">进行中</div><div class="title-label-region">上海市</div>
    <div class="title-label-item-list">AI视频生成</div><div>今日发布</div></div>
    <div class="base-info-row"><div class="base-info-title">需求标题</div><div class="base-info-value">{title}</div></div>
    <div class="base-info-row"><div class="base-info-title">需求描述</div><div class="base-info-value">{description}</div></div>
    <div class="base-info-row"><div class="base-info-title">预算金额</div><div class="base-info-value">{budget}</div></div>
    <div class="detail-info-item"><div class="detail-info-title">人才所在地</div><div class="detail-info-value">全国</div></div>
    <div class="detail-info-item"><div class="detail-info-title">期望完成日期</div><div class="detail-info-value">--</div></div>
    <script type="application/ld+json">{{"pubDate":"2026-09-17T11:54:45"}}</script>'''

ZBJ_LIST=zbj_detail()+'''<div>类似需求</div><a href="https://www.zbj.com/xq/VoKHS7qbNi4ipx0m.html">AI带货短视频 ￥0 5天前发布该需求</a>
<a href="https://www.zbj.com/fw/1.html">AI视频服务商</a><a href="https://evil.example/xq/VoKHS7qbNi4ipx0m.html">AI视频 1天前发布该需求</a>'''


class MarketplaceTests(unittest.TestCase):
    def test_tahou_public_fields_and_platform_not_used_as_client(self):
        options=candidates('tahou',TAHOU_LIST)
        self.assertEqual(len(options),1)
        row=detail('tahou',options[0],TAHOU_DETAIL)
        self.assertEqual(row['budget'],'￥48,000')
        self.assertEqual(row['published_on'],'2026-10-21')
        self.assertEqual(row['deadline_at'],'2026-10-28T14:00:00+08:00')
        self.assertEqual(row['delivery_deadline'],'2026/11/05 00:00:00')
        self.assertIsNone(row['publisher']);self.assertEqual(row['region'],'MAINLAND_CLUE')

    def test_tahou_awarded_is_closed_even_if_delivery_in_future(self):
        option=candidates('tahou',TAHOU_LIST)[0]
        for label in ('已定标','工作中','已结算'):
            with self.subTest(label=label):
                row=detail('tahou',option,TAHOU_DETAIL.replace('报名中',label))
                self.assertEqual(row['source_status'],'CLOSED')
                self.assertEqual(row['source_status_text'],label)

    def test_tahou_mv_uses_explicit_video_deliverable_not_picture_fallback(self):
        option=candidates('tahou',TAHOU_LIST)[0]
        html=TAHOU_DETAIL.replace('招商宣传短视频制作','唯美歌曲MV制作').replace('制作AI视频，呈现商城招商场景。','按歌曲输出明亮温暖的氛围。')
        self.assertEqual(detail('tahou',option,html)['category'],'视频与广告')

    def test_expiration_respects_registration_hour_not_delivery_date(self):
        payload=detail('tahou',candidates('tahou',TAHOU_LIST)[0],TAHOU_DETAIL)
        now=datetime(2026,10,28,5,59,tzinfo=timezone.utc)
        row=CommissionLead(id=1,url=payload['url'],payload=payload,captured_at=now,checked_at=now)
        self.assertEqual(lead_output(row,now=now)['status'],'OPEN')
        self.assertEqual(lead_output(row,now=datetime(2026,10,28,6,tzinfo=timezone.utc))['status'],'EXPIRED')

    def test_zbj_recommendations_only_one_hop_and_absolute_canonical_links(self):
        options=candidates('zbj',ZBJ_LIST)
        self.assertEqual(len(options),2)
        self.assertEqual(options[0].url,SOURCES['zbj'][1])
        self.assertNotIn('/fw/',options[1].url)
        fetch=Mock(side_effect=[(SOURCES['zbj'][1],ZBJ_LIST.encode(),'text/html'),
            (options[1].url,zbj_detail(budget='500元').encode(),'text/html')])
        rows,report=CommissionConnector(fetch).collect_source('zbj')
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(len(rows),2);self.assertEqual(report['status'],'OK')
        self.assertIn('有限发现',report['coverage'])
        self.assertEqual(rows[1]['budget'],'500元')

    def test_zbj_uses_detail_date_price_and_demand_region_not_footer(self):
        row=detail('zbj',candidates('zbj',ZBJ_LIST)[0],zbj_detail())
        self.assertEqual(row['published_on'],'2026-09-17') # NOT the visible 今日发布.
        self.assertEqual(row['budget'],'需人才报价') # NOT recommendation-card ￥0.
        self.assertEqual(row['region_evidence'],'原帖需求地区：上海市')
        self.assertIsNone(row['deadline']);self.assertIsNone(row['publisher'])
        unknown=zbj_detail().replace('上海市','待明确').replace('"pubDate":"2026-09-17T11:54:45"','"dateUnknown":true')
        row=detail('zbj',candidates('zbj',ZBJ_LIST)[0],unknown+'<footer>上海 北京 广东</footer>')
        self.assertEqual(row['region'],'UNKNOWN');self.assertIsNone(row['published_on'])

    def test_software_requests_and_unrelated_ads_are_not_creative_commissions(self):
        option=candidates('zbj',ZBJ_LIST)[0]
        self.assertIsNone(detail('zbj',option,zbj_detail(title='AI视频软件开发',description='需要AI视频软件开发')))
        self.assertIsNone(detail('zbj',option,zbj_detail(title='海外AI短剧制作')))

    def test_blocked_and_changed_pages_are_failures_not_empty_searches(self):
        for source in ('tahou','zbj'):
            for html in ('<h1>请登录</h1>','<p>安全验证</p>'):
                with self.assertRaises(ValueError):candidates(source,html)
        self.assertEqual(candidates('tahou','<p>暂未搜索到商单</p>'),[])

    def test_new_transport_scope_does_not_allow_search_verification_or_account_endpoints(self):
        for url in ('https://www.zbj.com/xq/?k=AI','https://verify.zbj.com/index.php',
                'https://www.tahou.com/login','https://www.zbj.com/fw/1.html'):
            with self.assertRaises(ValueError):fetch_public(url)

if __name__=='__main__':unittest.main()
