#!/usr/bin/env python3
"""
理学療法・作業療法 教科書チャットボット
qwen2.5-coder:3b (高速) + ChromaDB + キーワード検索ハイブリッド
"""
import os, sys, json, re
import requests
import chromadb
from sentence_transformers import SentenceTransformer
from flask import Flask, request, Response, stream_with_context

DB_DIR      = os.path.expanduser("~/textbook-chatbot/chroma_db")
EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"
OLLAMA_URL  = "http://localhost:11434/api/generate"
LLM_MODEL   = "gemma3:4b"    # 8GB RAM向け・高速・日本語医療対応
TOP_K       = 6

_model      = None
_collection = None

# ── リソースロード ────────────────────────────────────────────────

def load_resources():
    global _model, _collection
    if _model is None:
        print("埋め込みモデルをロード中...", flush=True)
        _model = SentenceTransformer(EMBED_MODEL)
        print("完了", flush=True)
    if _collection is None:
        client = chromadb.PersistentClient(path=DB_DIR)
        _collection = client.get_collection("textbooks")
        print(f"DB: {_collection.count()} チャンク読込済", flush=True)
    return _model, _collection

# ── ハイブリッド検索（ベクトル＋キーワード） ────────────────────

def search_context(question: str) -> list[dict]:
    model, col = load_resources()

    # ① ベクトル検索（意味的に近いチャンクを取得）
    emb = model.encode([question]).tolist()
    res = col.query(query_embeddings=emb, n_results=TOP_K,
                    include=["documents","metadatas","distances"])
    seen_ids = set()
    chunks = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        uid = f"{meta.get('source','')}_{meta.get('page','')}"
        seen_ids.add(uid)
        chunks.append({
            "text":   doc,
            "source": meta.get("source", ""),
            "page":   meta.get("page", "?"),
            "score":  round(1 - dist, 3),
            "match":  "意味検索",
        })

    # ② キーワード検索（質問の重要語を含むチャンクをBrute-forceで追加）
    # 英数字略語（MMT, ROM, ADLなど）と日本語重要語を抽出
    abbrevs  = re.findall(r'[A-Za-z0-9]{2,}', question)
    ja_parts = re.split(r'[ってはをがにのでへともやか、。？?！!\s　「」・（）()]+', question)
    keywords = list(set(abbrevs + [w for w in ja_parts if len(w) >= 2]))
    if keywords:
        all_docs = col.get(include=["documents","metadatas"])
        for doc, meta in zip(all_docs["documents"], all_docs["metadatas"]):
            uid = f"{meta.get('source','')}_{meta.get('page','')}"
            if uid in seen_ids:
                continue
            hit = sum(1 for kw in keywords if kw in doc)
            if hit >= 1:
                chunks.append({
                    "text":   doc,
                    "source": meta.get("source",""),
                    "page":   meta.get("page","?"),
                    "score":  round(hit / len(keywords), 3),
                    "match":  "キーワード",
                })
                seen_ids.add(uid)
                if len(chunks) >= TOP_K * 2:
                    break

    # スコア順に並べて上位8件
    chunks.sort(key=lambda x: x["score"], reverse=True)
    return chunks[:8]

# ── プロンプト構築 ────────────────────────────────────────────────

def build_prompt(question: str, chunks: list[dict]) -> str:
    ctx = "\n\n".join(
        f"【出典{i}】「{c['source']}」p.{c['page']}\n{c['text'][:500]}"
        for i, c in enumerate(chunks, 1)
    )
    return f"""あなたは理学療法士・作業療法士の国家試験・臨床学習を支援する医療専門AIです。

ルール：
- 教科書の記述と自分の医療知識を合わせて、正確に日本語で答えてください
- 教科書に記載があればそれを優先し、出典（書名・ページ）を示してください
- 略語（MMT、ROM、ADLなど）は必ずフルネームと意味を説明してください
- 推測で答えず、わからない場合は正直に「わかりません」と言ってください

【教科書の記述】
{ctx}

【質問】{question}

【回答（日本語で）】"""

# ── Flask アプリ ──────────────────────────────────────────────────

app = Flask(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>教科書チャットボット</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#f0f2f5;height:100vh;display:flex;flex-direction:column}
header{background:#1d4ed8;color:#fff;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px}
header h1{font-size:17px;font-weight:700}
header p{font-size:11px;opacity:.75;margin-top:2px}
#bibBtn{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.4);color:#fff;border-radius:8px;padding:5px 11px;font-size:11.5px;cursor:pointer;white-space:nowrap;flex-shrink:0}
#bibBtn:hover{background:rgba(255,255,255,.28)}
#bibPanel{display:none;background:#fff;border-bottom:1px solid #e2e8f0;padding:12px 20px;font-size:12px;color:#334155}
#bibPanel.open{display:block}
#bibPanel h2{font-size:12.5px;font-weight:700;color:#1e40af;margin-bottom:8px}
#bibPanel ul{display:flex;flex-wrap:wrap;gap:4px 12px;padding-left:0;list-style:none}
#bibPanel li::before{content:"📖 "}
#chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.bubble{max-width:85%;padding:11px 15px;border-radius:16px;font-size:13.5px;line-height:1.7;word-break:break-word}
.user{align-self:flex-end;background:#1d4ed8;color:#fff;border-bottom-right-radius:4px;white-space:pre-wrap}
.bot{align-self:flex-start;background:#fff;color:#1e293b;border-bottom-left-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
.answer{white-space:pre-wrap}
.src-toggle{margin-top:8px;font-size:11px;color:#2563eb;cursor:pointer;user-select:none}
.src-toggle:hover{text-decoration:underline}
.src-list{display:none;margin-top:6px;border-top:1px solid #e2e8f0;padding-top:6px;font-size:11.5px;color:#475569}
.src-list.open{display:block}
.src-item{margin-bottom:8px;padding:7px 9px;background:#f8fafc;border-radius:8px;border-left:3px solid #93c5fd}
.src-item .book{font-weight:600;color:#1e40af;margin-bottom:3px}
.src-item .excerpt{color:#64748b;font-size:11px;line-height:1.5}
.cursor::after{content:"▌";animation:blink .7s infinite}
@keyframes blink{50%{opacity:0}}
#form{display:flex;gap:8px;padding:12px 16px;background:#fff;border-top:1px solid #e2e8f0}
#q{flex:1;padding:9px 14px;border:1.5px solid #e2e8f0;border-radius:24px;font-size:13.5px;outline:none}
#q:focus{border-color:#2563eb}
button{background:#1d4ed8;color:#fff;border:none;border-radius:24px;padding:9px 20px;font-size:13.5px;cursor:pointer;white-space:nowrap}
button:disabled{opacity:.45;cursor:default}
</style>
</head>
<body>
<header>
  <div>
    <h1>📚 理学療法・作業療法 教科書チャットボット</h1>
    <p>gemma3 + RAG — 29冊の標準教科書から検索して回答</p>
  </div>
  <button id="bibBtn" onclick="toggleBib()">参考文献一覧 ▾</button>
</header>
<div id="bibPanel">
  <h2>収録教科書（29冊）</h2>
  <ul>
    <li>標準理学療法学　理学療法評価学</li>
    <li>標準理学療法学　理学療法概説</li>
    <li>標準理学療法学　神経理学療法学</li>
    <li>標準理学療法学　運動療法学総論</li>
    <li>標準理学療法学　運動療法学各論</li>
    <li>標準理学療法学　骨関節理学療法学</li>
    <li>標準理学療法学　内部疾患理学療法学</li>
    <li>標準理学療法学　地域理学療法学</li>
    <li>標準理学療法学　日常生活活動学・生活環境学</li>
    <li>標準理学療法学　物理療法学</li>
    <li>標準理学療法学　理学療法研究法</li>
    <li>標準理学療法学　病態運動学</li>
    <li>標準理学療法学　臨床実習とケーススタディ</li>
    <li>標準理学療法学作業療法学　解剖学</li>
    <li>標準理学療法学作業療法学　生理学</li>
    <li>標準理学療法学作業療法学　運動学</li>
    <li>標準理学療法学作業療法学　病理学</li>
    <li>標準理学療法学作業療法学　内科学</li>
    <li>標準理学療法学作業療法学　精神医学</li>
    <li>標準理学療法学作業療法学　神経内科</li>
    <li>標準理学療法学作業療法学　整形外科学</li>
    <li>標準理学療法学作業療法学　小児科学</li>
    <li>標準理学療法学作業療法学　老年学</li>
    <li>標準理学療法学作業療法学　人間発達学</li>
    <li>標準理学療法学作業療法学　義肢装具学</li>
    <li>標準理学療法学作業療法学　リハビリテーション管理学</li>
    <li>標準理学療法学作業療法学　がんのリハビリテーション</li>
    <li>標準理学療法学作業療法学　脳画像</li>
    <li>系統看護学講座　解剖生理学</li>
  </ul>
</div>
<div id="chat">
  <div class="bubble bot"><div class="answer">こんにちは！教科書について何でも聞いてください。
例：「ROMとは」「大腿骨頸部骨折のリハビリ」「筋電図の読み方」</div></div>
</div>
<form id="form" onsubmit="send(event)">
  <input id="q" type="text" placeholder="質問を入力…" autocomplete="off">
  <button id="btn">送信</button>
</form>
<script>
const chat=document.getElementById('chat'),q=document.getElementById('q'),btn=document.getElementById('btn');
function scroll(){chat.scrollTop=chat.scrollHeight}
function toggleBib(){
  const p=document.getElementById('bibPanel'),b=document.getElementById('bibBtn');
  p.classList.toggle('open');
  b.textContent=p.classList.contains('open')?'参考文献一覧 ▴':'参考文献一覧 ▾';
}

function addUser(t){
  const d=document.createElement('div');
  d.className='bubble user';d.textContent=t;
  chat.appendChild(d);scroll();
}

function addBot(){
  const wrap=document.createElement('div');
  wrap.className='bubble bot';
  const ans=document.createElement('div');ans.className='answer cursor';
  wrap.appendChild(ans);
  chat.appendChild(wrap);scroll();
  return{ans,wrap};
}

function addSources(wrap,sources){
  if(!sources||!sources.length)return;
  const tog=document.createElement('div');
  tog.className='src-toggle';
  tog.textContent='📖 参照した教科書を見る（'+sources.length+'件）▼';
  const list=document.createElement('div');list.className='src-list';
  sources.forEach((c,i)=>{
    const item=document.createElement('div');item.className='src-item';
    item.innerHTML=`<div class="book">【${i+1}】「${c.source}」p.${c.page} <span style="color:#64748b;font-weight:normal">(${c.match} ${Math.round(c.score*100)}%)</span></div>`+
      `<div class="excerpt">${c.text.slice(0,120).replace(/\n/g,' ')}…</div>`;
    list.appendChild(item);
  });
  tog.onclick=()=>{list.classList.toggle('open');tog.textContent=list.classList.contains('open')?'📖 参照した教科書を閉じる▲':'📖 参照した教科書を見る（'+sources.length+'件）▼'};
  wrap.appendChild(tog);wrap.appendChild(list);
}

async function send(e){
  e.preventDefault();
  const text=q.value.trim();if(!text)return;
  q.value='';btn.disabled=true;
  addUser(text);
  const{ans,wrap}=addBot();
  try{
    const res=await fetch('/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text})});
    const reader=res.body.getReader(),dec=new TextDecoder();
    let sources=[];
    while(true){
      const{done,value}=await reader.read();if(done)break;
      for(const line of dec.decode(value).split('\n')){
        if(!line.startsWith('data: '))continue;
        const d=line.slice(6);if(d==='[DONE]')break;
        try{
          const obj=JSON.parse(d);
          if(obj.token){ans.textContent+=obj.token;scroll();}
          if(obj.sources)sources=obj.sources;
        }catch{}
      }
    }
    ans.classList.remove('cursor');
    addSources(wrap,sources);
  }catch(err){ans.classList.remove('cursor');ans.textContent='エラー: '+err;}
  btn.disabled=false;scroll();q.focus();
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

@app.route("/stream", methods=["POST"])
def stream():
    question = request.json.get("question","").strip()
    if not question:
        return Response("data: [DONE]\n\n", mimetype="text/event-stream")

    chunks  = search_context(question)
    prompt  = build_prompt(question, chunks)

    def generate():
        yield f"data: {json.dumps({'sources': chunks}, ensure_ascii=False)}\n\n"
        try:
            with requests.post(OLLAMA_URL, json={
                "model":   LLM_MODEL,
                "prompt":  prompt,
                "stream":  True,
                "options": {"temperature": 0.2, "num_predict": 800},
            }, stream=True, timeout=300) as resp:
                for line in resp.iter_lines():
                    if not line: continue
                    obj = json.loads(line)
                    t   = obj.get("response","")
                    if t:
                        yield f"data: {json.dumps({'token': t}, ensure_ascii=False)}\n\n"
                    if obj.get("done"): break
        except Exception as e:
            msg = "\nエラー: " + str(e)
            yield f"data: {json.dumps({'token': msg})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

if __name__ == "__main__":
    load_resources()
    print("\n🚀 起動完了 → http://localhost:7860\n")
    app.run(host="0.0.0.0", port=7860, debug=False, threaded=True)
