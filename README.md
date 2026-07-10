# Shorts Video Oluşturucu

Master AI Yönetmen ile YouTube Shorts / Reels üretim hattı.

## Ne yapar?

1. **AI1 — Senaryo** (OpenRouter / Claude): viral hook → gelişme → CTA  
2. **AI2 — Görsel** (OpenRouter image / Flux): her sahne için 9:16 kare  
3. **AI3 — Kurgu** (FFmpeg): görsel + ElevenLabs ses → MP4  
4. **Tartışma paneli**: senaryoyu eleştir, yalnız ilgili kısmı revize et  
5. **Kopya kilidi**: senaryoyu kopyalamak için kredi (admin muaf)

## Hızlı başlangıç

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env` içine anahtarlarını yaz (detay: [`backend/.env.example`](backend/.env.example)):

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL=anthropic/claude-sonnet-4`
- `OPENROUTER_IMAGE_MODEL=black-forest-labs/flux.2-pro`
- `ELEVENLABS_API_KEY`
- `ENCRYPTION_KEY` (Fernet)
- `JWT_SECRET`
- `ADMIN_EMAIL` (sonsuz kredi + admin panel)
- `MOCK_AI=false` (canlı) veya `true` (geliştirme)

```bash
uvicorn app.main:app --reload --port 8000
```

- Stüdyo: http://localhost:8000  
- Admin: http://localhost:8000/admin  
- API docs: http://localhost:8000/docs  

Daha fazla: [`backend/README.md`](backend/README.md)
