from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.errors import FloodWaitError
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import json
import os
import logging

# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d.%m.%Y %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '')
INACTIVE_DAYS = int(os.getenv('INACTIVE_DAYS', '7'))
CHECK_HOUR = int(os.getenv('CHECK_HOUR', '0'))
CHECK_MINUTE = int(os.getenv('CHECK_MINUTE', '0'))
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Istanbul')

# Uyarı sistemi ayarları
WARNING_ENABLED = os.getenv('WARNING_ENABLED', 'true').lower() == 'true'
WARNING_DAYS_BEFORE = int(os.getenv('WARNING_DAYS_BEFORE', '2'))
WARNING_MESSAGE = os.getenv('WARNING_MESSAGE', 
    '⚠️ Dikkat! Son {days} gündür mesaj atmadınız. '
    '{remaining} gün içinde mesaj atmazsanız gruptan çıkarılacaksınız!')

# Rapor sistemi
REPORT_ENABLED = os.getenv('REPORT_ENABLED', 'true').lower() == 'true'
REPORT_CHAT_ID = os.getenv('REPORT_CHAT_ID', '')  # Boş bırakılırsa kanala gönderir
ADMIN_USER_IDS = os.getenv('ADMIN_USER_IDS', '').split(',')
ADMIN_USER_IDS = [int(uid.strip()) for uid in ADMIN_USER_IDS if uid.strip().isdigit()]

# WHITELIST - Asla çıkarılmayacak kullanıcılar
WHITELIST_USERNAMES = os.getenv('WHITELIST_USERNAMES', '').split(',')
WHITELIST_USER_IDS = os.getenv('WHITELIST_USER_IDS', '').split(',')

# Temizle ve parse et
WHITELIST_USERNAMES = [u.strip().lower().replace('@', '') for u in WHITELIST_USERNAMES if u.strip()]
WHITELIST_USER_IDS = [int(uid.strip()) for uid in WHITELIST_USER_IDS if uid.strip().isdigit()]

USER_DATA_FILE = '/app/data/user_activity.json'
WHITELIST_FILE = '/app/data/whitelist.json'

# Data klasörünü oluştur
os.makedirs('/app/data', exist_ok=True)

def load_user_data():
    """Kullanıcı aktivite verilerini yükle"""
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            logger.warning("Kullanıcı verisi okunamadı, yeni dosya oluşturuluyor")
            return {}
    return {}

def save_user_data(data):
    """Kullanıcı aktivite verilerini kaydet"""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Kullanıcı verisi kaydedildi ({len(data)} kullanıcı)")
    except Exception as e:
        logger.error(f"❌ Veri kaydetme hatası: {e}")

def load_whitelist():
    """Whitelist'i yükle"""
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'usernames': [], 'user_ids': []}
    return {'usernames': [], 'user_ids': []}

def save_whitelist(whitelist):
    """Whitelist'i kaydet"""
    try:
        with open(WHITELIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Whitelist kaydetme hatası: {e}")

def is_whitelisted(user_id, username):
    """Kullanıcı whitelist'te mi kontrol et"""
    # ENV'den whitelist
    if user_id in WHITELIST_USER_IDS:
        return True, "ENV - User ID"
    
    if username and username.lower() in WHITELIST_USERNAMES:
        return True, "ENV - Username"
    
    # Dosyadan whitelist
    whitelist = load_whitelist()
    if user_id in whitelist.get('user_ids', []):
        return True, "Dosya - User ID"
    
    if username and username.lower() in [u.lower() for u in whitelist.get('usernames', [])]:
        return True, "Dosya - Username"
    
    return False, None

def is_admin(user_id):
    """Kullanıcı admin mi kontrol et"""
    return user_id in ADMIN_USER_IDS

async def send_daily_report(client, channel, report_data):
    """Günlük rapor gönder"""
    try:
        report_text = f"""
📊 **GÜNLÜK AKTİVİTE RAPORU**
📅 Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

{'='*40}
👥 **ÜYE İSTATİSTİKLERİ**
{'='*40}
- Toplam üye: {report_data['total_members']}
- ✅ Aktif: {report_data['active_users']}
- ⚠️ Uyarı gönderilen: {report_data['warned_users']}
- 🛡️ Korumalı: {report_data['whitelisted_users']}
- ❌ Çıkarılan: {report_data['removed_users']}
- ⚠️ Çıkarılamayan: {report_data['skipped_users']}

{'='*40}
📨 **MESAJ İSTATİSTİKLERİ**
{'='*40}
- Taranan mesaj: {report_data['total_messages']}
- Topic sayısı: {report_data['topic_count']}

{'='*40}
"""

        if report_data['warned_list']:
            report_text += f"\n⚠️ **Uyarı Gönderilenler:**\n"
            for user in report_data['warned_list'][:5]:
                report_text += f"  • {user['name']} (@{user['username'] or 'no_username'}) - {user['days_remaining']} gün kaldı\n"
            if len(report_data['warned_list']) > 5:
                report_text += f"  ... ve {len(report_data['warned_list']) - 5} kişi daha\n"

        if report_data['removed_list']:
            report_text += f"\n❌ **Çıkarılanlar:**\n"
            for user in report_data['removed_list'][:5]:
                report_text += f"  • {user['name']} (@{user['username'] or 'no_username'}) - {user['reason']}\n"
            if len(report_data['removed_list']) > 5:
                report_text += f"  ... ve {len(report_data['removed_list']) - 5} kişi daha\n"

        report_text += f"\n✅ **Bot durumu:** Çalışıyor\n"
        report_text += f"⏰ **Sonraki kontrol:** Yarın {CHECK_HOUR:02d}:{CHECK_MINUTE:02d}"

        # Raporu gönder
        if REPORT_CHAT_ID:
            # Belirtilen chat'e gönder (admin DM veya özel kanal)
            await client.send_message(int(REPORT_CHAT_ID), report_text)
            logger.info(f"📊 Rapor gönderildi: {REPORT_CHAT_ID}")
        else:
            # Ana kanala gönder
            await client.send_message(channel, report_text)
            logger.info(f"📊 Rapor kanala gönderildi")

    except Exception as e:
        logger.error(f"❌ Rapor gönderme hatası: {e}")

async def handle_command(client, event, channel):
    """Telegram komutlarını işle"""
    message = event.message
    user_id = message.from_id.user_id if hasattr(message.from_id, 'user_id') else None
    
    if not user_id or not is_admin(user_id):
        await message.reply("❌ Bu komutu kullanma yetkiniz yok!")
        return
    
    text = message.text.strip()
    
    try:
        # /stats komutu
        if text == '/stats':
            user_data = load_user_data()
            whitelist = load_whitelist()
            
            total_tracked = len(user_data)
            active = sum(1 for v in user_data.values() if isinstance(v, dict) and v.get('last_message'))
            inactive = total_tracked - active
            whitelisted = len(whitelist.get('usernames', [])) + len(whitelist.get('user_ids', []))
            
            stats_text = f"""
📊 **ANLIK İSTATİSTİKLER**

👥 Takip edilen: {total_tracked}
✅ Aktif: {active}
❌ İnaktif: {inactive}
🛡️ Whitelist: {whitelisted}

⚙️ Ayarlar:
- İnaktiflik süresi: {INACTIVE_DAYS} gün
- Uyarı: {WARNING_DAYS_BEFORE} gün önce
- Kontrol saati: {CHECK_HOUR:02d}:{CHECK_MINUTE:02d}
"""
            await message.reply(stats_text)
        
        # /whitelist @username
        elif text.startswith('/whitelist '):
            username = text.replace('/whitelist ', '').strip().replace('@', '').lower()
            
            if not username:
                await message.reply("❌ Kullanım: /whitelist @username")
                return
            
            whitelist = load_whitelist()
            if 'usernames' not in whitelist:
                whitelist['usernames'] = []
            
            if username not in [u.lower() for u in whitelist['usernames']]:
                whitelist['usernames'].append(username)
                save_whitelist(whitelist)
                await message.reply(f"✅ @{username} whitelist'e eklendi!")
                logger.info(f"🛡️ Whitelist eklendi: @{username}")
            else:
                await message.reply(f"⚠️ @{username} zaten whitelist'te!")
        
        # /remove_whitelist @username
        elif text.startswith('/remove_whitelist '):
            username = text.replace('/remove_whitelist ', '').strip().replace('@', '').lower()
            
            if not username:
                await message.reply("❌ Kullanım: /remove_whitelist @username")
                return
            
            whitelist = load_whitelist()
            if 'usernames' not in whitelist:
                whitelist['usernames'] = []
            
            # Case-insensitive removal
            original_usernames = whitelist['usernames']
            whitelist['usernames'] = [u for u in original_usernames if u.lower() != username]
            
            if len(whitelist['usernames']) < len(original_usernames):
                save_whitelist(whitelist)
                await message.reply(f"✅ @{username} whitelist'ten çıkarıldı!")
                logger.info(f"🛡️ Whitelist'ten çıkarıldı: @{username}")
            else:
                await message.reply(f"⚠️ @{username} whitelist'te bulunamadı!")
        
        # /list_whitelist
        elif text == '/list_whitelist':
            whitelist = load_whitelist()
            usernames = whitelist.get('usernames', [])
            user_ids = whitelist.get('user_ids', [])
            
            if not usernames and not user_ids:
                await message.reply("📝 Whitelist boş!")
                return
            
            wl_text = "🛡️ **WHITELIST**\n\n"
            
            if usernames:
                wl_text += "**Username:**\n"
                for username in usernames:
                    wl_text += f"  • @{username}\n"
            
            if user_ids:
                wl_text += "\n**User ID:**\n"
                for uid in user_ids:
                    wl_text += f"  • {uid}\n"
            
            await message.reply(wl_text)
        
        # /help
        else:
            help_text = """
🤖 **BOT KOMUTLARI**

/stats - Anlık istatistikler
/whitelist @username - Kullanıcıyı koru
/remove_whitelist @username - Korumayı kaldır
/list_whitelist - Korumalı listesi

⚠️ Sadece adminler kullanabilir!
"""
            await message.reply(help_text)
    
    except Exception as e:
        await message.reply(f"❌ Hata: {str(e)}")
        logger.error(f"❌ Komut hatası: {e}")

async def send_warning_to_user(client, channel, user, days_inactive, days_remaining):
    """Kullanıcıya uyarı mesajı gönder"""
    try:
        warning_text = WARNING_MESSAGE.format(
            days=days_inactive,
            remaining=days_remaining
        )
        
        try:
            # Önce DM dene
            await client.send_message(user.id, warning_text)
            logger.info(f"📨 DM gönderildi: {user.first_name} (@{user.username or 'no_username'})")
            return True
        except Exception as dm_error:
            # DM gönderilemezse kanalda mention et
            logger.warning(f"⚠️ DM gönderilemedi, kanalda mention edilecek: {dm_error}")
            
            try:
                # Kanalda mention et
                mention_text = f"👤 [{user.first_name}](tg://user?id={user.id})\n{warning_text}"
                await client.send_message(channel, mention_text)
                logger.info(f"📢 Kanalda mention edildi: {user.first_name}")
                return True
            except Exception as mention_error:
                logger.error(f"❌ Mention başarısız: {mention_error}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Uyarı gönderme hatası: {e}")
        return False

async def scan_all_messages_comprehensive(client, channel, cutoff_date):
    """TÜM topic'lerdeki mesajları kapsamlı şekilde tara"""
    active_users = {}
    total_messages = 0
    topic_stats = {}
    
    logger.info("🔍 Kapsamlı mesaj taraması başlıyor...")
    logger.info("📊 Tüm mesajlar tek tek kontrol edilecek...")
    
    try:
        async for message in client.iter_messages(
            channel,
            offset_date=cutoff_date,
            reverse=True,
            limit=None
        ):
            if message.from_id:
                user_id = message.from_id.user_id if hasattr(message.from_id, 'user_id') else None
                
                if user_id:
                    topic_name = "Genel"
                    
                    if hasattr(message, 'reply_to') and message.reply_to:
                        if hasattr(message.reply_to, 'reply_to_top_id'):
                            topic_id = message.reply_to.reply_to_top_id
                            topic_name = f"Topic #{topic_id}"
                        elif hasattr(message.reply_to, 'forum_topic'):
                            topic_id = message.reply_to.reply_to_msg_id
                            topic_name = f"Topic #{topic_id}"
                    
                    # Timezone-aware datetime kullan
                    msg_date = message.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    
                    if user_id not in active_users:
                        active_users[user_id] = {
                            'last_message': msg_date,
                            'topics': set(),
                            'message_count': 0
                        }
                    
                    active_users[user_id]['topics'].add(topic_name)
                    active_users[user_id]['message_count'] += 1
                    
                    if msg_date > active_users[user_id]['last_message']:
                        active_users[user_id]['last_message'] = msg_date
                    
                    if topic_name not in topic_stats:
                        topic_stats[topic_name] = {'users': set(), 'messages': 0}
                    topic_stats[topic_name]['users'].add(user_id)
                    topic_stats[topic_name]['messages'] += 1
                    
                    total_messages += 1
                    
                    if total_messages % 500 == 0:
                        logger.info(f"  📊 {total_messages} mesaj tarandı, {len(active_users)} aktif kullanıcı bulundu...")
        
        logger.info(f"\n✅ Tarama tamamlandı!")
        logger.info(f"📨 Toplam {total_messages} mesaj")
        logger.info(f"👥 Toplam {len(active_users)} aktif kullanıcı")
        logger.info(f"📝 Toplam {len(topic_stats)} farklı topic\n")
        
        logger.info("📊 Topic İstatistikleri:")
        for topic_name, stats in sorted(topic_stats.items(), key=lambda x: x[1]['messages'], reverse=True):
            logger.info(f"  • {topic_name}: {len(stats['users'])} kullanıcı, {stats['messages']} mesaj")
        
        return active_users, total_messages, topic_stats
        
    except Exception as e:
        logger.error(f"❌ Mesaj tarama hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {}, 0, {}

async def check_and_kick_inactive():
    """İnaktif kullanıcıları kontrol et ve çıkar"""
    logger.info("\n" + "="*70)
    logger.info("🔍 İNAKTİF KULLANICI KONTROLÜ BAŞLADI")
    logger.info("="*70)
    
    client = TelegramClient('session', API_ID, API_HASH)
    
    try:
        await client.start(phone=PHONE)
        logger.info("✅ Telegram'a bağlanıldı")
        
        # Forum kanallar için özel handling
        try:
            # Önce normal deneme
            if str(CHANNEL_USERNAME).startswith('@'):
                channel = await client.get_entity(CHANNEL_USERNAME)
            else:
                # ID ise int'e çevir
                channel_id = int(str(CHANNEL_USERNAME).replace('-100', ''))
                channel = await client.get_entity(f'-100{channel_id}')
        except Exception as e:
            logger.warning(f"get_entity başarısız: {e}, dialogs'dan aranıyor...")
            # Alternatif: Dialoglardan bul
            channel = None
            async for dialog in client.iter_dialogs():
                if dialog.is_channel:
                    # ID karşılaştır (hem -100 prefix'li hem prefix'siz)
                    dialog_id_str = str(dialog.id).replace('-100', '')
                    channel_id_str = str(CHANNEL_USERNAME).replace('-100', '').replace('-', '')
                    
                    if dialog_id_str == channel_id_str:
                        channel = dialog.entity
                        logger.info(f"✅ Kanal bulundu (dialogs): {dialog.title}")
                        break
            
            if not channel:
                raise Exception(f"Kanal bulunamadı: {CHANNEL_USERNAME}")
        
        # Timezone-aware cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS)
        
        logger.info(f"📢 Kanal: {channel.title}")
        logger.info(f"⏰ İnaktiflik süresi: {INACTIVE_DAYS} gün")
        logger.info(f"📆 Kontrol tarihi: {cutoff_date.strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info(f"⚠️ Uyarı sistemi: {'Aktif' if WARNING_ENABLED else 'Kapalı'}")
        if WARNING_ENABLED:
            logger.info(f"   Uyarı zamanı: {WARNING_DAYS_BEFORE} gün önce")
        logger.info(f"📊 Rapor sistemi: {'Aktif' if REPORT_ENABLED else 'Kapalı'}")
        
        if WHITELIST_USERNAMES or WHITELIST_USER_IDS:
            logger.info(f"🛡️ Whitelist aktif:")
            if WHITELIST_USERNAMES:
                logger.info(f"  • Username: {', '.join(['@' + u for u in WHITELIST_USERNAMES])}")
            if WHITELIST_USER_IDS:
                logger.info(f"  • User ID: {', '.join([str(u) for u in WHITELIST_USER_IDS])}")
        
        whitelist = load_whitelist()
        if whitelist.get('usernames') or whitelist.get('user_ids'):
            logger.info(f"🛡️ Whitelist (Dosya):")
            if whitelist.get('usernames'):
                logger.info(f"  • Username: {', '.join(whitelist['usernames'])}")
            if whitelist.get('user_ids'):
                logger.info(f"  • User ID: {', '.join([str(u) for u in whitelist['user_ids']])}")
        
        logger.info("")
        
        user_data = load_user_data()
        logger.info(f"📂 {len(user_data)} kullanıcı verisi yüklendi\n")
        
        active_users_data, total_messages, topic_stats = await scan_all_messages_comprehensive(
            client, channel, cutoff_date
        )
        
        for user_id, data in active_users_data.items():
            # Eğer daha önce kayıt yoksa, first_seen ekle
            existing_data = user_data.get(str(user_id), {})
            
            user_data[str(user_id)] = {
                'last_message': data['last_message'].isoformat(),
                'topics': list(data['topics']),
                'message_count': data['message_count'],
                'first_seen': existing_data.get('first_seen', datetime.now(timezone.utc).isoformat()),
                'warnings_sent': existing_data.get('warnings_sent', [])
            }
        
        logger.info("\n👥 Kanal üyeleri alınıyor...")
        all_members = await client.get_participants(channel)
        logger.info(f"✅ Toplam {len(all_members)} üye\n")
        
        logger.info("🔍 İnaktif kullanıcılar tespit ediliyor...")
        removed = []
        skipped = []
        kept_active = []
        whitelisted_users = []
        warned_users = []
        
        for member in all_members:
            user_id = str(member.id)
            
            if member.bot:
                continue
            
            is_wl, wl_reason = is_whitelisted(member.id, member.username)
            if is_wl:
                whitelisted_users.append({
                    'name': member.first_name or 'İsimsiz',
                    'username': member.username,
                    'id': member.id,
                    'reason': wl_reason
                })
                logger.info(f"🛡️ Korumalı: {member.first_name or 'İsimsiz'} (@{member.username or 'no_username'}) - {wl_reason}")
                continue
            
            user_info = user_data.get(user_id)
            is_inactive = False
            should_warn = False
            reason = ""
            days_inactive = 0
            
            if not user_info:
                # Hiç mesaj atmamış - yeni kayıt olarak ekle
                user_data[user_id] = {
                    'first_seen': datetime.now(timezone.utc).isoformat(),
                    'last_message': None,
                    'topics': [],
                    'message_count': 0,
                    'warnings_sent': []
                }
                logger.info(f"📝 Yeni kullanıcı kaydedildi: {member.first_name or 'İsimsiz'} (@{member.username or 'no_username'})")
                continue
            else:
                try:
                    if isinstance(user_info, dict):
                        last_message_str = user_info.get('last_message')
                        first_seen_str = user_info.get('first_seen')
                        topics_str = ", ".join(user_info.get('topics', []))
                        msg_count = user_info.get('message_count', 0)
                        warnings_sent = user_info.get('warnings_sent', [])
                        
                        # İlk görülme tarihi yoksa şimdi ekle
                        if not first_seen_str:
                            first_seen_str = datetime.now(timezone.utc).isoformat()
                            user_data[user_id]['first_seen'] = first_seen_str
                        
                        first_seen = datetime.fromisoformat(first_seen_str)
                        if first_seen.tzinfo is None:
                            first_seen = first_seen.replace(tzinfo=timezone.utc)
                        
                        # İlk görülmeden beri kaç gün geçti?
                        days_since_first_seen = (datetime.now(timezone.utc) - first_seen).days
                        
                        # Eğer INACTIVE_DAYS'den yeni ise atma
                        if days_since_first_seen < INACTIVE_DAYS:
                            logger.info(f"⏳ Yeni kullanıcı: {member.first_name or 'İsimsiz'} (@{member.username or 'no_username'}) - {days_since_first_seen} gün önce ilk görüldü")
                            continue
                        
                        # Son mesaj kontrolü
                        if not last_message_str:
                            days_inactive = days_since_first_seen
                            is_inactive = True
                            reason = f"{days_inactive} gün içinde hiç mesaj atmamış"
                        else:
                            last_active = datetime.fromisoformat(last_message_str)
                            if last_active.tzinfo is None:
                                last_active = last_active.replace(tzinfo=timezone.utc)
                            
                            days_inactive = (datetime.now(timezone.utc) - last_active).days
                            
                            if last_active < cutoff_date:
                                is_inactive = True
                                reason = f"{days_inactive} gün önce son mesaj"
                            else:
                                # Aktif kullanıcı
                                kept_active.append({
                                    'name': member.first_name or 'İsimsiz',
                                    'username': member.username,
                                    'days_ago': days_inactive,
                                    'topics': topics_str,
                                    'message_count': msg_count
                                })
                                
                                # Uyarı kontrolü (aktif ama yaklaşıyor)
                                days_remaining = INACTIVE_DAYS - days_inactive
                                if WARNING_ENABLED and days_remaining <= WARNING_DAYS_BEFORE and days_remaining > 0:
                                    # Bu gün uyarı gönderildi mi kontrol et
                                    today = datetime.now(timezone.utc).date().isoformat()
                                    if today not in warnings_sent:
                                        should_warn = True
                                        warnings_sent.append(today)
                                        user_data[user_id]['warnings_sent'] = warnings_sent
                    else:
                        # Eski format - string olarak kayıtlı
                        last_message_str = user_info
                        last_active = datetime.fromisoformat(last_message_str)
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(tzinfo=timezone.utc)
                        
                        days_inactive = (datetime.now(timezone.utc) - last_active).days
                        
                        if last_active < cutoff_date:
                            is_inactive = True
                            reason = f"{days_inactive} gün önce son mesaj"
                            
                except Exception as e:
                    is_inactive = True
                    reason = f"Tarih hatası: {e}"
            
            # Uyarı gönder
            if should_warn:
                days_remaining = INACTIVE_DAYS - days_inactive
                warning_sent = await send_warning_to_user(
                    client, channel, member, 
                    days_inactive, days_remaining
                )
                if warning_sent:
                    warned_users.append({
                        'name': member.first_name or 'İsimsiz',
                        'username': member.username,
                        'days_inactive': days_inactive,
                        'days_remaining': days_remaining
                    })
                await asyncio.sleep(2)  # Rate limit
            
            # Kullanıcıyı çıkar
            if is_inactive:
                try:
                    await client.kick_participant(channel, member.id)
                    
                    removed.append({
                        'id': member.id,
                        'name': member.first_name or 'İsimsiz',
                        'username': member.username,
                        'reason': reason
                    })
                    
                    user_data.pop(user_id, None)
                    
                    logger.info(f"❌ Çıkarıldı: {member.first_name or 'İsimsiz'} (@{member.username or 'no_username'}) - {reason}")
                    
                    await asyncio.sleep(5)  # Rate limit koruması
                    
                except FloodWaitError as e:
                    logger.warning(f"⏳ Rate limit! {e.seconds} saniye bekleniyor...")
                    await asyncio.sleep(e.seconds)
                    try:
                        await client.kick_participant(channel, member.id)
                        removed.append({
                            'id': member.id,
                            'name': member.first_name or 'İsimsiz',
                            'username': member.username,
                            'reason': reason
                        })
                        user_data.pop(user_id, None)
                        logger.info(f"❌ Çıkarıldı (retry): {member.first_name or 'İsimsiz'} (@{member.username or 'no_username'})")
                    except Exception as retry_err:
                        logger.error(f"⚠️ Retry başarısız: {retry_err}")
                        skipped.append({
                            'name': member.first_name or 'İsimsiz',
                            'username': member.username,
                            'error': f"FloodWait: {str(retry_err)}"
                        })
                except Exception as e:
                    error_msg = str(e)
                    skipped.append({
                        'name': member.first_name or 'İsimsiz',
                        'username': member.username,
                        'error': error_msg
                    })
                    logger.warning(f"⚠️ Çıkarılamadı: {member.first_name or 'İsimsiz'} - {error_msg}")
        
        save_user_data(user_data)
        
        # Günlük rapor gönder
        if REPORT_ENABLED:
            report_data = {
                'total_members': len(all_members),
                'active_users': len(kept_active),
                'warned_users': len(warned_users),
                'whitelisted_users': len(whitelisted_users),
                'removed_users': len(removed),
                'skipped_users': len(skipped),
                'total_messages': total_messages,
                'topic_count': len(topic_stats),
                'warned_list': warned_users,
                'removed_list': removed
            }
            await send_daily_report(client, channel, report_data)
        
        logger.info("\n" + "="*70)
        logger.info("📊 DETAYLI ÖZET RAPOR")
        logger.info("="*70)
        logger.info(f"👥 Toplam üye: {len(all_members)}")
        logger.info(f"✅ Aktif kullanıcı: {len(kept_active)}")
        logger.info(f"⚠️ Uyarı gönderilen: {len(warned_users)}")
        logger.info(f"🛡️ Korumalı kullanıcı: {len(whitelisted_users)}")
        logger.info(f"❌ Çıkarılan kullanıcı: {len(removed)}")
        logger.info(f"⚠️ Çıkarılamayan: {len(skipped)}")
        logger.info(f"📨 Taranan mesaj: {total_messages}")
        logger.info(f"📝 Topic sayısı: {len(topic_stats)}")
        logger.info("="*70)
        
        # Uyarı gönderilenleri göster
        if warned_users:
            logger.info(f"\n⚠️ Uyarı Gönderilen Kullanıcılar ({len(warned_users)} kişi):")
            for user in warned_users[:20]:
                logger.info(f"  • {user['name']} (@{user['username'] or 'no_username'}) - {user['days_inactive']} gün inaktif, {user['days_remaining']} gün kaldı")
            if len(warned_users) > 20:
                logger.info(f"  ... ve {len(warned_users) - 20} kişi daha")
        
        if whitelisted_users:
            logger.info(f"\n🛡️ Korumalı Kullanıcılar ({len(whitelisted_users)} kişi):")
            for user in whitelisted_users[:20]:
                logger.info(f"  • {user['name']} (@{user['username'] or 'no_username'}) - {user['reason']}")
            if len(whitelisted_users) > 20:
                logger.info(f"  ... ve {len(whitelisted_users) - 20} kişi daha")
        
        if kept_active:
            logger.info("\n✅ Aktif Kullanıcılar (ilk 10):")
            for user in sorted(kept_active, key=lambda x: x['days_ago'])[:10]:
                logger.info(f"  • {user['name']} (@{user['username'] or 'no_username'}) - Son mesaj: {user['days_ago']} gün önce")
        
        if removed:
            logger.info("\n❌ Çıkarılan Kullanıcılar (ilk 10):")
            for user in removed[:10]:
                logger.info(f"  • {user['name']} (@{user['username'] or 'no_username'}) - {user['reason']}")
            if len(removed) > 10:
                logger.info(f"  ... ve {len(removed) - 10} kişi daha")
        
        if skipped:
            logger.info("\n⚠️ Çıkarılamayan Kullanıcılar:")
            for user in skipped[:5]:
                logger.info(f"  • {user['name']} - {user['error']}")
        
    except Exception as e:
        logger.error(f"\n❌ HATA: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        await client.disconnect()
        logger.info(f"\n✅ Kontrol tamamlandı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")

async def start_command_listener():
    """Komut dinleyici başlat"""
    client = TelegramClient('session', API_ID, API_HASH)
    await client.start(phone=PHONE)
    
    # Kanal entity
    try:
        if str(CHANNEL_USERNAME).startswith('@'):
            channel = await client.get_entity(CHANNEL_USERNAME)
        else:
            channel_id = int(str(CHANNEL_USERNAME).replace('-100', ''))
            channel = await client.get_entity(f'-100{channel_id}')
    except:
        logger.error("❌ Kanal bulunamadı, komut dinleyici başlatılamıyor")
        return
    
    @client.on(events.NewMessage(chats=channel, pattern=r'^/'))
    async def command_handler(event):
        await handle_command(client, event, channel)
    
    logger.info("🤖 Komut dinleyici başlatıldı")
    
    # Client'ı çalışır durumda tut
    await client.run_until_disconnected()

def start_scheduler():
    """Otomatik scheduler başlat"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    scheduler = AsyncIOScheduler(timezone=TIMEZONE, event_loop=loop)
    
    scheduler.add_job(
        check_and_kick_inactive, 
        'cron', 
        hour=CHECK_HOUR, 
        minute=CHECK_MINUTE
    )
    
    logger.info("="*70)
    logger.info("⏰ OTOMATIK KONTROL SCHEDULER BAŞLATILDI")
    logger.info("="*70)
    logger.info(f"⏰ Her gün saat {CHECK_HOUR:02d}:{CHECK_MINUTE:02d}'da kontrol yapılacak ({TIMEZONE})")
    logger.info(f"📢 Kanal: {CHANNEL_USERNAME}")
    logger.info(f"⏳ İnaktiflik süresi: {INACTIVE_DAYS} gün")
    logger.info(f"⚠️ Uyarı sistemi: {'Aktif' if WARNING_ENABLED else 'Kapalı'}")
    logger.info(f"📊 Rapor sistemi: {'Aktif' if REPORT_ENABLED else 'Kapalı'}")
    if ADMIN_USER_IDS:
        logger.info(f"👑 Admin sayısı: {len(ADMIN_USER_IDS)}")
    logger.info("="*70 + "\n")
    
    if os.getenv('RUN_ON_START', 'false').lower() == 'true':
        logger.info("🚀 İlk kontrol hemen başlatılıyor...")
        loop.run_until_complete(check_and_kick_inactive())
    
    scheduler.start()
    
    # Komut listener'ı başlat (eğer admin varsa)
    if ADMIN_USER_IDS:
        logger.info("🤖 Komut dinleyici başlatılıyor...")
        loop.create_task(start_command_listener())
    
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n⏹️ Program durduruldu")

if __name__ == "__main__":
    import sys
    
    if not all([API_ID, API_HASH, PHONE, CHANNEL_USERNAME]):
        logger.error("❌ Eksik environment variables! API_ID, API_HASH, PHONE, CHANNEL_USERNAME gerekli.")
        sys.exit(1)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'manual':
        logger.info("🔧 Manuel kontrol modu\n")
        asyncio.run(check_and_kick_inactive())
    else:
        start_scheduler()
