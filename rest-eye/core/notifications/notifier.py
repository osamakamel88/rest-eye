import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import httpx
from ..config import config

class AlertNotifier:
    """
    Automated Instant Incident Dispatcher supporting:
    1. Telegram Bot (Instant photo + 8s video clip message)
    2. WhatsApp Cloud API / Webhooks
    """
    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        whatsapp_url: Optional[str] = None,
        whatsapp_token: Optional[str] = None,
        whatsapp_phone: Optional[str] = None
    ):
        self.telegram_token = telegram_token or config.telegram_bot_token
        self.telegram_chat_id = telegram_chat_id or config.telegram_chat_id
        self.whatsapp_url = whatsapp_url or config.whatsapp_api_url
        self.whatsapp_token = whatsapp_token or config.whatsapp_token
        self.whatsapp_phone = whatsapp_phone or config.whatsapp_phone_number

    async def send_telegram_alert(
        self,
        title: str,
        message: str,
        photo_path: Optional[Path] = None,
        video_path: Optional[Path] = None,
        token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Sends an instant formatted alert to a Telegram Chat / Channel"""
        bot_token = token or self.telegram_token
        target_chat = chat_id or self.telegram_chat_id

        if not bot_token or not target_chat:
            return False, "Telegram Bot Token or Chat ID is not configured."

        caption = f"🚨 *REST-EYE SENTRY ALERT*\n\n*{title}*\n\n{message}\n\n_Recode Developments AI Sentry_"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Send Video if available
                if video_path and video_path.exists():
                    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
                    with open(video_path, "rb") as f:
                        files = {"video": (video_path.name, f, "video/mp4")}
                        data = {"chat_id": target_chat, "caption": caption, "parse_mode": "Markdown"}
                        res = await client.post(url, data=data, files=files)
                        if res.status_code == 200:
                            return True, "تم إرسال تنبيه الفيديو بنجاح على تليجرام"
                        else:
                            print(f"[Notifier] Telegram video failed: {res.text}")

                # 2. Fallback to Photo if available
                if photo_path and photo_path.exists():
                    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                    with open(photo_path, "rb") as f:
                        files = {"photo": (photo_path.name, f, "image/jpeg")}
                        data = {"chat_id": target_chat, "caption": caption, "parse_mode": "Markdown"}
                        res = await client.post(url, data=data, files=files)
                        if res.status_code == 200:
                            return True, "تم إرسال لقطة التنبيه بنجاح على تليجرام"

                # 3. Fallback to Text message
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {"chat_id": target_chat, "text": caption, "parse_mode": "Markdown"}
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return True, "تم إرسال رسالة التنبيه بنجاح على تليجرام"
                return False, f"Telegram API Error: {res.text}"

        except Exception as e:
            print(f"[Notifier] Telegram dispatch exception: {e}")
            return False, str(e)

    async def send_whatsapp_alert(
        self,
        title: str,
        message: str,
        video_url: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Dispatches an alert to WhatsApp Cloud API / Webhook"""
        target_phone = phone or self.whatsapp_phone
        if not self.whatsapp_url or not target_phone:
            return False, "WhatsApp API URL or Phone is not configured."

        payload = {
            "phone": target_phone,
            "title": title,
            "body": message,
            "video_url": video_url,
            "source": "REST-EYE"
        }
        headers = {}
        if self.whatsapp_token:
            headers["Authorization"] = f"Bearer {self.whatsapp_token}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(self.whatsapp_url, json=payload, headers=headers)
                if res.status_code in [200, 201, 202]:
                    return True, "تم إرسال التنبيه إلى الواتساب بنجاح"
                return False, f"WhatsApp API Error: {res.text}"
        except Exception as e:
            return False, str(e)

    def dispatch_incident(
        self,
        incident_type: str,
        camera_name: str,
        zone_name: str,
        person_id: int,
        dwell_sec: float,
        photo_path: Optional[Path] = None,
        video_path: Optional[Path] = None,
        video_url: Optional[str] = None
    ):
        """Asynchronously dispatches alerts across configured channels"""
        title = f"مخالفة: {incident_type}"
        msg = (
            f"📹 *الكاميرا:* {camera_name}\n"
            f"📍 *المنطقة:* {zone_name}\n"
            f"👤 *رقم الموظف:* #{person_id}\n"
            f"⏱️ *مدة الحركة:* {dwell_sec:.1f} ثانية"
        )
        # Run in background without blocking video processing
        try:
            async def _do_dispatch():
                tasks = [self.send_telegram_alert(title, msg, photo_path, video_path)]
                if video_url:
                    tasks.append(self.send_whatsapp_alert(title, msg, video_url))
                await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run(_do_dispatch())
        except Exception as e:
            print(f"[Notifier] Background alert dispatch error: {e}")

alert_notifier = AlertNotifier()
