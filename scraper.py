import arxiv
import json
import time
import os
import random
import requests
import sys
from datetime import datetime

# --- 配置区域 ---
# ⚠️ GitHub 版本关键修改：
# 移除硬编码的 Key，强制从环境变量获取。
# 在 GitHub Actions 中，这会自动读取你设置的 Secrets。
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 安全检查：如果没有获取到 Key，直接终止程序
if not API_KEY:
    print("❌ 错误：未检测到 DEEPSEEK_API_KEY 环境变量。")
    print("💡 提示：")
    print("   1. 本地运行：请在终端设置环境变量，或在 .env 文件中配置。")
    print("   2. GitHub Actions：请确保在 Settings > Secrets and variables > Actions 中添加了 'DEEPSEEK_API_KEY'。")
    sys.exit(1)

DB_FILE = 'papers.json'

# ArXiv 搜索关键词 (覆盖金融工程、机器学习、加密货币)
SEARCH_QUERY = 'cat:q-fin.ST OR cat:q-fin.PM OR cat:cs.LG OR cat:q-fin.TR OR cat:q-fin.CP'

def get_deepseek_analysis(paper):
    """调用 DeepSeek API 进行深度分析 (毒舌 + 提炼)"""
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # System Prompt: 设定人设和严格的格式要求
    system_prompt = """
    You are an elite Wall Street Quant Researcher. 
    Your job is to filter ArXiv papers for a hedge fund trading desk.
    
    CRITICAL OUTPUT RULES:
    1. Output MUST be valid JSON.
    2. 'summary_cn' and 'verdict_cn' MUST be in simplified Chinese.
    3. 'summary_en' and 'verdict_en' MUST be in English.
    4. Keep content CONCISE and BULLISH/BEARISH. No academic fluff.
    """

    # User Prompt: 具体指令
    user_prompt = f"""
    Analyze this paper:
    Title: {paper.title}
    Abstract: {paper.summary}

    Return JSON with this EXACT structure:
    {{
        "ai_score": (float 0-10, be strict, <6 is trash),
        "translated_title": (Chinese translation),
        
        "summary_en": (Format as 3-5 bullet points using '• '. Focus on: 1. Core Model/Algorithm 2. Data Source 3. Key Findings. Keep it short.),
        "summary_cn": (格式为3-5个'• '开头的分点。重点提炼：1. 核心模型/算法 2. 数据来源 3. 主要结论。拒绝废话，直击要害。),
        
        "verdict_en": (3 bullet points using '• '. 1. Innovation 2. Real-world Trading Risk 3. Implementation Difficulty),
        "verdict_cn": (3个'• '开头的分点毒舌点评。1. 创新点在哪里 2. 实盘会有什么坑 3. 复现难易度),
        
        "ai_strategy": (Select ONE: "High-Freq", "Arbitrage", "Alpha-Factor", "Risk-Mgmt", "Crypto", "NLP/LLM", "Deep-Learning"),
        
        "journal_info": {{
            "name": (Predict target venue e.g. 'J.Finance', 'NeurIPS', 'ICML' or 'ArXiv Garbage'),
            "status": (Predict: 'Preprint', 'Under Review', 'Accepted')
        }}
    }}
    """

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": { "type": "json_object" },
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        # 打印状态码以便调试
        if response.status_code != 200:
             print(f"⚠️ API Error: {response.status_code} - {response.text}")
        response.raise_for_status()
        return json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"❌ DeepSeek Connection Failed: {e}")
        return None

def main():
    print(f"🚀 Alpha Hunter Scraper Started at {datetime.now()}")
    
    # 1. 读取现有数据库
    existing_papers = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                existing_papers = json.load(f)
        except:
            existing_papers = []
    
    existing_ids = {p['pdf_url'] for p in existing_papers}
    print(f"📚 Loaded {len(existing_papers)} existing papers.")

    # 2. 爬取 ArXiv
    print("📡 Fetching from ArXiv...")
    client = arxiv.Client()
    search = arxiv.Search(
        query=SEARCH_QUERY,
        max_results=10,  # 这里的数量可以根据需要调整
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    new_entries = []
    
    try:
        results = list(client.results(search))
    except Exception as e:
        print(f"❌ ArXiv Connection Failed: {e}")
        # 在 GitHub Actions 中，如果连不上 ArXiv，可能需要重试或直接失败
        return

    for result in results:
        # 跳过已存在的
        if result.pdf_url in existing_ids:
            continue
            
        print(f"🔍 Analyzing: {result.title[:50]}...")
        
        # 调用 AI
        analysis = get_deepseek_analysis(result)
        
        # 如果分析失败（可能因为网络或配额），为了不中断流程，可以选择跳过或存一个空记录
        # 这里选择跳过
        if not analysis:
            print("   -> Analysis skipped due to API error.")
            continue

        # 组装数据
        paper_entry = {
            "id": result.pdf_url.split('/')[-1], # 使用 ArXiv ID
            "title": result.title,
            "pdf_url": result.pdf_url,
            "published": result.published.strftime("%Y-%m-%d"),
            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            # AI 字段
            "ai_score": analysis.get("ai_score", 0),
            "translated_title": analysis.get("translated_title", result.title),
            "summary_en": analysis.get("summary_en", "Analysis failed."),
            "summary_cn": analysis.get("summary_cn", "分析失败。"),
            "verdict_en": analysis.get("verdict_en", "No verdict."),
            "verdict_cn": analysis.get("verdict_cn", "暂无点评。"),
            "ai_strategy": analysis.get("ai_strategy", "Other"),
            "journal_info": analysis.get("journal_info", {"name": "ArXiv", "status": "Preprint"})
        }
        
        new_entries.append(paper_entry)
        print(f"✅ Indexed! Score: {paper_entry['ai_score']}")
        
        # ⚠️ 重要：避免频繁请求触发速率限制，DeepSeek 也有 QPS 限制
        time.sleep(2) 

    # 3. 保存更新
    if new_entries:
        # 新论文放前面
        updated_db = new_entries + existing_papers
        # 保持数据库不过大，只存最近 2000 篇
        updated_db = updated_db[:2000]
        
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_db, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved {len(new_entries)} new papers. Total: {len(updated_db)}")
    else:
        print("💤 No new papers found or all analysis failed.")

if __name__ == "__main__":
    main()
