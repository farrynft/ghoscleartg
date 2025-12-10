from telethon import TelegramClient
import asyncio

print("="*60)
print("📱 TELEGRAM SESSION OLUŞTURUCU")
print("="*60)
print("Bu script Telegram session dosyası oluşturur.")
print("session.session dosyası oluşturulduktan sonra Railway'e yükleyin.\n")

api_id = int(input('API_ID: '))
api_hash = input('API_HASH: ')
phone = input('PHONE (+905XXXXXXXXX): ')

async def main():
    client = TelegramClient('session', api_id, api_hash)
    
    print("\n📞 Telegram'a bağlanılıyor...")
    await client.start(phone=phone)
    
    print("\n✅ Session başarıyla oluşturuldu!")
    print("📁 Dosya: session.session")
    print("\n🚀 Sonraki adımlar:")
    print("1. session.session dosyasını Railway'e yükle")
    print("2. Railway Volume mount path: /app/data")
    print("3. Dosyayı /app/data/session.session olarak yükle")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
