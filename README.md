# StepWay

## Fayllar
- `main.py` — backend (FastAPI): Telegram login tekshiruvi, tarix, shaxsiy tezlik
- `static/index.html` — sayt (frontend)
- `requirements.txt`, `Procfile` — Railway uchun

## GitHub → Railway joylash tartibi

1. Bu papkadagi barcha fayllarni GitHub repositoriyaga yuklang (`main.py`, `static/index.html`, `requirements.txt`, `Procfile`).
2. Railway'da yangi loyiha oching va shu repository'ni ulang.
3. Railway loyihasida **Variables** bo'limiga quyidagilarni qo'shing:
   - `BOT_TOKEN` — @BotFather bergan token (@stepwayloginbot uchun)
   - `SECRET_KEY` — o'zingiz o'ylab topgan uzun tasodifiy matn (masalan 40 ta random belgi)
4. @BotFather'da botga ulanadigan domenni sozlang:
   - BotFather'ga boring → `/mybots` → `@stepwayloginbot` → **Bot Settings** → **Domain** → Railway sizga bergan domenni kiriting (masalan `stepway-production.up.railway.app`)
   - Bu qadamsiz Telegram Login tugmasi ishlamaydi.
5. Deploy tugagach, Railway domeningizni ochib ko'ring — sayt ishlab turgan bo'ladi.

## Eslatma
- `stepway.db` (SQLite) Railway'ning fayl tizimida saqlanadi. Agar loyiha qayta deploy qilinsa yoki instance o'zgarsa, ma'lumotlar yo'qolishi mumkin — kelajakda kerak bo'lsa Railway'ning Volume yoki Postgres xizmatiga o'tish mumkin.
