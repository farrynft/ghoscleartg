# Telegram Inactive User Kicker Bot

Telegram kanallarındaki inaktif kullanıcıları otomatik olarak tespit edip çıkaran bot.

## 🎯 Özellikler

- ✅ Tüm topic'leri tarar
- ✅ Geçmiş mesajları analiz eder
- ✅ Otomatik günlük kontrol
- ✅ Whitelist desteği
- ✅ Detaylı raporlama
- ✅ Railway ready

## 🚀 Railway Deploy

### 1. GitHub'a Push Et

\`\`\`bash
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_REPO_URL
git push -u origin main
\`\`\`

### 2. Railway'de Variables Ekle

\`\`\`bash
API_ID=your_api_id
API_HASH=your_api_hash
PHONE=+905XXXXXXXXX
CHANNEL_USERNAME=@your_channel
INACTIVE_DAYS=7
CHECK_HOUR=0
CHECK_MINUTE=0
TIMEZONE=Europe/Istanbul
RUN_ON_START=true
\`\`\`

### 3. Session Oluştur

Local'de:

\`\`\`bash
pip install telethon
python session_creator.py
\`\`\`

Oluşan \`session.session\` dosyasını Railway Volume'e yükle:
- Mount Path: \`/app/data\`
- Dosya adı: \`session.session\`

### 4. Deploy & Start

Railway otomatik deploy edecek ve bot çalışmaya başlayacak!

## 🛡️ Whitelist Kullanımı

Railway Variables'a ekle:

\`\`\`bash
WHITELIST_USERNAMES=user1,user2,admin
WHITELIST_USER_IDS=123456789,987654321
\`\`\`

## 📊 Logları İzleme

Railway dashboard → Deployments → Logs

## 🔧 Manuel Çalıştırma

\`\`\`bash
railway run python main.py manual
\`\`\`

## ⚙️ Environment Variables

| Variable | Açıklama | Default |
|----------|----------|---------|
| API_ID | Telegram API ID | - |
| API_HASH | Telegram API Hash | - |
| PHONE | Telefon numarası | - |
| CHANNEL_USERNAME | Kanal username/ID | - |
| INACTIVE_DAYS | İnaktiflik süresi | 7 |
| CHECK_HOUR | Kontrol saati | 0 |
| CHECK_MINUTE | Kontrol dakikası | 0 |
| TIMEZONE | Zaman dilimi | Europe/Istanbul |
| RUN_ON_START | Başlangıçta çalış | false |
| WHITELIST_USERNAMES | Korumalı usernames | - |
| WHITELIST_USER_IDS | Korumalı user IDs | - |

## 📝 Notlar

- Bot kanalda admin olmalı
- Ban yetkisi olmalı
- Session dosyası güvenli saklanmalı

## 🆘 Sorun Giderme

**Session hatası:** Session dosyasını tekrar oluştur  
**API hatası:** API credentials kontrol et  
**Ban hatası:** Bot'un admin yetkilerini kontrol et

## 📄 Lisans

MIT
