#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
科技与AI资讯自动抓取推送脚本 v3.1
功能：从21个RSS源抓取最新科技和AI新闻，英文内容自动翻译成中文，
      智能分类精选后通过Server酱推送到微信
作者：自动化部署
更新：2026-03-25 - v3.1 新增英文自动翻译
  - 所有英文新闻标题和摘要自动翻译成中文
  - 使用 Google Translate 免费接口，无需API Key
  - 翻译失败时保留原文，不影响推送
  - 其余功能与 v3.0 一致
"""

import requests
import feedparser
from datetime import datetime, timedelta, timezone
from deep_translator import GoogleTranslator
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
MAX_NEWS_PER_CATEGORY = 8

# 总共最多展示的新闻条数（避免推送过长）
MAX_TOTAL_NEWS = 20

# 网络请求重试次数
MAX_RETRIES = 2

# 网络请求超时时间（秒）
REQUEST_TIMEOUT = 15

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
    参数：
        text: 待翻译的文本
    返回：
        翻译后的中文文本（或原文）
    """
    if not text or not text.strip():
        return text

    # 如果已经是中文，直接返回
    if is_chinese(text):
        return text

    # 检查缓存
    cache_key = text[:100]  # 用前100个字符作为缓存key
    if cache_key in _translate_cache:
        return _translate_cache[cache_key]

    try:
        # 文本过长时截断（Google Translate 免费接口有长度限制）
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
    """
    翻译单条新闻的标题和摘要
    参数：
        news: 新闻字典
    返回：
        翻译后的新闻字典
    """
    # 翻译标题
    if not is_chinese(news["title"]):
        original_title = news["title"]
        news["title"] = translate_text(news["title"])
        # 如果翻译成功，保留原标题作为参考（可选）
        if news["title"] != original_title:
            print(f"    🔄 标题翻译: {original_title[:40]}... -> {news['title'][:40]}...")

    # 翻译摘要
    if news.get("summary") and not is_chinese(news["summary"]):
        news["summary"] = translate_text(news["summary"])

    return news


# ============================================================
# RSS 新闻源配置（三级分类管理）
# ============================================================

# ==========================================
# 第一类：核心AI平台（官方一手消息）
# ==========================================
AI_PLATFORM_SOURCES = [
    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "category": "核心AI平台",
        "icon": "🤖",
        "priority": 1,
        "lang": "en",  # 标记语言，用于判断是否需要翻译
    },
    {
        "name": "Anthropic",
        "url": "https://www.anthropic.com/rss.xml",
        "category": "核心AI平台",
        "icon": "🧬",
        "priority": 1,
        "lang": "en",
    },
    {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "核心AI平台",
        "icon": "🧠",
        "priority": 1,
        "lang": "en",
    },
    {
        "name": "Google AI",
        "url": "https://blog.google/technology/ai/rss/",
        "category": "核心AI平台",
        "icon": "🔍",
        "priority": 1,
        "lang": "en",
    },
    {
        "name": "NVIDIA AI",
        "url": "https://blogs.nvidia.com/feed/",
        "category": "核心AI平台",
        "icon": "💚",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "Meta AI",
        "url": "https://ai.meta.com/blog/rss/",
        "category": "核心AI平台",
        "icon": "Ⓜ️",
        "priority": 1,
        "lang": "en",
    },
    {
        "name": "Hugging Face",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "核心AI平台",
        "icon": "🤗",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "MIT Tech Review AI",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
        "category": "核心AI平台",
        "icon": "🎓",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "MarkTechPost",
        "url": "https://www.marktechpost.com/feed/",
        "category": "核心AI平台",
        "icon": "📝",
        "priority": 3,
        "lang": "en",
    },
]

# ==========================================
# 第二类：中文AI与科技核心（国内最快资讯）
# ==========================================
CN_SOURCES = [
    {
        "name": "机器之心",
        "url": "https://www.jiqizhixin.com/rss",
        "category": "中文AI与科技",
        "icon": "⚙️",
        "priority": 1,
        "lang": "zh",
    },
    {
        "name": "量子位",
        "url": "https://www.qbitai.com/feed",
        "category": "中文AI与科技",
        "icon": "⚛️",
        "priority": 1,
        "lang": "zh",
    },
    {
        "name": "36氪",
        "url": "https://www.36kr.com/feed/",
        "category": "中文AI与科技",
        "icon": "📱",
        "priority": 2,
        "lang": "zh",
    },
    {
        "name": "虎嗅网",
        "url": "https://www.huxiu.com/rss.xml",
        "category": "中文AI与科技",
        "icon": "🐯",
        "priority": 2,
        "lang": "zh",
    },
    {
        "name": "爱范儿",
        "url": "https://www.ifanr.com/feed/",
        "category": "中文AI与科技",
        "icon": "💡",
        "priority": 2,
        "lang": "zh",
    },
    {
        "name": "少数派",
        "url": "https://sspai.com/feed",
        "category": "中文AI与科技",
        "icon": "📐",
        "priority": 3,
        "lang": "zh",
    },
]

# ==========================================
# 第三类：全球科技与开发者社区
# ==========================================
GLOBAL_TECH_SOURCES = [
    {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "category": "全球科技与社区",
        "icon": "🔶",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/feed",
        "category": "全球科技与社区",
        "icon": "🏹",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "全球科技与社区",
        "icon": "🚀",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "全球科技与社区",
        "icon": "⚡",
        "priority": 2,
        "lang": "en",
    },
    {
        "name": "Wired AI",
        "url": "https://www.wired.com/feed/tag/ai/latest/rss",
        "category": "全球科技与社区",
        "icon": "🔌",
        "priority": 3,
        "lang": "en",
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "category": "全球科技与社区",
        "icon": "🖥️",
        "priority": 3,
        "lang": "en",
    },
]

# 合并所有源
ALL_SOURCES = AI_PLATFORM_SOURCES + CN_SOURCES + GLOBAL_TECH_SOURCES


# ============================================================
# 核心功能函数
# ============================================================

def clean_html(text):
    """清除HTML标签，提取纯文本"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    # 移除多余的特殊字符
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&')
    clean = clean.replace('&lt;', '<').replace('&gt;', '>')
    return clean


def get_summary(entry, max_length=100):
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
        except Exception:
            pass
    # 尝试 updated_parsed
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except Exception:
            pass
    # 如果都没有，返回 None（后续会作为"时间未知"处理）
    return None


def fetch_with_retry(url, headers, retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT):
    """
    带重试机制的网络请求
    参数：
        url: 请求地址
        headers: 请求头
        retries: 最大重试次数
        timeout: 超时时间
    返回：
        response 对象，失败返回 None
    """
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
            time.sleep(2)  # 重试前等待2秒

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

        for entry in feed.entries[:15]:  # 每个源最多取15条
            published = parse_publish_time(entry)

            # 如果有时间信息，检查是否在时间范围内
            # 如果没有时间信息，也收录（可能是新发布的）
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
            }

            news_list.append(news_item)

        print(f"  ✅ {source['name']}: 获取到 {len(news_list)} 条新闻")

    except Exception as e:
        print(f"  ❌ {source['name']}: 抓取失败 - {e}")

    return news_list


def deduplicate_news(news_list):
    """
    新闻去重：基于标题相似度和链接去重
    增强版：还会过滤标题高度相似的新闻（不同源转载同一条新闻）
    """
    seen_ids = set()
    seen_titles = set()
    unique_news = []

    for news in news_list:
        # 基于ID去重
        if news["id"] in seen_ids:
            continue

        # 基于标题去重（去除空格和标点后比较）
        clean_title = re.sub(r'[\s\W]+', '', news["title"]).lower()

        # 检查是否有高度相似的标题（前20个字符相同视为重复）
        title_key = clean_title[:20] if len(clean_title) > 20 else clean_title
        if title_key in seen_titles:
            continue

        seen_ids.add(news["id"])
        seen_titles.add(title_key)
        unique_news.append(news)

    return unique_news


def smart_select(all_news):
    """
    智能精选：根据优先级和分类进行均衡选择
    确保每个分类都有内容展示，同时优先展示高优先级的新闻
    """
    # 先按优先级排序（数字小优先级高），再按时间排序
    all_news.sort(key=lambda x: (x["priority"], -(x["published"].timestamp() if x["published"] else time.time())))

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

    # 如果总数超过限制，按优先级截断
    if len(selected) > MAX_TOTAL_NEWS:
        selected.sort(key=lambda x: (x["priority"], -(x["published"].timestamp() if x["published"] else time.time())))
        selected = selected[:MAX_TOTAL_NEWS]

    return selected


def batch_translate_news(news_list):
    """
    批量翻译新闻列表中的英文内容
    只翻译标记为英文(lang='en')的新闻源的标题和摘要
    翻译之间加入适当延迟，避免触发频率限制
    参数：
        news_list: 新闻列表
    返回：
        翻译后的新闻列表
    """
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

        # 每翻译一条，稍微等一下，避免触发 Google 频率限制
        if translated_count < en_count:
            time.sleep(0.3)

    print(f"🔄 翻译完成: 共翻译 {translated_count} 条新闻")
    return news_list


def format_news_message(all_news):
    """
    格式化新闻消息，生成美观的Markdown推送内容
    三级分类展示，清晰明了
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
    lines.append(f"> 📅 {now.strftime('%Y年%m月%d日 %H:%M')} | 共 {len(all_news)} 条精选资讯\n")

    # 按分类分组
    categories = {}
    for news in all_news:
        cat = news["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(news)

    # 分类展示顺序和标题
    category_config = {
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

    # 按预设顺序展示
    sorted_cats = sorted(categories.keys(), key=lambda x: category_config.get(x, {}).get("order", 99))

    for cat in sorted_cats:
        if cat not in categories:
            continue

        cat_news = categories[cat]
        config = category_config.get(cat, {"title": cat, "desc": "", "order": 99})

        lines.append(f"\n---\n### {config['title']}\n")
        if config["desc"]:
            lines.append(f"> 📡 来源：{config['desc']}\n")

        for i, news in enumerate(cat_news, 1):
            # 标题行：序号 + 标题链接
            lines.append(f"**{i}. [{news['title']}]({news['link']})**\n")
            # 来源和时间
            lines.append(f"> {news['icon']} {news['source']} · ⏰ {news['time']}\n")
            # 摘要（如果有的话）
            if news['summary']:
                lines.append(f"> {news['summary']}\n")
            lines.append("")

    # 底部统计信息
    lines.append("\n---\n")

    # 统计各分类数量
    stats_parts = []
    for cat in sorted_cats:
        if cat in categories:
            config = category_config.get(cat, {"title": cat})
            stats_parts.append(f"{config['title'].split(' ', 1)[-1]} {len(categories[cat])}条")

    lines.append(f"*📊 本次精选：{' | '.join(stats_parts)}*\n")
    lines.append(f"*📡 共监控 {len(ALL_SOURCES)} 个信息源 | 每3小时自动推送*\n")
    lines.append(f"*🔄 v3.1 - 英文内容已自动翻译为中文*")

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
    """主函数：抓取新闻 -> 去重整理 -> 智能精选 -> 翻译 -> 格式化 -> 推送"""
    print("=" * 60)
    print(f"🚀 科技与AI资讯抓取推送 v3.1（含英文自动翻译）")
    print(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏰ 抓取范围: 过去 {FETCH_HOURS} 小时的新闻")
    print(f"📡 信息源数量: {len(ALL_SOURCES)} 个")
    print(f"   - 核心AI平台: {len(AI_PLATFORM_SOURCES)} 个")
    print(f"   - 中文AI与科技: {len(CN_SOURCES)} 个")
    print(f"   - 全球科技与社区: {len(GLOBAL_TECH_SOURCES)} 个")
    print("=" * 60)

    all_news = []
    success_count = 0
    fail_count = 0

    # 逐个抓取RSS源
    for source in ALL_SOURCES:
        news = get_rss_news(source)
        if news:
            success_count += 1
        else:
            fail_count += 1
        all_news.extend(news)
        time.sleep(0.5)  # 适当间隔，避免请求过快

    print(f"\n📊 抓取统计: 成功 {success_count} 个源 / 失败 {fail_count} 个源")
    print(f"📊 原始新闻: {len(all_news)} 条")

    # 去重
    all_news = deduplicate_news(all_news)
    print(f"📊 去重后: {len(all_news)} 条")

    # 智能精选
    all_news = smart_select(all_news)
    print(f"📊 精选后: {len(all_news)} 条")

    if not all_news:
        print("⚠️ 本次未获取到最新资讯，跳过推送")
        return

    # 翻译英文新闻为中文
    all_news = batch_translate_news(all_news)

    # 格式化消息
    title, desp = format_news_message(all_news)

    # 推送到微信
    print(f"\n📤 正在推送 {len(all_news)} 条精选资讯到微信...")
    send_to_wechat(title, desp)

    print("\n✅ 任务完成!")


if __name__ == "__main__":
    main()
