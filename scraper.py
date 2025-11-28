import arxiv
import json
import time
import os
import random
import requests
import sys
from datetime import datetime

# --- 配置区域 ---
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not API_KEY:
    print("❌ 错误：未检测到 DEEPSEEK_API_KEY 环境变量。")
    sys.exit(1)

DB_FILE = 'papers.json'
SEARCH_QUERY = 'cat:q-fin.ST OR cat:q-fin.PM OR cat:cs.LG OR cat:q-fin.TR OR cat:q-fin.CP'

def get_deepseek_analysis(paper):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 核心修改：加强版 Prompt，强制分点，强制双语独立
    system_prompt = """
    You are an elite Wall Street Quant Researcher (Alpha Hunter).
    Your task is to analyze academic papers for a hedge fund.
    
    CRITICAL FORMATTING RULES:
    1. Output MUST be valid JSON.
    2. 'summary_cn' and 'verdict_cn' MUST be in CHINESE.
    3. 'summary_en' and 'verdict_en' MUST be in ENGLISH.
    4. For summaries and verdicts, use bullet points starting with '•'.
    5. Each section MUST have at least 3 distinct bullet points.
    6. Be critical, concise, and professional.
    """

    user_prompt = f"""
    Analyze this paper:
    Title: {paper.title}
    Abstract: {paper.summary}

    Return JSON with this EXACT structure:
    {{
        "ai_score": (float 0-10, strict evaluation, <6 is trash),
        "translated_title": (Translate title to simplified Chinese),
        
        "summary_en": (3-5 bullet points in English. Focus on: • Model Architecture • Data used • Performance metrics.),
        "summary_cn": (3-5个中文分点。格式：• 核心模型: ... • 数据来源: ... • 主要结论: ...),
        
        "verdict_en": (3-5 bullet points in English. Focus on: • Alpha Potential • Implementation Risk • Novelty.),
        "verdict_cn": (3-5个中文分点。犀利点评：• 创新点: ... • 实盘坑: ... • 复现难度: ...),
        
        "ai_strategy": (Select ONE: "High-Freq", "Arbitrage", "Alpha-Factor", "Risk-Mgmt", "Crypto", "NLP/LLM", "Deep-Learning"),
        
        "journal_info": {{
            "name": (Predict venue e.g., 'J.Finance', 'NeurIPS', 'ICML' or 'ArXiv Preprint'),
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
        response = requests.post(url, headers=headers, json=payload, timeout=45) # 增加超时时间
        if response.status_code != 200:
             print(f"⚠️ API Error: {response.status_code} - {response.text}")
             return None
        return json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return None

def main():
    print(f"🚀 Alpha Hunter Scraper Started at {datetime.now()}")
    
    existing_papers = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                existing_papers = json.load(f)
        except:
            existing_papers = []
    
    existing_ids = {p['pdf_url'] for p in existing_papers}
    print(f"📚 Loaded {len(existing_papers)} existing papers.")

    client = arxiv.Client()
    search = arxiv.Search(
        query=SEARCH_QUERY,
        max_results=10, # 每次更新10篇，避免API超时
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    new_entries = []
    
    try:
        results = list(client.results(search))
    except Exception as e:
        print(f"❌ ArXiv Failed: {e}")
        return

    for result in results:
        if result.pdf_url in existing_ids:
            continue
            
        print(f"🔍 Analyzing: {result.title[:50]}...")
        analysis = get_deepseek_analysis(result)
        
        if not analysis:
            print("   -> Skipped (API Error)")
            continue

        paper_entry = {
            "id": result.pdf_url.split('/')[-1],
            "title": result.title,
            "pdf_url": result.pdf_url,
            "published": result.published.strftime("%Y-%m-%d"),
            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ai_score": analysis.get("ai_score", 0),
            "translated_title": analysis.get("translated_title", result.title),
            "summary_en": analysis.get("summary_en", "• Analysis pending."),
            "summary_cn": analysis.get("summary_cn", "• 分析失败或等待中。"),
            "verdict_en": analysis.get("verdict_en", "• No verdict."),
            "verdict_cn": analysis.get("verdict_cn", "• 暂无锐评。"),
            "ai_strategy": analysis.get("ai_strategy", "Other"),
            "journal_info": analysis.get("journal_info", {"name": "ArXiv", "status": "Preprint"})
        }
        
        new_entries.append(paper_entry)
        print(f"✅ Indexed! Score: {paper_entry['ai_score']}")
        time.sleep(2) 

    if new_entries:
        updated_db = new_entries + existing_papers
        updated_db = updated_db[:1500] # 限制总库大小
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_db, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved {len(new_entries)} papers.")
    else:
        print("💤 No new papers.")

if __name__ == "__main__":
    main()
