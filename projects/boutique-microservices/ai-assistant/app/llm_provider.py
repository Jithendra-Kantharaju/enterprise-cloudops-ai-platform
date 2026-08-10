"""Provider-agnostic generation: OpenAI or Anthropic, chosen by LLM_PROVIDER."""
import os

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")


def generate(system_prompt: str, user_content: str, temperature: float = 0.2) -> dict:
    """Return {text, provider, model, prompt_tokens, completion_tokens}."""
    if PROVIDER == "anthropic":
        return _anthropic(system_prompt, user_content, temperature)
    return _openai(system_prompt, user_content, temperature)


def _openai(system_prompt, user_content, temperature):
    from openai import OpenAI
    r = OpenAI().chat.completions.create(
        model=OPENAI_MODEL, temperature=temperature,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_content}],
    )
    u = r.usage
    return {"text": r.choices[0].message.content.strip(), "provider": "openai",
            "model": OPENAI_MODEL,
            "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens}


def _anthropic(system_prompt, user_content, temperature):
    import anthropic
    r = anthropic.Anthropic().messages.create(
        model=ANTHROPIC_MODEL, max_tokens=1024, temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in r.content if b.type == "text").strip()
    return {"text": text, "provider": "anthropic", "model": ANTHROPIC_MODEL,
            "prompt_tokens": r.usage.input_tokens, "completion_tokens": r.usage.output_tokens}