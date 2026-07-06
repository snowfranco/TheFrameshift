# Local logo fallbacks

Used by `watcher/logo_fetcher.py` when Clearbit is unavailable.

**Filename format:** `{company_key}.png`  
Use underscores for multi-word keys: `boston_dynamics.png`, `hugging_face.png`

**Format:** PNG with transparency (RGBA). Target size: ≤200×80px.

**Examples:** `openai.png`, `anthropic.png`, `meta.png`, `nvidia.png`

Company keys and their domains are defined in `logo_fetcher.COMPANY_DOMAINS`.
