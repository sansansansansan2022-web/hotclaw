---
name: hot_topic_fetch
description: |
  热点话题获取技能。从多个 RSS 源抓取热点话题，为公众号内容创作提供选题灵感。
  使用场景：
  - 获取科技/AI 相关热点话题
  - 为公众号选题提供参考
  - 追踪行业最新动态
  执行方式：python -m app.skills.hot_topic_fetch.scripts.main
---

# Hot Topic Fetch Skill

热点话题获取技能，通过聚合多个权威内容源的最新资讯，为公众号运营者提供高质量的选题候选。

## 数据源

### 中文源（国内可达）
| 源 | URL | 权重 | 标签 |
|---|-----|------|------|
| IT之家 | https://www.ithome.com.tw/rss | 0.68 | 科技、数码、硬件 |

### 英文源（需要代理）
| 源 | URL | 权重 | 标签 |
|---|-----|------|------|
| OpenAI News | https://openai.com/news/rss.xml | 0.90 | AI、LLM、产品 |
| TechCrunch AI | https://techcrunch.com/category/artificial-intelligence/feed/ | 0.76 | AI、创业、产品 |

## 执行命令

### 获取热点话题
```bash
python -m app.skills.hot_topic_fetch.scripts.main
```

### 按关键词过滤
```bash
python -m app.skills.hot_topic_fetch.scripts.main --keywords "AI 人工智能" --max-results 10
```

### 指定数据源
```bash
python -m app.skills.hot_topic_fetch.scripts.main --sources "openai_news,techcrunch_ai" --max-results 5
```

## 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--keywords` | string | - | 逗号分隔的关键词列表 |
| `--max-results` | integer | 10 | 最大返回结果数 |
| `--sources` | string | 全部 | 逗号分隔的数据源 key |
| `--timeout` | integer | 15 | 超时秒数 |

## 数据源 Key

- `ithome_rss`: IT之家
- `openai_news`: OpenAI News
- `techcrunch_ai`: TechCrunch AI

## 依赖

- Python 3.11+
- httpx（异步 HTTP 客户端）
