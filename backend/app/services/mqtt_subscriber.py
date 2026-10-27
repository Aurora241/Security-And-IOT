"""
Lang nghe su kien enroll van tay tu ESP32 qua MQTT, luu vao Supabase.

Topic ESP32 publish: access/{device_id}/enroll
Payload: {"employee_code": "NV001", "credential_type": "fingerprint", "slot_id": 1}

Topic backend publish lai (ket qua): access/{device_id}/enroll_ack
Payload: {"success": true/false, "message": "..."}

Topic ESP32 publish tien trinh (buoc chup lan 1/2...): access/{device_id}/enroll_progress
Payload: {"step": "...", "message": "..."} - backend giu ban ghi moi nhat trong RAM,
web poll qua GET /devices/{device_id}/enroll-progress de hien thi nhu tren Serial Monitor.

Topic ESP32 publish ket qua verify: access/{device_id}/verify_result
Payload: {"matched": true/false, "found_id": int, "confidence": int, "expected_slot_id": int}

Topic ESP32 publish heartbeat (moi 30s): access/{device_id}/heartbeat
Payload: {"status": "online", "rssi": int, "uptime_s": int} - cap nhat devices.status="online"
+ devices.last_seen=now() (tra cuu qua devices.mqtt_topic == device_id)

Topic Last Will (broker tu gui ho khi ESP32 mat ket noi dot ngot): access/{device_id}/lwt
Payload: {"status": "offline"} - cap nhat devices.status="offline", GIU NGUYEN last_seen
(last_seen phai la lan online gan nhat, khong phai luc phat hien mat ket noi)
"""
import json
import logging
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.api.v1.access_credentials import DuplicateCredentialError, enroll_credential_core
from app.core.config import settings
from app.core.supabase_client import get_supabase
from app.services import access_control

logger = logging.getLogger("mqtt_subscriber")

ENROLL_TOPIC_FILTER = "access/+/enroll"
PROGRESS_TOPIC_FILTER = "access/+/enroll_progress"
VERIFY_RESULT_TOPIC_FILTER = "access/+/verify_result"
HEARTBEAT_TOPIC_FILTER = "access/+/heartbeat"
LWT_TOPIC_FILTER = "access/+/lwt"

_client: mqtt.Client | None = None
_progress_state: dict[str, dict] = {}
_verify_state: dict[str, dict] = {}
# Ngu canh cua lenh verify dang cho ket qua tu ESP32 - can employee_id/access_point_id de
# cham access_policies ngay khi verify_result ve, vi payload ESP32 tra ve khong mang employee_id.
_pending_verify: dict[str, dict] = {}


def _get_employee_id_by_code(code: str) -> str | None:
    result = get_supabase().table("employees").select("id").eq("code", code).execute()
    if not result.data:
        return None
    return result.data[0]["id"]


def _publish_ack(client: mqtt.Client, device_id: str, ack: dict) -> None:
    client.publish(f"access/{device_id}/enroll_ack", json.dumps(ack), qos=1)


def _handle_enroll_message(client: mqtt.Client, device_id: str, payload: dict) -> None:
    employee_code = payload.get("employee_code")
    cred_type = payload.get("credential_type")
    slot_id = payload.get("slot_id")

    if not employee_code or not cred_type or slot_id is None:
        _publish_ack(client, device_id, {
            "success": False,
            "message": "Thieu employee_code/credential_type/slot_id trong payload",
        })
        return

    employee_id = _get_employee_id_by_code(employee_code)
    if employee_id is None:
        _publish_ack(client, device_id, {
            "success": False,
            "message": f"Khong tim thay nhan vien voi ma '{employee_code}'",
        })
        return

    try:
        credential = enroll_credential_core(
            employee_id, cred_type, {"fingerprint_slot_id": slot_id, "device_id": device_id}
        )
        _publish_ack(client, device_id, {
            "success": True,
            "message": "Da luu credential thanh cong",
            "credential_id": credential["id"],
            "employee_code": employee_code,
            "slot_id": slot_id,
        })
        logger.info("Enroll thanh cong: %s slot %s -> employee %s", cred_type, slot_id, employee_code)
    except DuplicateCredentialError as e:
        _publish_ack(client, device_id, {"success": False, "message": str(e)})
    except Exception as e:  # noqa: BLE001 - can bat het loi de luon tra ack ve thiet bi
        logger.exception("Loi khi luu credential tu MQTT")
        _publish_ack(client, device_id, {"success": False, "message": f"Loi server: {e}"})


def _on_connect(client, userdata, flags, reason_code, properties=None):
    logger.info("MQTT subscriber da ket noi broker %s:%s, rc=%s",
                settings.mqtt_broker_host, settings.mqtt_broker_port, reason_code)
    client.subscribe(ENROLL_TOPIC_FILTER, qos=1)
    client.subscribe(PROGRESS_TOPIC_FILTER, qos=0)
    client.subscribe(VERIFY_RESULT_TOPIC_FILTER, qos=1)
    client.subscribe(HEARTBEAT_TOPIC_FILTER, qos=0)
    client.subscribe(LWT_TOPIC_FILTER, qos=1)


def _update_device_status(device_id: str, status: str, touch_last_seen: bool) -> None:
    data = {"status": status}
    if touch_last_seen:
        data["last_seen"] = datetime.now(timezone.utc).isoformat()
    try:
        get_supabase().table("devices").update(data).eq("mqtt_topic", device_id).execute()
    except Exception:  # noqa: BLE001 - chay trong thread MQTT, khong de loi Supabase lam chet thread
        logger.exception("Khong cap nhat duoc devices.status cho %s", device_id)


def _on_message(client, userdata, msg):
    parts = msg.topic.split("/")  # access/{device_id}/enroll hoac /enroll_progress
    if len(parts) != 3:
        return
    device_id, leaf = parts[1], parts[2]

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Payload MQTT khong phai JSON hop le tren topic %s", msg.topic)
        return

    if leaf == "enroll_progress":
        payload["received_at"] = time.time()
        _progress_state[device_id] = payload
        return

    if leaf == "enroll":
        _progress_state[device_id] = {"step": "saving", "message": "Da luu tren cam bien, dang dong bo len he thong..."}
        _handle_enroll_message(client, device_id, payload)
        return

    if leaf == "verify_result":
        payload["received_at"] = time.time()

        pending = _pending_verify.pop(device_id, None)
        if pending is not None:
            decision = access_control.evaluate_and_log(
                employee_id=pending["employee_id"],
                access_point_id=pending["access_point_id"],
                method="fingerprint",
                matched=bool(payload.get("matched")),
                confidence=payload.get("confidence"),
            )
            payload["result"] = decision["result"]
            if decision["result"] == "accepted":
                publish_cmd(device_id, {"action": "open_door"})
        else:
            logger.warning("verify_result tu %s nhung khong co pending context (co the do cmd cu/timeout)", device_id)

        _verify_state[device_id] = payload
        return

    if leaf == "heartbeat":
        _update_device_status(device_id, "online", touch_last_seen=True)
        return

    if leaf == "lwt":
        _update_device_status(device_id, payload.get("status", "offline"), touch_last_seen=False)
        return


def get_progress(device_id: str) -> dict:
    return _progress_state.get(device_id, {"step": "idle", "message": ""})


def reset_progress(device_id: str) -> None:
    _progress_state[device_id] = {"step": "cmd_sent", "message": "Da gui lenh, cho ESP32 phan hoi..."}


def get_verify_result(device_id: str) -> dict:
    return _verify_state.get(device_id, {"status": "pending"})


def reset_verify_result(device_id: str) -> None:
    _verify_state.pop(device_id, None)


def set_pending_verify(device_id: str, employee_id: str, access_point_id: str) -> None:
    """Goi ngay truoc khi gui lenh verify_fingerprint xuong ESP32, de luu lai danh tinh
    dang cho xac thuc - verify_result tu thiet bi khong mang employee_id nen phai tra cuu lai."""
    _pending_verify[device_id] = {"employee_id": employee_id, "access_point_id": access_point_id}


def start() -> None:
    global _client
    _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="backend_enroll_subscriber")
    _client.on_connect = _on_connect
    _client.on_message = _on_message
    _client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=60)
    _client.loop_start()
    logger.info("MQTT subscriber thread da khoi dong")


def stop() -> None:
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()


def publish_cmd(device_id: str, payload: dict) -> None:
    """Gui lenh xuong thiet bi qua topic access/{device_id}/cmd (vd: bat dau enroll van tay)."""
    if _client is None:
        raise RuntimeError("MQTT client chua khoi dong")
    _client.publish(f"access/{device_id}/cmd", json.dumps(payload), qos=1)
