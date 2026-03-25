#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
科技与AI资讯自动抓取推送脚本
功能：从多个RSS源抓取最新科技和AI新闻，分类整理后通过Server酱推送到微信
作者：自动化部署
更新：2026-03-25 - 增加AI专项源、优化推送格式、增加分类展示
"""

import requests
import feedparser
from datetime import datetime, timedelta, timezone
import time
import os
import re
import hashlib

# ============================================================
# 配置区域
# ============================================================

# Server酱配置 - 从环境变量获取
SEND_KEY = os.environ.get("SEND_KEY", "")

if not SEND_KEY:
    print("错误: 请设置SEND_KEY环境变量")
    exit(1)

# 抓取时间范围（小时），每3小时运行一次，抓取过去4小时的新闻（留1小时重叠防遗漏）
FETCH_HOURS = 4

# 每个分类最多展示的新闻条数
MAX_NEWS_PER_CATEGORY = 10

# 总共最多展示的新闻条数
MAX_TOTAL_NEWS = 30

# ============================================================
# RSS 新闻源配置（分类管理）
# ============================================================

# 分类：AI 平台与前沿动态
AI_SOURCES = [
    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "category": "AI前沿",
        "icon": "🤖"
    },
    {
        "name": "Google AI",
        "url": "https://blog.google/technology/ai/rss/",
        "category": "AI前沿",
        "icon": "🧠"
    },
    {
        "name": "Hugging Face",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "AI前沿",
        "icon": "🤗"
    },
    {
        "name": "MIT Tech Review AI",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
        "category": "AI前沿",
        "icon": "🎓"
    },
    {
        "name": "MarkTechPost",
        "url": "https://www.marktechpost.com/feed/",
        "category": "AI前沿",
        "icon": "📝"
    },
]

# 分类：科技综合资讯
TECH_SOURCES = [
    {
        "name": "36氪",
        "url": "https://www.36kr.com/feed/",
        "category": "科技综合",
        "icon": "📱"
    },
    {
        "name": "虎嗅网",
        "url": "https://www.huxiu.com/rss.xml",
        "category": "科技综合",
        "icon": "🐯"
    },
    {
        "name": "爱范儿",
        "url": "https://www.ifanr.com/feed/",
        "category": "科技综合",
        "icon": "💡"
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "科技综合",
        "icon": "🚀"
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "科技综合",
        "icon": "⚡"
    },
    {
        "name": "Wired AI",
        "url": "https://www.wired.com/feed/tag/ai/latest/rss",
        "category": "科技综合",
        "icon": "🔌"
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "category": "科技综合",
        "icon": "🖥️"
    },
]

# 合并所有源
ALL_SOURCES = AI_SOURCES + TECH_SOURCES


# ============================================================
# 核心功能函数
# ============================================================

def clean_html(text):
    """清除HTML标签，提取纯文本"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def get_summary(entry, max_length=80):
    """从RSS条目中提取摘要，限制长度"""
    summary = ""
    # 优先使用 summary 字段
    if hasattr(entry, 'summary') and entry.summary:
        summary = clean_html(entry.summary)
    # 其次使用 description 字段
    elif hasattr(entry, 'description') and entry.description:
        summary = clean_html(entry.description)
    # 最后使用 content 字段
    elif hasattr(entry, 'content') and entry.content:
        summary = clean_html(entry.content[0].get('value', ''))

    if len(summary) > max_length:
        summary = summary[:max_length] + "..."
    return summary


def get_news_id(title, link):
    """生成新闻唯一标识，用于去重"""
    content = f"{title}_{link}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]


def parse_publish_time(entry):
    """解析发布时间，兼容多种格式"""
    # 尝试 published_parsed
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except:
            pass
    # 尝试 updated_parsed
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except:
            pass
    # 如果都没有，返回 None（后续会作为"时间未知"处理）
    return None


def get_rss_news(source, hours=FETCH_HOURS):
    """
    抓取单个RSS源的最新新闻
    参数：
        source: RSS源配置字典
        hours: 抓取过去多少小时的新闻
    返回：
        新闻列表
    """
    news_list = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }
        response = requests.get(source["url"], headers=headers, timeout=15)
        response.encoding = 'utf-8'

        feed = feedparser.parse(response.text)
        cutoff_time = datetime.now() - timedelta(hours=hours)

        for entry in feed.entries[:20]:
            published = parse_publish_time(entry)

            # 如果有时间信息，检查是否在时间范围内
            # 如果没有时间信息，也收录（可能是新发布的）
            if published and published < cutoff_time:
                continue

            title = entry.title.strip() if hasattr(entry, 'title') else "无标题"
            link = entry.link if hasattr(entry, 'link') else ""
            summary = get_summary(entry)
            time_str = published.strftime("%H:%M") if published else "最新"

            news_list.append({
                "id": get_news_id(title, link),
                "title": title,
                "link": link,
                "summary": summary,
                "source": source["name"],
                "category": source["category"],
                "icon": source["icon"],
                "time": time_str,
                "published": published,
            })

        print(f"  ✅ {source['name']}: 获取到 {len(news_list)} 条新闻")

    except Exception as e:
        print(f"  ❌ {source['name']}: 抓取失败 - {e}")

    return news_list


def deduplicate_news(news_list):
    """
    新闻去重：基于标题相似度和链接去重
    """
    seen_ids = set()
    seen_titles = set()
    unique_news = []

    for news in news_list:
        # 基于ID去重
        if news["id"] in seen_ids:
            continue
        # 基于标题去重（去除空格后比较）
        clean_title = re.sub(r'\s+', '', news["title"])
        if clean_title in seen_titles:
            continue

        seen_ids.add(news["id"])
        seen_titles.add(clean_title)
        unique_news.append(news)

    return unique_news


def format_news_message(all_news):
    """
    格式化新闻消息，生成美观的Markdown推送内容
    """
    now = datetime.now()
    # 根据时间段生成问候语
    hour = now.hour
    if 5 <= hour < 9:
        greeting = "早安"
        period = "清晨"
    elif 9 <= hour < 12:
        greeting = "上午好"
        period = "上午"
    elif 12 <= hour < 14:
        greeting = "午间"
        period = "午间"
    elif 14 <= hour < 18:
        greeting = "下午好"
        period = "下午"
    elif 18 <= hour < 22:
        greeting = "晚上好"
        period = "晚间"
    else:
        greeting = "夜间"
        period = "深夜"

    title = f"{greeting}！科技&AI资讯速递 {now.strftime('%m/%d %H:%M')}"

    # 构建推送正文
    lines = []
    lines.append(f"## {period}科技与AI资讯速递\n")
    lines.append(f"> 📅 {now.strftime('%Y年%m月%d日 %H:%M')} | 共 {len(all_news)} 条新鲜资讯\n")

    # 按分类分组
    categories = {}
    for news in all_news:
        cat = news["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(news)

    # 先展示 AI前沿，再展示 科技综合
    category_order = ["AI前沿", "科技综合"]

    for cat in category_order:
        if cat not in categories:
            continue
        cat_news = categories[cat][:MAX_NEWS_PER_CATEGORY]

        if cat == "AI前沿":
            lines.append(f"\n---\n### 🤖 AI 前沿动态\n")
        else:
            lines.append(f"\n---\n### 🌐 科技综合资讯\n")

        for i, news in enumerate(cat_news, 1):
            # 标题行：序号 + 来源标签 + 标题链接 + 时间
            lines.append(f"**{i}. [{news['title']}]({news['link']})**\n")
            # 来源和时间
            lines.append(f"> {news['icon']} {news['source']} · ⏰ {news['time']}\n")
            # 摘要（如果有的话）
            if news['summary']:
                lines.append(f"> {news['summary']}\n")
            lines.append("")

    # 底部信息
    lines.append("\n---\n")
    lines.append(f"*本次共采集 {len(ALL_SOURCES)} 个信息源 | 每3小时自动推送*\n")
    lines.append(f"*数据源：OpenAI · Google AI · Hugging Face · MIT Tech Review · MarkTechPost · 36氪 · 虎嗅 · 爱范儿 · TechCrunch · The Verge · Wired · Ars Technica*")

    desp = "\n".join(lines)
    return title, desp


def send_to_wechat(title, desp):
    """
    通过Server酱推送消息到微信
    参数：
        title: 推送标题
        desp: 推送正文（支持Markdown）
    返回：
        是否推送成功
    """
    url = f"https://sctapi.ftqq.com/{SEND_KEY}.send"

    data = {
        "text": title,
        "desp": desp,
        "channel": 9
    }

    try:
        response = requests.post(url, data=data, timeout=15)
        result = response.json()
        if result.get("code") == 0:
            print("✅ 微信推送成功!")
            return True
        else:
            print(f"❌ 推送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 推送异常: {e}")
        return False


def main():
    """主函数：抓取新闻 -> 去重整理 -> 格式化 -> 推送"""
    print("=" * 50)
    print(f"🚀 开始抓取科技与AI资讯...")
    print(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏰ 抓取范围: 过去 {FETCH_HOURS} 小时的新闻")
    print(f"📡 信息源数量: {len(ALL_SOURCES)} 个")
    print("=" * 50)

    all_news = []

    # 逐个抓取RSS源
    for source in ALL_SOURCES:
        news = get_rss_news(source)
        all_news.extend(news)
        time.sleep(0.5)  # 缩短等待时间，加快抓取速度

    # 去重
    all_news = deduplicate_news(all_news)
    print(f"\n📊 去重后共 {len(all_news)} 条资讯")

    # 按时间排序（最新的在前面）
    # 没有时间的排在最前面（假设是最新的）
    all_news.sort(key=lambda x: x["published"] or datetime.now(), reverse=True)

    # 限制总数
    all_news = all_news[:MAX_TOTAL_NEWS]

    if not all_news:
        print("⚠️ 本次未获取到最新资讯，跳过推送")
        return

    # 格式化消息
    title, desp = format_news_message(all_news)

    # 推送到微信
    print(f"\n📤 正在推送 {len(all_news)} 条资讯到微信...")
    send_to_wechat(title, desp)

    print("\n✅ 任务完成!")


if __name__ == "__main__":
    main()
