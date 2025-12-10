from telethon import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest
from datetime import datetime, timedelta
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
                    
                    if user_id not in active_users:
                        active_users[user_id] = {
                            'last_message': message.date,
                            'topics': set(),
                            'message_count': 0
                        }
                    
                    active_users[user_id]['topics'].add(topic_name)
                    active_users[user_id]['message_count'] += 1
                    
                    if message.date > active_users[user_id]['last_message']:
                        active_users[user_id]['last_message'] = message.date
                    
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
        
        channel = await client.get_entity(CHANNEL_USERNAME)
        cutoff_date = datetime.now() - timedelta(days=INACTIVE_DAYS)
        
        logger.info(f"📢 Kanal: {channel.title}")
        logger.info(f"⏰ İnaktiflik süresi: {INACTIVE_DAYS} gün")
        logger.info(f"📆 Kontrol tarihi: {cutoff_date.strftime('%d.%m.%Y %H:%M:%S')}")
        
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
            user_data[str(user_id)] = {
                'last_message': data['last_message'].isoformat(),
                'topics': list(data['topics']),
                'message_count': data['message_count']
            }
        
        logger.info("\n👥 Kanal üyeleri alınıyor...")
        all_members = await client.get_participants(channel)
        logger.info(f"✅ Toplam {len(all_members)} üye\n")
        
        logger.info("🔍 İnaktif kullanıcılar tespit ediliyor...")
        removed = []
        skipped = []
        kept_active = []
        whitelisted_users = []
        
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
            reason = ""
            
            if not user_info:
                is_inactive = True
                reason = "Hiç mesaj atmamış"
            else:
                try:
                    if isinstance(user_info, dict):
                        last_message_str = user_info['last_message']
                        topics_str = ", ".join(user_info.get('topics', []))
                        msg_count = user_info.get('message_count', 0)
                    else:
                        last_message_str = user_info
                        topics_str = "Bilinmiyor"
                        msg_count = 0
                    
                    last_active = datetime.fromisoformat(last_message_str)
                    
                    if last_active < cutoff_date:
                        is_inactive = True
                        days_ago = (datetime.now() - last_active).days
                        reason = f"{days_ago} gün önce son mesaj"
                    else:
                        days_ago = (datetime.now() - last_active).days
                        kept_active.append({
                            'name': member.first_name or 'İsimsiz',
                            'username': member.username,
                            'days_ago': days_ago,
                            'topics': topics_str,
                            'message_count': msg_count
                        })
                        
                except Exception as e:
                    is_inactive = True
                    reason = f"Geçersiz tarih: {e}"
            
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
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    error_msg = str(e)
                    skipped.append({
                        'name': member.first_name or 'İsimsiz',
                        'username': member.username,
                        'error': error_msg
                    })
                    logger.warning(f"⚠️ Çıkarılamadı: {member.first_name or 'İsimsiz'} - {error_msg}")
        
        save_user_data(user_data)
        
        logger.info("\n" + "="*70)
        logger.info("📊 DETAYLI ÖZET RAPOR")
        logger.info("="*70)
        logger.info(f"👥 Toplam üye: {len(all_members)}")
        logger.info(f"✅ Aktif kullanıcı: {len(kept_active)}")
        logger.info(f"🛡️ Korumalı kullanıcı: {len(whitelisted_users)}")
        logger.info(f"❌ Çıkarılan kullanıcı: {len(removed)}")
        logger.info(f"⚠️ Çıkarılamayan: {len(skipped)}")
        logger.info(f"📨 Taranan mesaj: {total_messages}")
        logger.info(f"📝 Topic sayısı: {len(topic_stats)}")
        logger.info("="*70)
        
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

def start_scheduler():
    """Otomatik scheduler başlat"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
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
    logger.info("="*70 + "\n")
    
    if os.getenv('RUN_ON_START', 'false').lower() == 'true':
        logger.info("🚀 İlk kontrol hemen başlatılıyor...")
        asyncio.get_event_loop().run_until_complete(check_and_kick_inactive())
    
    scheduler.start()
    
    try:
        asyncio.get_event_loop().run_forever()
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
