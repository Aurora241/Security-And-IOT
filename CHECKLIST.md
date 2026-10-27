# Checklist test Access Control (27/10/2026)

Trạng thái lúc tạo file này: backend + dashboard đã chạy thông toàn bộ pipeline với dữ liệu thật
(verify khuôn mặt NV001 bằng ảnh có sẵn → ra đúng `accepted`). Còn thiếu test tay thật và phần cứng.

## 0. Khởi động lại server

Hai server này chạy nền trong phiên Claude Code trước, đã tắt khi đóng phiên — khởi động lại:

```bash
cd "C:\Users\Admin\Security and IOT\backend"
python -m uvicorn app.main:app --port 8001
```

```bash
cd "C:\Users\Admin\Security and IOT\frontend"
npm run dev
```

Dashboard: http://localhost:5173 — Trang demo cũ (vẫn còn): http://localhost:8001/demo

Mỗi lần sửa code backend: tắt hẳn tiến trình `uvicorn` cũ rồi chạy lại lệnh trên (không dùng `--reload`,
đã từng không đáng tin trong môi trường này). Tìm đúng PID qua
`Get-CimInstance Win32_Process -Filter "name='python.exe'"` rồi `Stop-Process -Id <PID>`, không kill
theo tên `python.exe` (quá rộng, dễ bị chặn).

## 1. Vân tay (cần cắm ESP32 qua USB + nạp lại firmware mới nhất)

- [ ] Nạp `firmware/esp32_as608_test/esp32_as608_test.ino` (đã gồm servo + chống trùng vân tay +
      heartbeat/LWT, compile OK 81% flash)
- [ ] Enroll vân tay cho **NV001** qua dashboard (`/employees/<NV001-id>` → "Đăng ký vân tay (qua ESP32)")
- [ ] Thử enroll **trùng đúng ngón đó** cho **NV002** → phải bị ESP32 từ chối (test chống trùng vân tay)
- [ ] Verify vân tay NV001 → phải ra **ACCEPTED** (đang trong giờ hành chính T2-T6, 7h-19h theo policy)

## 2. Khuôn mặt (qua webcam thật trên dashboard)

- [ ] Enroll khuôn mặt NV002 qua webcam
- [ ] Verify khuôn mặt NV001 qua webcam thật (đã test bằng ảnh có sẵn, giờ test qua webcam thật)
- [ ] Verify khuôn mặt NV002 qua webcam thật

## 3. Test REJECTED

- [ ] Vào trang chi tiết NV001, bấm "Sửa" chính sách, đổi khung giờ sang lúc **không phải** giờ đang test
- [ ] Verify lại (mặt hoặc vân tay) → phải ra **REJECTED**
- [ ] Đổi policy về lại đúng giờ cũ (T2-T6, 07:00-19:00) sau khi test xong

## 4. Test UNKNOWN

- [ ] Verify bằng khuôn mặt của người **chưa đăng ký** → phải ra **UNKNOWN**
- [ ] Verify bằng vân tay của người **chưa đăng ký** → phải ra **UNKNOWN**

## 5. Kiểm tra Nhật ký ra vào

- [ ] Vào `/access-log`, xác nhận từng lượt test ở trên đều có ghi lại đúng (nhân viên, phương thức,
      độ tin cậy, kết quả ACCEPTED/REJECTED/UNKNOWN)

## 6. Khi đã mua servo/relay

- [ ] Nối dây theo đúng sơ đồ trong comment đầu file `esp32_as608_test.ino` (servo dùng **nguồn 5V
      riêng**, không lấy từ cổng USB nạp code — tránh ESP32 bị reset khi servo giật dòng)
- [ ] Test mở cửa thật khi verify ra ACCEPTED (servo quay 90°, tự khoá lại sau 4 giây)

## Ghi chú

- NV001 id: `78c49bb3-d1e3-483c-8e8b-aba483ab635c`
- NV002 id: `88f46017-15e3-47d1-ae04-5a48a7f6af34`
- access_policies hiện có: NV001 + NV002 đều được T2-T6, 07:00-19:00 (chỉnh qua dashboard, không cần SQL nữa)
- Nếu thấy lỗi lạ kiểu "Failed to fetch" từ dashboard: thử hard reload trang trước (F5) — có thể chỉ là
  console log cũ còn sót lại từ lần lỗi trước, không phải bug mới
