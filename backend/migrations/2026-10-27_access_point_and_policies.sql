-- Chay 1 lan trong Supabase SQL Editor truoc khi test access_policies enforcement.
--
-- SUA LAI (27/10, lan chay dau bi loi 42804): access_points.device_id la FK uuid ->
-- devices.id theo DUNG schema goc (KHONG phai chuoi nhu "esp32_test_01") - khong doi kieu
-- cot nua. Thay vao do tao 1 ban ghi trong bang `devices` dai dien ESP32 that, luu doan
-- device_id dung trong topic MQTT (access/{device_id}/...) vao cot devices.mqtt_topic,
-- roi tro access_points.device_id ve dung uuid do.

-- status KHONG truyen - de mac dinh "offline" (hop le). Cot status chi mang tinh thong
-- tin/giam sat, logic access_control khong doc den, nen khong anh huong gi.
-- direction = 'bidirectional' (dung dinh nghia constraint access_points_direction_check:
-- CHECK (direction IN ('entry','exit','bidirectional')) - cua chinh dung ca ra lan vao).
WITH dev AS (
  INSERT INTO devices (name, location, type, mqtt_topic)
  VALUES ('ESP32 AS608 Test', 'Cua chinh', 'access_controller', 'esp32_test_01')
  RETURNING id
), ap AS (
  INSERT INTO access_points (name, device_id, direction, allowed_methods, is_active)
  SELECT 'Cua chinh', dev.id, 'bidirectional', ARRAY['face', 'fingerprint'], true
  FROM dev
  RETURNING id
)
-- Cap chinh sach mac dinh gio hanh chinh T2-T6 7h-19h cho tat ca nhan vien active.
-- Doi allowed_days/allowed_time_start/allowed_time_end lai cho tung nhan vien sau nay
-- bang UPDATE rieng tren access_policies neu can khac gio hanh chinh (hoac qua UI dashboard
-- moi them o trang chi tiet nhan vien).
INSERT INTO access_policies (employee_id, access_point_id, allowed_days, allowed_time_start, allowed_time_end, is_active)
SELECT e.id, ap.id, ARRAY['mon', 'tue', 'wed', 'thu', 'fri'], '07:00', '19:00', true
FROM employees e, ap
WHERE e.status = 'active';
