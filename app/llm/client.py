from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def ask_llm(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.output_text.strip()