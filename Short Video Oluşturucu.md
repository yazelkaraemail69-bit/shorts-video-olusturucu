# Short Video Oluşturucu Projesi

Master AI Yönetmen ile YouTube Shorts / Instagram Reels / TikTok video üretim hattı.

**GitHub deposu:** https://github.com/yazelkaraemail69-bit/shorts-video-olusturucu

---

## Ne yapar?

| Ajan | Görev | Sağlayıcı |
|------|-------|-----------|
| **AI1** | Viral senaryo (hook → gelişme → CTA) | OpenRouter / Claude |
| **AI2** | Her sahne için 9:16 sinematik görsel | OpenRouter image (Flux) |
| **AI3** | Görsel + ElevenLabs ses + kurgu → MP4 | FFmpeg |
| **Eleştiri** | Senaryoyu tartış, yalnız ilgili kısmı revize et | OpenRouter |

Ek özellikler:
- Shorts önizleme (9:16 dikey player + kinetik caption)
- Kredi sistemi ve kopya kilidi
- Admin paneli

---

## Hızlı başlangıç

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

### .env ayarları

Geliştirme için `MOCK_AI=true` yeterli (gerçek API çağrılmaz).

Canlı üretim için `backend/.env` içine:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL=anthropic/claude-sonnet-4`
- `OPENROUTER_IMAGE_MODEL=black-forest-labs/flux.2-pro`
- `ELEVENLABS_API_KEY`
- `ENCRYPTION_KEY` (Fernet)
- `JWT_SECRET`
- `ADMIN_EMAIL`
- `MOCK_AI=false`

### Sunucuyu başlat

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

| Sayfa | Adres |
|-------|-------|
| Stüdyo | http://localhost:8000 |
| Admin | http://localhost:8000/admin |
| API docs | http://localhost:8000/docs |
| Sağlık | http://localhost:8000/health |

---

## Proje yapısı

```
shorts-video-olusturucu/
├── backend/                 # FastAPI — ana uygulama
│   ├── app/
│   │   ├── main.py          # Uygulama girişi
│   │   ├── routers/         # API uçları
│   │   └── services/
│   │       └── director/    # AI1, AI2, AI3 hattı
│   ├── static/              # Stüdyo arayüzü (index.html)
│   └── requirements.txt
├── src/                     # Next.js (modüler AI üretim)
└── supabase/                # Veritabanı migration
```

---

## Kullanım akışı

1. Stüdyoda fikir notunu yaz (ör. “kahve shorts”).
2. **AI1: Viral Senaryo Yaz** — hook → payoff senaryosu oluşur.
3. **AI2+AI3: Görsel Üret & Kurguya Ver** — MP4 + eleştiri raporu.
4. İstersen eleştiri yaz → yalnız ilgili parça revize edilir.

---

## Lisans

ISC
