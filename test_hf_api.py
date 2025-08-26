import os
import requests

# 🔑 Put your actual Hugging Face API key here or set as environment variable
HF_API_KEY = os.getenv("HF_API_KEY", "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")
HF_MODEL = "facebook/bart-large-cnn"   # free + works well

url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
headers = {"Authorization": f"Bearer {HF_API_KEY}"}

# Test prompt
prompt = """
You are an educational coach. Analyze this student:

Journals:
- 2025-08-19: Taught Circles chapter
- 2025-08-18: Struggling with Triangles

Tests:
- 2025-08-16: 22/25

Attendance:
- Present on 18, 19 Aug
- Absent on 20 Aug

Please give me:
1. Strengths
2. Weaknesses
3. Actionable Advice
4. Overall Trend
"""


payload = {"inputs": prompt}

response = requests.post(url, headers=headers, json=payload)

try:
    response.raise_for_status()
    print("✅ Hugging Face Response:")
    print(response.json())
except requests.exceptions.RequestException as e:
    print("❌ Request failed:", e)
    print("Response content:", response.text)
