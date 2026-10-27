"""
Gui lenh MQTT bat coi dien tu cho module Alarm - dung 1 client rieng, KET NOI NGAN HAN
(connect -> publish -> disconnect) cho moi lenh, KHONG dung chung client thuong truc cua
mqtt_subscriber.py (file do thuoc Access Control, khong duoc dong vao).

Hop ly vi tan suat gui lenh coi rat thap (vai lan/ngay khi co xam nhap thuc), khac voi
Access Control can giu ket noi song de nhan heartbeat/enroll_progress lien tuc.

Topic rieng cho Alarm: alarm/{device_id}/cmd (KHAC namespace access/{device_id}/cmd cua
Access Control, de firmware ESP32-coi sau nay subscribe dung topic cua minh).
"""
import json
import logging

import paho.mqtt.client as mqtt

from app.core.config import settings

logger = logging.getLogger("alarm_mqtt")

CONNECT_TIMEOUT_SECONDS = 3


def publish_cmd(device_id: str, payload: dict) -> bool:
    """Tra ve True neu gui thanh cong, False neu khong ket noi duoc broker (khong raise -
    mot lenh coi gui hong khong duoc chan viec ghi alarm_events, event van phai duoc luu)."""
    client = mqtt.Client()
    try:
        client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=CONNECT_TIMEOUT_SECONDS)
        client.loop_start()
        client.publish(f"alarm/{device_id}/cmd", json.dumps(payload), qos=1)
        client.loop_stop()
        client.disconnect()
        return True
    except Exception:
        logger.warning("Khong gui duoc lenh coi MQTT xuong device %s", device_id, exc_info=True)
        return False
