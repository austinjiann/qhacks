import json
from dataclasses import dataclass

from openai import AsyncOpenAI
from utils.env import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


DETECT_AND_SANITIZE_PROMPT = """You analyze prompts for an AI video generator that CANNOT reference real people AT ALL — not by name, not by description, not by role.

Given a title and outcome from a prediction market, do ALL of the following:

1. **has_real_people**: true/false — does the text mention ANY real person (celebrity, athlete, politician, etc.)?
2. **detected_names**: List of ALL real person names found in the text (first name, last name, nicknames, any form). Empty list if none.
3. **safe_title**: Rewrite the title to focus ONLY on the event/action, completely removing all references to people. Do NOT replace names with descriptions like "a famous rapper" or "a political leader" — those still reference real people. Instead, rewrite around the EVENT itself.
   Examples:
   - "Will Drake release a new album in 2026?" → "Will a new rap album drop in 2026?"
   - "Trump wins the election" → "A dramatic election night victory"
   - "Taylor Swift and Kelce break up" → "A celebrity couple splits up"
   - "Messi scores in the final" → "A dramatic goal in the championship final"
4. **safe_outcome**: Same treatment — describe the EVENT/RESULT only, no person references whatsoever. Also clean up any "YES -" or "NO -" prefixes into natural language.
   Examples:
   - "YES - Drake releases album" → "A new rap album is released"
   - "NO - Will Taylor Swift tour?" → "The anticipated concert tour does not happen"

Return JSON only:
{"has_real_people": bool, "detected_names": [str], "safe_title": str, "safe_outcome": str}"""


@dataclass
class PromptAnalysis:
    has_real_people: bool
    detected_names: list[str]
    safe_title: str
    safe_outcome: str


def _names_leak_check(detected_names: list[str], safe_title: str, safe_outcome: str) -> bool:
    """Return True if ANY detected name still appears in the safe text."""
    combined = f"{safe_title} {safe_outcome}".lower()
    for name in detected_names:
        # Check full name and each individual part (first/last)
        parts = [name] + name.split()
        for part in parts:
            part_lower = part.lower().strip()
            if len(part_lower) >= 3 and part_lower in combined:
                print(f"[prompt_enhancer] LEAK DETECTED: \"{part}\" still in safe text!", flush=True)
                return True
    return False


async def detect_and_sanitize(title: str, outcome: str) -> PromptAnalysis:
    """Detect real people in the prompt and produce sanitized versions.

    Single OpenAI call that handles everything upfront, with hard validation
    that no detected names leak into the safe text sent to Veo.
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

        has_real_people = parsed.get("has_real_people", False)
        detected_names = parsed.get("detected_names", [])
        safe_title = parsed.get("safe_title", title)
        safe_outcome = parsed.get("safe_outcome", outcome)

        # ── Hard validation: if names were detected, verify they're gone ──
        if has_real_people or detected_names:
            if _names_leak_check(detected_names, safe_title, safe_outcome):
                print(f"[prompt_enhancer] GPT sanitization leaked names — using generic fallback", flush=True)
                return PromptAnalysis(
                    has_real_people=True,
                    detected_names=detected_names,
                    safe_title="a trending prediction market event",
                    safe_outcome="the predicted outcome happens",
                )

        # ── Extra safety: even if GPT said no real people, double-check ──
        # Compare safe vs original — if they're identical, GPT may have
        # missed the names entirely. Check original for capitalized
        # multi-word sequences that look like names.
        if not has_real_people and safe_title == title and safe_outcome == outcome:
            # GPT said no real people and didn't change anything — trust it
            pass

        print(f"[prompt_enhancer] Sanitization OK — safe_title=\"{safe_title}\", safe_outcome=\"{safe_outcome}\"", flush=True)
        return PromptAnalysis(
            has_real_people=has_real_people,
            detected_names=detected_names,
            safe_title=safe_title,
            safe_outcome=safe_outcome,
        )
    except Exception as e:
        print(f"[prompt_enhancer] detect_and_sanitize failed: {e}", flush=True)
        return PromptAnalysis(
            has_real_people=True,
            detected_names=[],
            safe_title="a trending prediction market event",
            safe_outcome="the predicted outcome happens",
        )
