# 🚀 科技与AI资讯自动推送 v3.0

每3小时自动抓取全球顶级科技与AI新闻，智能精选后推送到你的微信。

## 功能特性

- **21个顶级信息源**：覆盖全球核心AI平台、中文AI顶会、国际科技媒体和开发者社区
- **三级分类展示**：核心AI平台动态 / 中文AI与科技资讯 / 全球科技与开发者社区
- **智能精选机制**：每次推送精选20条最重要的新闻，避免信息轰炸
- **增强去重算法**：基于标题相似度和链接双重去重，杜绝重复内容
- **网络请求重试**：自动重试失败的请求，提高抓取稳定性
- **每3小时推送**：北京时间 07:00 / 10:00 / 13:00 / 16:00 / 19:00 / 22:00
- **完全免费**：基于 GitHub Actions，无需服务器

## 信息源列表（21个）

### 🤖 核心AI平台（9个）

| 来源 | 说明 |
|------|------|
| OpenAI | GPT系列模型官方动态 |
| Anthropic | Claude系列模型官方动态 |
| Google DeepMind | Gemini等前沿AI研究 |
| Google AI | Google AI技术博客 |
| NVIDIA AI | GPU算力与AI基础设施 |
| Meta AI | Llama开源模型动态 |
| Hugging Face | 开源AI模型社区 |
| MIT Tech Review AI | MIT科技评论AI专栏 |
| MarkTechPost | AI技术深度解读 |

### 🇨🇳 中文AI与科技（6个）

| 来源 | 说明 |
|------|------|
| 机器之心 | 中文AI三大顶会之一，深度报道 |
| 量子位 | 中文AI三大顶会之一，前沿追踪 |
| 36氪 | 国内科技创投第一媒体 |
| 虎嗅网 | 深度商业科技分析 |
| 爱范儿 | 消费科技与数码产品 |
| 少数派 | 效率工具与科技生活 |

### 🌍 全球科技与开发者社区（6个）

| 来源 | 说明 |
|------|------|
| Hacker News | 全球极客最关注的科技榜单 |
| Product Hunt | 每天最新发布的科技产品 |
| TechCrunch | 全球科技创业权威媒体 |
| The Verge | 科技与文化深度报道 |
| Wired AI | 连线杂志AI专栏 |
| Ars Technica | 硬核技术分析 |

## 推送时间表

| 推送时段 | 北京时间 | 说明 |
|---------|---------|------|
| 早间推送 | 07:00 | 开始新的一天 |
| 上午推送 | 10:00 | 工作间隙 |
| 午间推送 | 13:00 | 午休时间 |
| 下午推送 | 16:00 | 下午茶时间 |
| 晚间推送 | 19:00 | 下班路上 |
| 夜间推送 | 22:00 | 睡前浏览 |

## 快速部署

### 第一步：获取 Server酱 SendKey

1. 打开 [Server酱官网](https://sct.ftqq.com/)
2. 用微信扫码登录
3. 复制你的 SendKey（`SCT` 开头的字符串）

### 第二步：Fork 本项目

点击页面右上角的 `Fork` 按钮，将项目复制到你的账号下。

### 第三步：配置密钥

1. 进入你 Fork 后的仓库
2. 点击 `Settings` → `Secrets and variables` → `Actions`
3. 点击 `New repository secret`
4. Name 填 `SEND_KEY`，Value 填你的 SendKey
5. 点击 `Add secret`

### 第四步：启用 Actions

1. 点击仓库的 `Actions` 标签
2. 点击 `I understand my workflows, go ahead and enable them`
3. 在左侧点击工作流名称，点击 `Enable workflow`

### 第五步：手动测试

1. 在 Actions 页面点击 `Run workflow`
2. 检查微信是否收到推送

## 文件说明

```
news/
├── fetch_news.py              # Python 抓取推送脚本（核心）
├── requirements.txt           # Python 依赖
├── README.md                  # 说明文档
└── .github/workflows/
    └── daily_tech_news.yml   # GitHub Actions 工作流配置
```

## 本地运行（可选）

如果你想在本地测试脚本：

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/news.git
cd news

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置环境变量（Linux/Mac）
export SEND_KEY="你的SendKey"

# 4. 运行脚本
python fetch_news.py
```

Windows 用户使用：
```cmd
set SEND_KEY=你的SendKey
python fetch_news.py
```

## 技术说明

- **运行环境**：GitHub Actions (Ubuntu + Python 3.11)
- **依赖库**：requests, feedparser
- **推送通道**：Server酱（微信推送）
- **抓取策略**：每次抓取过去4小时的新闻（留1小时重叠防遗漏）
- **去重机制**：基于标题相似度 + 链接MD5哈希双重去重
- **精选机制**：按优先级和时间智能排序，每次最多推送20条

## 常见问题

**Q: 为什么收不到微信推送？**
A: 请确认已关注 Server酱 微信公众号，并检查 SendKey 是否正确。

**Q: 可以修改推送频率吗？**
A: 可以，修改 `.github/workflows/daily_tech_news.yml` 中的 cron 表达式即可。

**Q: 如何添加更多RSS源？**
A: 修改 `fetch_news.py` 中的 `AI_PLATFORM_SOURCES`、`CN_SOURCES` 或 `GLOBAL_TECH_SOURCES` 列表，按照现有格式添加即可。

**Q: 推送失败怎么办？**
A: 查看 Actions 运行日志中的错误信息，常见问题是 SendKey 无效或网络超时。脚本已内置自动重试机制。

## 更新记录

- **v3.0** (2026-03-25)：重大升级
  - 数据源从12个扩充到21个
  - 新增 Anthropic、Google DeepMind、NVIDIA AI、Meta AI 等核心AI平台官方源
  - 新增机器之心、量子位等中文AI三大顶会
  - 新增 Hacker News、Product Hunt 等开发者社区
  - 三级分类展示：核心AI平台 / 中文AI与科技 / 全球科技与社区
  - 智能精选机制，每次最多推送20条精选
  - 增强去重算法（标题相似度 + 链接去重）
  - 网络请求自动重试机制
- **v2.0** (2026-03-25)：数据源从4个扩充到12个，增加AI源，优化格式
- **v1.0**：初始版本，4个基础科技RSS源
