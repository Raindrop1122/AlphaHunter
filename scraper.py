import arxiv
import json
import time
import os
from openai import OpenAI

# --- 1. 配置 DeepSeek ---
# 逻辑：优先从环境变量读取 Key (给 GitHub Actions 用)
# 如果读取不到，就使用后面这个默认值 (给你本地电脑用)
# 这样你既可以在本地直接跑，传到 GitHub 也能自动跑，不用改代码！
api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-ed58b41ea71547938569c2a7076cdc7a")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# --- 2. 搜索设置 ---
# 使用 arxiv 库抓取最新论文
arxiv_client = arxiv.Client()
search = arxiv.Search(
    query = 'cat:q-fin.ST OR cat:q-fin.PM OR cat:cs.LG',
    max_results = 10,  # 🔥 升级：每天抓取 10 篇
    sort_by = arxiv.SortCriterion.SubmittedDate
)

papers_data = []

print(f"🚀 Alpha Hunter (每日10篇版) 启动中...")
print(f"🔑 当前使用的 API Key: {api_key[:10]}******")
print("📡 正在连接 ArXiv 获取最新论文...")

# 获取搜索结果
results = list(arxiv_client.results(search))
print(f"✅ 成功获取 {len(results)} 篇论文元数据，准备开始 AI 分析...")

for i, result in enumerate(results):
    print(f"\n[{i+1}/10] 正在分析: {result.title[:50]}...")
    
    # 准备发给 AI 的提示词
    prompt = f"""
    你是华尔街顶级对冲基金的 Quant Researcher。
    请阅读这篇论文摘要，判断其对量化交易的实战价值。
    
    摘要内容：
    {result.summary}
    
    请严格按照以下 JSON 格式返回（不要 Markdown，只要纯 JSON）：
    {{
        "ai_score": (0-10分，数值类型，保留一位小数),
        "ai_verdict": (犀利的中文点评，30字以内，直击痛点),
        "ai_strategy": (适合的策略类型，如：高频/统计套利/多因子/风控/NLP情绪)
    }}
    """
    
    try:
        # 调用 DeepSeek API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个输出 JSON 格式的助手。"},
                {"role": "user", "content": prompt},
            ],
            response_format={ 'type': 'json_object' }, 
            stream=False
        )
        
        # 解析结果
        content = response.choices[0].message.content
        analysis = json.loads(content)
        
        print(f"   🧠 分析完成！")
        print(f"   👉 评分: {analysis.get('ai_score')} | 策略: {analysis.get('ai_strategy')}")
        
    except Exception as e:
        print(f"   ❌ 分析失败: {e}")
        # 失败时的保底数据
        analysis = {
            "ai_score": 0, 
            "ai_verdict": "分析超时或失败", 
            "ai_strategy": "未知"
        }

    # 整合数据
    paper_info = {
        "title": result.title,
        "summary": result.summary,
        "authors": [a.name for a in result.authors],
        "pdf_url": result.pdf_url,
        "published": str(result.published.date()),
        "ai_score": analysis.get("ai_score", 0),
        "ai_verdict": analysis.get("ai_verdict", "N/A"),
        "ai_strategy": analysis.get("ai_strategy", "N/A")
    }
    papers_data.append(paper_info)
    
    # 礼貌性停顿，避免触发 API 速率限制
    time.sleep(1)

# --- 保存结果 ---
# 确保保存为 UTF-8，防止中文乱码
with open('papers.json', 'w', encoding='utf-8') as f:
    json.dump(papers_data, f, ensure_ascii=False, indent=4)

print("\n" + "="*50)
print(f"✅ 今日任务完成！成功分析并保存 {len(papers_data)} 篇论文。")
print("📂 请去刷新你的网页查看最新情报！")