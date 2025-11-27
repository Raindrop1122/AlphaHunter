import arxiv
import json
import time
import os
from openai import OpenAI

# --- 1. 配置 DeepSeek (安全模式) ---
# 关键修改：不再直接写 "sk-..."，而是让代码去读取环境变量
# GitHub Actions 会自动把保险箱里的 Key 填进来
api_key = os.environ.get("DEEPSEEK_API_KEY")

# 本地测试逻辑（防止你本地跑不通）：
if not api_key:
    # 如果没读到环境变量，说明你可能在本地电脑运行
    # 你可以在这里临时填入 Key 进行测试，但【千万别提交】到 GitHub！
    # 建议的方式是：在本地电脑也配置一个环境变量，或者测试时手动填一下，测完删掉
    print("⚠️ 警告：未检测到环境变量 DEEPSEEK_API_KEY")
    print("💻 如果你在本地运行，请手动配置环境变量，或临时在代码里填入Key测试（测完记得删掉！）")
    # api_key = "sk-你的新Key" # <--- 本地测试时可以把这行取消注释，但千万别上传！
    
    # 为了防止程序直接崩坏，给个空字符串，虽然连不通但能跑完流程
    api_key = ""

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# --- 2. 搜索设置 ---
arxiv_client = arxiv.Client()
search = arxiv.Search(
    query = 'cat:q-fin.ST OR cat:q-fin.PM OR cat:cs.LG',
    max_results = 10,  
    sort_by = arxiv.SortCriterion.SubmittedDate
)

papers_data = []

print(f"🚀 Alpha Hunter (安全版) 启动中...")

# 只有 Key 存在时才打印这一行，且只打印前几位，防止泄露
if api_key:
    print(f"🔑 API Key 加载成功: {api_key[:6]}******")
else:
    print("❌ API Key 未加载！")

print("📡 正在连接 ArXiv 获取最新论文...")

results = list(arxiv_client.results(search))
print(f"✅ 成功获取 {len(results)} 篇论文元数据...")

for i, result in enumerate(results):
    print(f"\n[{i+1}/10] 正在分析: {result.title[:50]}...")
    
    prompt = f"""
    你是华尔街顶级对冲基金的 Quant Researcher。
    请阅读这篇论文摘要，判断其对量化交易的实战价值。
    
    摘要内容：
    {result.summary}
    
    请严格按照以下 JSON 格式返回（不要 Markdown，只要纯 JSON）：
    {{
        "ai_score": (0-10分，数值类型，保留一位小数),
        "ai_verdict": (犀利的中文点评，30字以内，直击痛点),
        "ai_strategy": (适合的策略类型)
    }}
    """
    
    try:
        if not api_key:
            raise ValueError("没有 API Key，跳过分析")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个输出 JSON 格式的助手。"},
                {"role": "user", "content": prompt},
            ],
            response_format={ 'type': 'json_object' }, 
            stream=False
        )
        
        content = response.choices[0].message.content
        analysis = json.loads(content)
        
        print(f"   🧠 分析完成！")
        print(f"   👉 评分: {analysis.get('ai_score')} | 策略: {analysis.get('ai_strategy')}")
        
    except Exception as e:
        print(f"   ❌ 分析失败: {e}")
        analysis = {
            "ai_score": 0, 
            "ai_verdict": "分析失败/Key缺失", 
            "ai_strategy": "未知"
        }

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
    time.sleep(1)

with open('papers.json', 'w', encoding='utf-8') as f:
    json.dump(papers_data, f, ensure_ascii=False, indent=4)

print("\n" + "="*50)
print(f"✅ 任务完成！")
