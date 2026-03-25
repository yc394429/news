# 🚀 科技与AI资讯自动推送

每3小时自动抓取全球顶尖科技和AI新闻源，整理后推送到你的微信。

## 功能特点

- **12个优质信息源**：覆盖AI前沿 + 科技综合两大类
- **每3小时自动推送**：每天6次推送，不错过任何重要新闻
- **AI专项追踪**：重点关注 OpenAI、Google AI、Hugging Face 等AI平台动态
- **智能去重**：自动过滤重复新闻，只推送新鲜内容
- **美观排版**：分类展示、带摘要、时间标签，一目了然
- **完全免费**：基于 GitHub Actions，无需服务器

## 信息源列表

### 🤖 AI 前沿动态（5个源）

| 源名称 | 说明 |
|--------|------|
| OpenAI | 官方产品和模型更新 |
| Google AI | Google AI模型和平台公告 |
| Hugging Face | 开源模型和工具实践 |
| MIT Tech Review AI | AI编辑分析和行业深度报道 |
| MarkTechPost | AI论文和新产品发布快讯 |

### 🌐 科技综合资讯（7个源）

| 源名称 | 说明 |
|--------|------|
| 36氪 | 中文科技创投新闻 |
| 虎嗅网 | 中文科技商业分析 |
| 爱范儿 | 中文消费科技资讯 |
| TechCrunch | 全球科技创业新闻 |
| The Verge | 科技产品与文化 |
| Wired AI | 连线杂志AI专栏 |
| Ars Technica | 深度科技报道 |

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
- **去重机制**：基于标题和链接的MD5哈希去重

## 常见问题

**Q: 为什么收不到微信推送？**
A: 请确认已关注 Server酱 微信公众号，并检查 SendKey 是否正确。

**Q: 可以修改推送频率吗？**
A: 可以，修改 `.github/workflows/daily_tech_news.yml` 中的 cron 表达式即可。

**Q: 如何添加更多RSS源？**
A: 修改 `fetch_news.py` 中的 `AI_SOURCES` 或 `TECH_SOURCES` 列表，按照现有格式添加即可。

**Q: 推送失败怎么办？**
A: 查看 Actions 运行日志中的错误信息，常见问题是 SendKey 无效或网络超时。

## 更新记录

- **2026-03-25**：大版本更新
  - 新增 5 个 AI 专项信息源（OpenAI、Google AI、Hugging Face、MIT Tech Review、MarkTechPost）
  - 新增 3 个科技综合信息源（The Verge、Wired AI、Ars Technica）
  - 推送频率从每天1次提升到每3小时1次（每天6次）
  - 优化推送格式：分类展示、带摘要、时间标签
  - 增加智能去重机制
  - 增加时段问候语
