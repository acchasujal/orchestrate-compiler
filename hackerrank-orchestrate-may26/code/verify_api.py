import os
from openai import OpenAI

def verify():
    keys = [("GROQ_API_KEY", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"), 
            ("NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1", "meta/llama-3.1-70b-instruct")]
    for env_name, url, model in keys:
        key = os.environ.get(env_name)
        if not key:
            print(f"[-] {env_name} missing.")
            continue
        try:
            client = OpenAI(base_url=url, api_key=key)
            client.chat.completions.create(model=model, messages=[{"role":"user","content":"Hi"}], max_tokens=5)
            print(f"[+] {env_name} ACTIVE")
        except Exception as e:
            print(f"[-] {env_name} FAILED: {e}")

if __name__ == "__main__": verify()