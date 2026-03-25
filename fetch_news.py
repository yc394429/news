#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
科技与AI资讯自动抓取推送脚本 v4.0
功能：
  1. 从21个RSS源抓取最新科技和AI新闻
  2. 英文内容自动翻译成中文
  3. 关键词智能过滤，优先推送你关心的内容
  4. GitHub Trending AI 项目推送
  5. 每日精华汇总（TOP10回顾）
作者：自动化部署
更新：2026-03-25 - v4.0 三大功能升级
  - 新增关键词过滤：优先推送包含关键词的新闻
  - 新增 GitHub Trending AI 项目抓取
  - 新增每日精华汇总模式（通过 --daily-digest 参数触发）
  - 支持命令行参数切换普通推送/每日精华两种模式
"""

import requests
import feedparser
from datetime import datetime, timedelta, timezone
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup
import time
import os
import re
import sys
import hashlib
import json

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

# 每日精华模式的抓取范围（小时）
DAILY_DIGEST_HOURS = 24

# 每个分类最多展示的新闻条数
MAX_NEWS_PER_CATEGORY = 8

# 总共最多展示的新闻条数（避免推送过长）
MAX_TOTAL_NEWS = 20

# 每日精华最多展示条数
MAX_DAILY_DIGEST = 10

# GitHub Trending 最多展示条数
MAX_TRENDING = 5

# 网络请求重试次数
MAX_RETRIES = 2

# 网络请求超时时间（秒）
REQUEST_TIMEOUT = 15

# ============================================================
# 关键词过滤配置
# ============================================================

# 高优先级关键词：包含这些词的新闻会被优先展示（权重+5）
# 你可以根据自己的兴趣随时修改这个列表
HIGH_PRIORITY_KEYWORDS = [
    # AI 大模型相关
    "GPT", "gpt", "大模型", "LLM", "llm", "大语言模型",
    "Claude", "claude", "Gemini", "gemini",
    "Llama", "llama", "开源模型",
    # AI 平台与产品
    "ChatGPT", "chatgpt", "Copilot", "copilot",
    "Midjourney", "midjourney", "Sora", "sora",
    "DALL-E", "Stable Diffusion", "文生图", "文生视频",
    # AI 核心技术
    "AGI", "agi", "通用人工智能",
    "多模态", "multimodal", "RAG", "rag",
    "Agent", "agent", "智能体",
    "微调", "fine-tune", "fine-tuning",
    "推理", "reasoning", "思维链",
    # AI 行业动态
    "融资", "收购", "开源", "发布", "上线",
    "突破", "里程碑", "首次",
]

# 低优先级关键词（黑名单）：包含这些词的新闻会被降权
# 用于过滤广告、软文等低质量内容
BLACKLIST_KEYWORDS = [
    "广告", "推广", "优惠券", "折扣", "限时",
    "抽奖", "福利", "赞助", "sponsored",
]


def calculate_keyword_score(news):
    """
    根据关键词计算新闻的优先级得分
    得分越高，排名越靠前
    参数：
        news: 新闻字典
    返回：
        额外得分（正数=加分，负数=减分）
    """
    text = f"{news['title']} {news.get('summary', '')}"
    score = 0

    # 检查高优先级关键词
    for keyword in HIGH_PRIORITY_KEYWORDS:
        if keyword in text:
            score += 5
            break  # 命中一个就够了，避免重复加分

    # 检查黑名单关键词
    for keyword in BLACKLIST_KEYWORDS:
        if keyword in text:
            score -= 10
            break

    return score


# ============================================================
# 翻译功能
# ============================================================

# 初始化 Google 翻译器（英文 -> 中文）
translator = GoogleTranslator(source='en', target='zh-CN')

# 翻译缓存，避免重复翻译相同内容
_translate_cache = {}


def is_chinese(text):
    """
    判断文本是否主要是中文
    如果中文字符占比超过30%，就认为是中文内容，不需要翻译
    """
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return True
    return (chinese_chars / total_chars) > 0.3


def translate_text(text):
    """
    将英文文本翻译成中文
    - 如果文本已经是中文，直接返回
    - 翻译失败时返回原文，不会报错
    - 使用缓存避免重复翻译
    """
    if not text or not text.strip():
        return text
    if is_chinese(text):
        return text

    cache_key = text[:100]
    if cache_key in _translate_cache:
        return _translate_cache[cache_key]

    try:
        text_to_translate = text[:500] if len(text) > 500 else text
        translated = translator.translate(text_to_translate)
        if translated and translated.strip():
            _translate_cache[cache_key] = translated
            return translated
        else:
            return text
    except Exception as e:
        print(f"    ⚠️ 翻译失败: {str(e)[:50]}，保留原文")
        return text


def translate_news_item(news):
    """翻译单条新闻的标题和摘要"""
    if not is_chinese(news["title"]):
        original_title = news["title"]
        news["title"] = translate_text(news["title"])
        if news["title"] != original_title:
            print(f"    🔄 标题翻译: {original_title[:40]}... -> {news['title'][:40]}...")

    if news.get("summary") and not is_chinese(news["summary"]):
        news["summary"] = translate_text(news["summary"])

    return news


# ============================================================
# RSS 新闻源配置（三级分类管理）
# ============================================================

AI_PLATFORM_SOURCES = [
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "category": "核心AI平台", "icon": "🤖", "priority": 1, "lang": "en"},
    {"name": "Anthropic", "url": "https://www.anthropic.com/rss.xml", "category": "核心AI平台", "icon": "🧬", "priority": 1, "lang": "en"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "category": "核心AI平台", "icon": "🧠", "priority": 1, "lang": "en"},
    {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/", "category": "核心AI平台", "icon": "🔍", "priority": 1, "lang": "en"},
    {"name": "NVIDIA AI", "url": "https://blogs.nvidia.com/feed/", "category": "核心AI平台", "icon": "💚", "priority": 2, "lang": "en"},
    {"name": "Meta AI", "url": "https://ai.meta.com/blog/rss/", "category": "核心AI平台", "icon": "Ⓜ️", "priority": 1, "lang": "en"},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "category": "核心AI平台", "icon": "🤗", "priority": 2, "lang": "en"},
    {"name": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/", "category": "核心AI平台", "icon": "🎓", "priority": 2, "lang": "en"},
    {"name": "MarkTechPost", "url": "https://www.marktechpost.com/feed/", "category": "核心AI平台", "icon": "📝", "priority": 3, "lang": "en"},
]

CN_SOURCES = [
    {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss", "category": "中文AI与科技", "icon": "⚙️", "priority": 1, "lang": "zh"},
    {"name": "量子位", "url": "https://www.qbitai.com/feed", "category": "中文AI与科技", "icon": "⚛️", "priority": 1, "lang": "zh"},
    {"name": "36氪", "url": "https://www.36kr.com/feed/", "category": "中文AI与科技", "icon": "📱", "priority": 2, "lang": "zh"},
    {"name": "虎嗅网", "url": "https://www.huxiu.com/rss.xml", "category": "中文AI与科技", "icon": "🐯", "priority": 2, "lang": "zh"},
    {"name": "爱范儿", "url": "https://www.ifanr.com/feed/", "category": "中文AI与科技", "icon": "💡", "priority": 2, "lang": "zh"},
    {"name": "少数派", "url": "https://sspai.com/feed", "category": "中文AI与科技", "icon": "📐", "priority": 3, "lang": "zh"},
]

GLOBAL_TECH_SOURCES = [
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "category": "全球科技与社区", "icon": "🔶", "priority": 2, "lang": "en"},
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "category": "全球科技与社区", "icon": "🏹", "priority": 2, "lang": "en"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "全球科技与社区", "icon": "🚀", "priority": 2, "lang": "en"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "全球科技与社区", "icon": "⚡", "priority": 2, "lang": "en"},
    {"name": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss", "category": "全球科技与社区", "icon": "🔌", "priority": 3, "lang": "en"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "全球科技与社区", "icon": "🖥️", "priority": 3, "lang": "en"},
]

ALL_SOURCES = AI_PLATFORM_SOURCES + CN_SOURCES + GLOBAL_TECH_SOURCES


# ============================================================
# GitHub Trending AI 项目抓取
# ============================================================

def fetch_github_trending():
    """
    抓取 GitHub Trending 中与 AI/ML 相关的热门项目
    通过解析 GitHub Trending 页面获取数据
    返回：
        trending 项目列表
    """
    print("\n🔥 正在抓取 GitHub Trending AI 项目...")
    trending_list = []

    # AI 相关的 Trending 页面（按今日星标排序）
    urls = [
        "https://github.com/trending/python?since=daily",
        "https://github.com/trending?since=daily",
    ]

    # AI 相关关键词，用于过滤非AI项目
    ai_keywords = [
        "ai", "ml", "llm", "gpt", "transformer", "neural", "deep-learning",
        "machine-learning", "nlp", "diffusion", "agent", "chatbot", "model",
        "inference", "training", "embedding", "vector", "rag", "fine-tun",
        "language-model", "generative", "multimodal", "vision", "speech",
        "openai", "anthropic", "huggingface", "langchain", "llamaindex",
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    seen_repos = set()

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                print(f"  ⚠️ GitHub Trending 请求失败: HTTP {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.select('article.Box-row')

            for article in articles:
                try:
                    # 获取仓库名称
                    h2 = article.select_one('h2 a')
                    if not h2:
                        continue
                    repo_name = h2.get_text(strip=True).replace('\n', '').replace(' ', '')
                    repo_name = re.sub(r'\s+', '', repo_name)

                    if repo_name in seen_repos:
                        continue

                    # 获取仓库链接
                    repo_link = "https://github.com" + h2.get('href', '')

                    # 获取描述
                    desc_tag = article.select_one('p')
                    description = desc_tag.get_text(strip=True) if desc_tag else ""

                    # 获取语言
                    lang_tag = article.select_one('[itemprop="programmingLanguage"]')
                    language = lang_tag.get_text(strip=True) if lang_tag else ""

                    # 获取今日星标数
                    stars_today_tag = article.select_one('span.d-inline-block.float-sm-right')
                    stars_today = stars_today_tag.get_text(strip=True) if stars_today_tag else ""

                    # 获取总星标数
                    star_links = article.select('a.Link--muted.d-inline-block.mr-3')
                    total_stars = star_links[0].get_text(strip=True) if star_links else ""

                    # 判断是否与AI相关（通过仓库名和描述判断）
                    check_text = f"{repo_name} {description}".lower()
                    is_ai_related = any(kw in check_text for kw in ai_keywords)

                    if is_ai_related:
                        seen_repos.add(repo_name)
                        trending_list.append({
                            "name": repo_name,
                            "link": repo_link,
                            "description": description,
                            "language": language,
                            "stars_today": stars_today,
                            "total_stars": total_stars,
                        })

                except Exception as e:
                    continue

            time.sleep(1)  # 请求间隔

        except Exception as e:
            print(f"  ❌ GitHub Trending 抓取失败: {e}")

    # 只取前 MAX_TRENDING 个
    trending_list = trending_list[:MAX_TRENDING]

    # 翻译描述
    for item in trending_list:
        if item["description"] and not is_chinese(item["description"]):
            item["description"] = translate_text(item["description"])

    print(f"  ✅ GitHub Trending: 获取到 {len(trending_list)} 个AI相关项目")
    return trending_list


# ============================================================
# 核心功能函数
# ============================================================

def clean_html(text):
    """清除HTML标签，提取纯文本"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&')
    clean = clean.replace('&lt;', '<').replace('&gt;', '>')
    return clean


def get_summary(entry, max_length=100):
    """从RSS条目中提取摘要，限制长度"""
    summary = ""
    if hasattr(entry, 'summary') and entry.summary:
        summary = clean_html(entry.summary)
    elif hasattr(entry, 'description') and entry.description:
        summary = clean_html(entry.description)
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
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except Exception:
            pass
    return None


def fetch_with_retry(url, headers, retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT):
    """带重试机制的网络请求"""
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response
            else:
                print(f"    ⚠️ HTTP {response.status_code}，第{attempt+1}次尝试")
        except requests.exceptions.Timeout:
            print(f"    ⚠️ 请求超时，第{attempt+1}次尝试")
        except requests.exceptions.ConnectionError:
            print(f"    ⚠️ 连接失败，第{attempt+1}次尝试")
        except Exception as e:
            print(f"    ⚠️ 请求异常: {e}，第{attempt+1}次尝试")

        if attempt < retries:
            time.sleep(2)

    return None


def get_rss_news(source, hours=FETCH_HOURS):
    """抓取单个RSS源的最新新闻"""
    news_list = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }

        response = fetch_with_retry(source["url"], headers)
        if not response:
            print(f"  ❌ {source['name']}: 所有重试均失败，跳过")
            return news_list

        feed = feedparser.parse(response.text)
        cutoff_time = datetime.now() - timedelta(hours=hours)

        for entry in feed.entries[:15]:
            published = parse_publish_time(entry)
            if published and published < cutoff_time:
                continue

            title = entry.title.strip() if hasattr(entry, 'title') else "无标题"
            link = entry.link if hasattr(entry, 'link') else ""
            summary = get_summary(entry)
            time_str = published.strftime("%H:%M") if published else "最新"

            news_item = {
                "id": get_news_id(title, link),
                "title": title,
                "link": link,
                "summary": summary,
                "source": source["name"],
                "category": source["category"],
                "icon": source["icon"],
                "priority": source["priority"],
                "time": time_str,
                "published": published,
                "lang": source.get("lang", "en"),
                "keyword_score": 0,  # 关键词得分，后续计算
            }

            news_list.append(news_item)

        print(f"  ✅ {source['name']}: 获取到 {len(news_list)} 条新闻")

    except Exception as e:
        print(f"  ❌ {source['name']}: 抓取失败 - {e}")

    return news_list


def deduplicate_news(news_list):
    """新闻去重：基于标题相似度和链接去重"""
    seen_ids = set()
    seen_titles = set()
    unique_news = []

    for news in news_list:
        if news["id"] in seen_ids:
            continue

        clean_title = re.sub(r'[\s\W]+', '', news["title"]).lower()
        title_key = clean_title[:20] if len(clean_title) > 20 else clean_title
        if title_key in seen_titles:
            continue

        seen_ids.add(news["id"])
        seen_titles.add(title_key)
        unique_news.append(news)

    return unique_news


def apply_keyword_filter(news_list):
    """
    应用关键词过滤：为每条新闻计算关键词得分
    得分高的新闻会在后续排序中获得更高优先级
    """
    print("\n🔍 正在进行关键词智能过滤...")
    high_priority_count = 0
    filtered_count = 0

    for news in news_list:
        score = calculate_keyword_score(news)
        news["keyword_score"] = score
        if score > 0:
            high_priority_count += 1
        elif score < 0:
            filtered_count += 1

    print(f"  📊 关键词匹配: {high_priority_count} 条高优先级 / {filtered_count} 条被降权")

    # 过滤掉黑名单命中的新闻（得分 < -5 的直接移除）
    news_list = [n for n in news_list if n["keyword_score"] > -5]

    return news_list


def smart_select(all_news, max_total=MAX_TOTAL_NEWS):
    """
    智能精选：综合优先级、关键词得分、分类进行均衡选择
    v4.0 升级：加入关键词得分权重
    """
    # 综合排序：关键词得分（越高越好）> 源优先级（越小越好）> 时间（越新越好）
    all_news.sort(key=lambda x: (
        -x.get("keyword_score", 0),  # 关键词得分高的优先
        x["priority"],  # 源优先级
        -(x["published"].timestamp() if x["published"] else time.time())  # 时间新的优先
    ))

    # 按分类分组
    categories = {}
    for news in all_news:
        cat = news["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(news)

    # 每个分类最多取 MAX_NEWS_PER_CATEGORY 条
    selected = []
    for cat, news_list in categories.items():
        selected.extend(news_list[:MAX_NEWS_PER_CATEGORY])

    # 如果总数超过限制，按综合得分截断
    if len(selected) > max_total:
        selected.sort(key=lambda x: (
            -x.get("keyword_score", 0),
            x["priority"],
            -(x["published"].timestamp() if x["published"] else time.time())
        ))
        selected = selected[:max_total]

    return selected


def batch_translate_news(news_list):
    """批量翻译新闻列表中的英文内容"""
    en_count = sum(1 for n in news_list if n.get("lang") == "en")
    if en_count == 0:
        print("📝 本次推送全部为中文内容，无需翻译")
        return news_list

    print(f"\n🔄 开始翻译 {en_count} 条英文新闻...")
    translated_count = 0

    for news in news_list:
        if news.get("lang") != "en":
            continue
        news = translate_news_item(news)
        translated_count += 1
        if translated_count < en_count:
            time.sleep(0.3)

    print(f"🔄 翻译完成: 共翻译 {translated_count} 条新闻")
    return news_list


# ============================================================
# 消息格式化
# ============================================================

# 分类展示配置
CATEGORY_CONFIG = {
    "核心AI平台": {
        "title": "🤖 核心AI平台动态",
        "desc": "OpenAI · Anthropic · DeepMind · Google AI · NVIDIA · Meta AI · Hugging Face",
        "order": 1,
    },
    "中文AI与科技": {
        "title": "🇨🇳 中文AI与科技资讯",
        "desc": "机器之心 · 量子位 · 36氪 · 虎嗅 · 爱范儿 · 少数派",
        "order": 2,
    },
    "全球科技与社区": {
        "title": "🌍 全球科技与开发者社区",
        "desc": "Hacker News · Product Hunt · TechCrunch · The Verge · Wired · Ars Technica",
        "order": 3,
    },
}


def get_greeting():
    """根据当前时间生成问候语"""
    hour = datetime.now().hour
    if 5 <= hour < 9:
        return "早安", "清晨"
    elif 9 <= hour < 12:
        return "上午好", "上午"
    elif 12 <= hour < 14:
        return "午间", "午间"
    elif 14 <= hour < 18:
        return "下午好", "下午"
    elif 18 <= hour < 22:
        return "晚上好", "晚间"
    else:
        return "夜间", "深夜"


def format_news_section(news_list):
    """格式化新闻列表为分类展示的Markdown"""
    lines = []

    # 按分类分组
    categories = {}
    for news in news_list:
        cat = news["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(news)

    sorted_cats = sorted(categories.keys(), key=lambda x: CATEGORY_CONFIG.get(x, {}).get("order", 99))

    for cat in sorted_cats:
        if cat not in categories:
            continue

        cat_news = categories[cat]
        config = CATEGORY_CONFIG.get(cat, {"title": cat, "desc": "", "order": 99})

        lines.append(f"\n---\n### {config['title']}\n")
        if config["desc"]:
            lines.append(f"> 📡 来源：{config['desc']}\n")

        for i, news in enumerate(cat_news, 1):
            # 关键词命中标记
            hot_tag = " 🔥" if news.get("keyword_score", 0) > 0 else ""
            lines.append(f"**{i}. [{news['title']}]({news['link']})**{hot_tag}\n")
            lines.append(f"> {news['icon']} {news['source']} · ⏰ {news['time']}\n")
            if news['summary']:
                lines.append(f"> {news['summary']}\n")
            lines.append("")

    return "\n".join(lines)


def format_trending_section(trending_list):
    """格式化 GitHub Trending 为 Markdown"""
    if not trending_list:
        return ""

    lines = []
    lines.append(f"\n---\n### 🔥 GitHub Trending AI 热门项目\n")
    lines.append(f"> 📡 今日最受关注的AI开源项目\n")

    for i, item in enumerate(trending_list, 1):
        lines.append(f"**{i}. [{item['name']}]({item['link']})**\n")
        meta_parts = []
        if item["language"]:
            meta_parts.append(f"💻 {item['language']}")
        if item["total_stars"]:
            meta_parts.append(f"⭐ {item['total_stars']}")
        if item["stars_today"]:
            meta_parts.append(f"📈 {item['stars_today']}")
        if meta_parts:
            lines.append(f"> {' · '.join(meta_parts)}\n")
        if item["description"]:
            lines.append(f"> {item['description']}\n")
        lines.append("")

    return "\n".join(lines)


def format_regular_message(all_news, trending_list):
    """
    格式化常规推送消息（每3小时推送一次）
    包含：新闻分类 + GitHub Trending
    """
    now = datetime.now()
    greeting, period = get_greeting()

    title = f"{greeting}！科技&AI资讯速递 {now.strftime('%m/%d %H:%M')}"

    lines = []
    lines.append(f"## {period}科技与AI资讯速递\n")
    lines.append(f"> 📅 {now.strftime('%Y年%m月%d日 %H:%M')} | 共 {len(all_news)} 条精选资讯\n")

    # 新闻分类展示
    lines.append(format_news_section(all_news))

    # GitHub Trending
    lines.append(format_trending_section(trending_list))

    # 底部统计
    lines.append("\n---\n")

    # 统计各分类数量
    categories = {}
    for news in all_news:
        cat = news["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    stats_parts = []
    for cat in sorted(categories.keys(), key=lambda x: CATEGORY_CONFIG.get(x, {}).get("order", 99)):
        config = CATEGORY_CONFIG.get(cat, {"title": cat})
        stats_parts.append(f"{config['title'].split(' ', 1)[-1]} {categories[cat]}条")

    if trending_list:
        stats_parts.append(f"GitHub热门 {len(trending_list)}个")

    # 关键词命中统计
    keyword_hits = sum(1 for n in all_news if n.get("keyword_score", 0) > 0)
    if keyword_hits > 0:
        lines.append(f"*🔍 关键词匹配: {keyword_hits} 条与你关注的AI话题相关*\n")

    stats_text = ' | '.join(stats_parts)
    lines.append(f"*📊 本次精选：{stats_text}*\n")
    lines.append(f"*📡 共监控 {len(ALL_SOURCES)} 个信息源 | 每3小时自动推送*\n")
    lines.append(f"*🔄 v4.0 - 关键词过滤 · GitHub Trending · 每日精华*")

    desp = "\n".join(lines)
    return title, desp


def format_daily_digest(all_news, trending_list):
    """
    格式化每日精华汇总消息（每天晚上21:00推送一次）
    从过去24小时的新闻中精选 TOP10
    """
    now = datetime.now()

    title = f"📋 今日AI与科技精华 TOP10 | {now.strftime('%m/%d')}"

    lines = []
    lines.append(f"## 📋 今日科技与AI精华 TOP10\n")
    lines.append(f"> 📅 {now.strftime('%Y年%m月%d日')} 每日回顾 | 过去24小时最值得关注的资讯\n")

    # TOP10 新闻（不分类，按综合得分排序）
    lines.append(f"\n---\n### 🏆 今日 TOP10 必读资讯\n")

    for i, news in enumerate(all_news[:MAX_DAILY_DIGEST], 1):
        # 排名标记
        if i <= 3:
            rank_icon = ["🥇", "🥈", "🥉"][i-1]
        else:
            rank_icon = f"**{i}.**"

        hot_tag = " 🔥" if news.get("keyword_score", 0) > 0 else ""
        lines.append(f"{rank_icon} [{news['title']}]({news['link']}){hot_tag}\n")
        lines.append(f"> {news['icon']} {news['source']} · ⏰ {news['time']}\n")
        if news['summary']:
            lines.append(f"> {news['summary']}\n")
        lines.append("")

    # GitHub Trending
    if trending_list:
        lines.append(format_trending_section(trending_list))

    # 今日统计
    lines.append("\n---\n")

    # 统计各分类数量
    categories = {}
    for news in all_news:
        cat = news["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    stats_parts = []
    for cat in sorted(categories.keys(), key=lambda x: CATEGORY_CONFIG.get(x, {}).get("order", 99)):
        config = CATEGORY_CONFIG.get(cat, {"title": cat})
        stats_parts.append(f"{config['title'].split(' ', 1)[-1]} {categories[cat]}条")

    keyword_hits = sum(1 for n in all_news if n.get("keyword_score", 0) > 0)

    lines.append(f"*📊 今日总览：{' | '.join(stats_parts)}*\n")
    if keyword_hits > 0:
        lines.append(f"*🔍 其中 {keyword_hits} 条与你关注的AI话题高度相关*\n")
    lines.append(f"*📡 共监控 {len(ALL_SOURCES)} 个信息源*\n")
    lines.append(f"*🔄 v4.0 - 每日精华汇总 · 明天见！*")

    desp = "\n".join(lines)
    return title, desp


# ============================================================
# 推送功能
# ============================================================

def send_to_wechat(title, desp):
    """通过Server酱推送消息到微信"""
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


# ============================================================
# 主函数
# ============================================================

def main():
    """
    主函数，支持两种运行模式：
    1. 普通模式（默认）：每3小时推送一次最新资讯
    2. 每日精华模式（--daily-digest）：每天晚上推送 TOP10 精华
    """
    # 检查运行模式
    is_daily_digest = "--daily-digest" in sys.argv

    if is_daily_digest:
        mode_name = "每日精华汇总"
        fetch_hours = DAILY_DIGEST_HOURS
    else:
        mode_name = "常规推送"
        fetch_hours = FETCH_HOURS

    print("=" * 60)
    print(f"🚀 科技与AI资讯抓取推送 v4.0")
    print(f"📋 运行模式: {mode_name}")
    print(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏰ 抓取范围: 过去 {fetch_hours} 小时的新闻")
    print(f"📡 信息源数量: {len(ALL_SOURCES)} 个")
    print(f"🔍 关键词过滤: 已启用（{len(HIGH_PRIORITY_KEYWORDS)} 个高优先级词）")
    print("=" * 60)

    all_news = []
    success_count = 0
    fail_count = 0

    # 逐个抓取RSS源
    for source in ALL_SOURCES:
        news = get_rss_news(source, hours=fetch_hours)
        if news:
            success_count += 1
        else:
            fail_count += 1
        all_news.extend(news)
        time.sleep(0.5)

    print(f"\n📊 抓取统计: 成功 {success_count} 个源 / 失败 {fail_count} 个源")
    print(f"📊 原始新闻: {len(all_news)} 条")

    # 去重
    all_news = deduplicate_news(all_news)
    print(f"📊 去重后: {len(all_news)} 条")

    # 关键词过滤
    all_news = apply_keyword_filter(all_news)
    print(f"📊 过滤后: {len(all_news)} 条")

    # 智能精选
    if is_daily_digest:
        all_news = smart_select(all_news, max_total=MAX_DAILY_DIGEST)
    else:
        all_news = smart_select(all_news, max_total=MAX_TOTAL_NEWS)
    print(f"📊 精选后: {len(all_news)} 条")

    if not all_news:
        print("⚠️ 本次未获取到最新资讯，跳过推送")
        return

    # 翻译英文新闻为中文
    all_news = batch_translate_news(all_news)

    # 抓取 GitHub Trending
    trending_list = fetch_github_trending()

    # 格式化消息
    if is_daily_digest:
        title, desp = format_daily_digest(all_news, trending_list)
    else:
        title, desp = format_regular_message(all_news, trending_list)

    # 推送到微信
    print(f"\n📤 正在推送 [{mode_name}] 到微信...")
    send_to_wechat(title, desp)

    print("\n✅ 任务完成!")


if __name__ == "__main__":
    main()
