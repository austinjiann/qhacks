import json
from dataclasses import dataclass
from typing import Optional

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


DETECT_AND_SANITIZE_PROMPT = """You analyze prompts for an AI video generator that CANNOT use real people's names.

Given a title and outcome from a prediction market, do ALL of the following:

1. **has_real_people**: true/false — does the text mention ANY real person (celebrity, athlete, politician, etc.)?
2. **image_search_query**: If has_real_people is true, write a Google Image Search query that would find a high-quality photo of these people in the right context (e.g. "Drake performing concert stage" or "LeBron James dunking Lakers"). Make it specific enough to get a relevant photo. If no real people, set to null.
3. **safe_title**: Rewrite the title replacing ALL real person names with vivid generic descriptions (e.g. "Drake" → "a famous Canadian rapper", "Trump" → "a prominent political leader"). Keep everything else the same.
4. **safe_outcome**: Same treatment for the outcome.

Return JSON only:
{"has_real_people": bool, "image_search_query": str|null, "safe_title": str, "safe_outcome": str}"""


@dataclass
class PromptAnalysis:
    has_real_people: bool
    image_search_query: Optional[str]
    safe_title: str
    safe_outcome: str


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


async def detect_and_sanitize(title: str, outcome: str) -> PromptAnalysis:
    """Detect real people in the prompt and produce sanitized versions + image search query.

    Single OpenAI call that handles everything upfront.
    """
    user_message = f"""Title: {title}
Outcome: {outcome}"""

    try:
        response = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DETECT_AND_SANITIZE_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)
        return PromptAnalysis(
            has_real_people=parsed.get("has_real_people", False),
            image_search_query=parsed.get("image_search_query"),
            safe_title=parsed.get("safe_title", title),
            safe_outcome=parsed.get("safe_outcome", outcome),
        )
    except Exception as e:
        print(f"[prompt_enhancer] detect_and_sanitize failed: {e}")
        # SAFETY: If detection fails, assume the worst — treat as having
        # real people and use a maximally generic fallback so celebrity
        # names NEVER reach Veo.
        return PromptAnalysis(
            has_real_people=True,
            image_search_query=None,
            safe_title="a trending prediction market event",
            safe_outcome="the predicted outcome happens",
        )
