from openai import AsyncOpenAI
from utils.env import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You lightly clarify trading market titles for a video AI. Given a trade title, outcome, and link, return ONE short sentence that makes the outcome obvious.

Rules:
1. Stay very close to the original title. Only add small clarifying details.
2. For competitions, name the winner AND the loser (e.g. "Seahawks beat the Eagles to win the Super Bowl").
3. One sentence max.
4. No statistics, odds, or numbers. No cinematic language. No camera directions.
5. Just state what happened as a simple headline."""


async def enhance_prompt(title: str, outcome: str, original_trade_link: str) -> str:
    user_message = f"""Trade title: {title}
Selected outcome: {outcome}
Trade link: {original_trade_link}

Write a vivid cinematic scene description for this outcome."""

    response = await _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()
