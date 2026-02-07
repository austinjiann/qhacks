from openai import AsyncOpenAI
from utils.env import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You lightly clarify betting market titles for a video AI. Given a bet title, outcome, and link, return ONE short sentence that makes the outcome obvious.

Rules:
1. Stay very close to the original title. Only add small clarifying details.
2. For competitions, name the winner AND the loser (e.g. "Seahawks beat the Eagles to win the Super Bowl").
3. One sentence max, under 20 words.
4. No statistics, odds, or numbers. No cinematic language. No camera directions.
5. Just state what happened as a simple headline."""


async def enhance_prompt(title: str, outcome: str, original_bet_link: str) -> str:
    """Use GPT-4o-mini to expand bare bet fields into a rich scene description."""
    user_message = f"""Bet title: {title}
Selected outcome: {outcome}
Bet link: {original_bet_link}

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
