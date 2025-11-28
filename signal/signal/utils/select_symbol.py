import json, os, sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

BASE = Path(__file__).resolve().parent.parent.parent

def main():
    load_dotenv(BASE / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=api_key)
    with open(BASE / "config/prompt_select.txt","r",encoding="utf-8") as f:
        p_select = f.read().strip()
    with open(BASE / "config/prompt_anna.txt","r",encoding="utf-8") as f:
        p_anna = f.read().strip()
    with open(BASE / "config/pool.json","r",encoding="utf-8") as f:
        pool = json.load(f)

    user = "Пул активов:\n" + json.dumps(pool, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL","gpt-4.1-mini"),
        response_format={"type":"json_object"},
        messages=[
            {"role":"system","content":p_select},
            {"role":"system","content":p_anna},
            {"role":"user","content":user},
        ],
        temperature=0.2,
    )
    print(resp.choices[0].message.content)

if __name__ == "__main__":
    main()
