# TechService: báo giá, cảnh báo và email/Teams qua n8n

Module Odoo 17: `ts_techservice_n8n`. Workflow import: [techservice_email_teams_v2.json](n8n/techservice_email_teams_v2.json).
Workflow không chứa credential hoặc secret, mặc định chưa kích hoạt. Không cần tạo workflow trực tiếp qua MCP.

## Tính năng

- Dùng nút gửi báo giá hiện có để xếp hàng email đính kèm PDF và tin nhắn Teams riêng cho sale phụ trách ticket.
- Sao chép “Mô tả lỗi” (`product_error_note`) sang báo giá khi tạo. Có thể sửa trước khi gửi. File PDF thể hiện lỗi, ticket và serial tương ứng, kể cả khi xuất chung báo giá.
- Sau khi cả email và Teams được Microsoft chấp nhận, bắt đầu đếm 3 ngày làm việc. Giữ nguyên giờ gửi, bỏ thứ Bảy/Chủ nhật và các ngày nghỉ đã khai báo. Cron kiểm tra mỗi 15 phút.
- Chưa phản hồi: gửi nhắc một lần trên cả hai kênh, tạo activity và thông báo chatter cho người xử lý và quản lý phòng ban. Nhắc dùng đúng PDF đã gửi lần đầu.
- Ngừng nhắc khi đã ghi nhận phản hồi sale, khách đồng ý/từ chối, báo giá xác nhận/hủy/từ chối, hoặc ticket đóng/từ chối.
- SLA: cảnh báo khi bước đang xử lý đã quá deadline của cơ chế SLA hiện có. Một cảnh báo cho mỗi lượt bước.
- SO giao trả: cảnh báo khi ticket đến bước `step_wf1_product_delivery` mà chưa có số SO SAP trên ticket hoặc báo giá liên quan. Phạm vi này dành cho workflow sửa chữa tại DAT; không tự suy đoán hoàn thành từ ghi chú.
- Bộ lọc: trạng thái, bước, ngày tạo/tiếp nhận/hoàn thành, hạn SLA, quá hạn SLA, quá hạn báo giá, chưa có SO giao trả. Dùng các ô khách hàng/model/serial đã có.
- Giá dịch vụ: cấu hình model thiết bị + sản phẩm dịch vụ + dòng bảng giá DAT. Khi chọn dịch vụ trên báo giá TechService, lấy giá từ dòng đã ghép, đổi tiền tệ/UoM theo báo giá. Nút cập nhật Price List cũng tôn trọng cấu hình. Dòng sửa tay không bị cron đổi giá. Không tự thêm mọi loại dịch vụ vào báo giá.
- Phiếu báo giá tổng hợp tính cả linh kiện và phí dịch vụ, tránh bỏ phí dịch vụ khi đã có linh kiện.

## Cài Odoo

1. Đặt thư mục module vào addons path, khởi động lại Odoo, cập nhật Apps List.
2. Cài **TS TechService Alerts and n8n** cùng các dependency trong manifest. Không cần thay model/controller gốc.
3. Vào **Thiết lập → TechService n8n**: nhập production webhook HTTPS và token.
4. Vào **Helpdesk → Configuration → Giá dịch vụ theo model**, ghép dữ liệu theo công ty. Dòng bảng giá phải cùng công ty với cấu hình. Bảng giá bị archive sẽ không được sử dụng.
5. Kiểm tra sale trên ticket có **Work Email** là tài khoản Microsoft của sale. Người nhận cảnh báo quản lý lấy từ `department_id.manager_id.user_id`; cần thiết lập quản lý phòng ban.
6. Kiểm tra `web.base.url` là địa chỉ HTTPS TechService. Khai báo ngày nghỉ dạng `YYYY-MM-DD`, ngăn cách bằng dấu phẩy. Múi giờ lấy từ lịch làm việc công ty, mặc định Asia/Bangkok.

## Import n8n

1. Import `n8n/techservice_email_teams_v2.json` bằng **Import from File** vào workflow mới. Bản tương thích dùng HTTP Request 4.2 và IF 2.2; bản đầu dùng 4.5/2.3 khiến một số editor không nhận node và không vẽ kết nối. File `techservice_email_teams.json` cũng đã được cập nhật cùng nội dung.
2. Trên **TechService Webhook**, chọn credential **Header Auth**:
   - Header name: `X-TechService-Token`.
   - Value: cùng token đã nhập trong Odoo.
3. Trên mọi node Microsoft Graph, chọn cùng credential **OAuth2 API** của tài khoản Microsoft 365 gửi thông báo.
   - Grant type: Authorization Code, tài khoản công ty, đăng nhập người dùng (delegated).
   - Authorization URL: `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize`.
   - Access Token URL: `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token`.
   - Scope: `openid offline_access https://graph.microsoft.com/User.Read https://graph.microsoft.com/User.ReadBasic.All https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Chat.Create https://graph.microsoft.com/ChatMessage.Send`.
   - Khai báo OAuth Redirect URL do n8n hiển thị vào App Registration trên Entra. Dùng client ID/secret của app của bạn trong credential, không chèn secret vào JSON.
   - Cấp consent theo chính sách tenant, tài khoản gửi có mailbox và Teams hoạt động.
4. Publish/activate workflow. Copy **Production URL** từ Webhook vào cấu hình Odoo.
5. Dùng một báo giá kiểm thử có sale là tài khoản khác người gửi. Workflow tìm người nhận trong tenant bằng mail hoặc UPN; yêu cầu khớp đúng một người và không dùng guest.

Workflow tạo hoặc dùng lại chat one-on-one của tài khoản gửi và sale. Theo [Microsoft Graph Create chat](https://learn.microsoft.com/en-us/graph/api/chat-post?view=graph-rest-1.0), chat riêng đã tồn tại sẽ được trả về thay vì tạo một chat khác. Gửi chat dùng quyền delegated [ChatMessage.Send](https://learn.microsoft.com/en-us/graph/api/chatmessage-post?view=graph-rest-1.0).
Email gửi bằng [Graph sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0), Microsoft chấp nhận request không đồng nghĩa xác nhận người nhận đã nhận/đọc email.

## Theo dõi và phản hồi

- Trên báo giá, tab **Gửi báo giá và phản hồi** cho biết PDF, nội dung lỗi, hạn và nội dung phản hồi.
- Nhập phản hồi rồi bấm **Ghi nhận phản hồi sale**. Không tự duyệt/từ chối báo giá hoặc thay luồng nghiệp vụ khi chỉ ghi nhận một phản hồi.
- Reply email/Teams tự do chưa tự động được đọc; sale/người xử lý cần ghi nhận trên Odoo. Không gửi Zalo trong workflow này.
- Quản trị viên xem **Helpdesk → Configuration → Hàng đợi thông báo**. Email và Teams có trạng thái riêng.
- Nếu một kênh lỗi: kiểm tra execution n8n và Microsoft trước, sau đó bấm gửi lại đúng kênh lỗi. Không tự retry khi timeout vì Microsoft có thể đã nhận thông báo. Kênh thành công không bị gửi lại.
- Nút gửi bị khóa sau khi tạo lượt gửi, tránh xếp lại cả hai kênh. Nếu cần báo giá phiên bản mới, tạo báo giá mới bằng luồng nhân bản hiện có.
- Cron lấy tối đa 2 thông báo mỗi phút, khóa hàng bằng `FOR UPDATE SKIP LOCKED`. Có thể tăng tần suất/điều chỉnh số lượng sau khi đo tải và giới hạn thời gian worker.
- Không có cam kết exactly-once với Microsoft: lỗi worker/database sau khi API đã chấp nhận có thể để lại thông báo chưa được đánh dấu. Cần xem execution trước khi gửi lại.

## Kiểm thử

Các kiểm tra chạy được mà không cần Odoo:

```powershell
python -B ts_techservice_n8n/tests/test_business_days.py
node ts_techservice_n8n/tests/test_workflow.js
```

Kiểm thử tích hợp trên Odoo staging sau khi cài:

1. Gửi báo giá: email có PDF/mô tả lỗi; Teams đến đúng sale; hai hàng thành công; hạn chỉ bắt đầu khi cả hai hàng thành công.
2. Tạm làm một kênh lỗi: hàng kia vẫn gửi được; sửa credential và chỉ retry kênh lỗi.
3. Kiểm tra thời hạn: thứ Sáu + 3 ngày làm việc = thứ Tư tuần sau cùng giờ; ngày nghỉ khai báo được bỏ qua.
4. Đặt hạn báo giá đã qua, chạy cron: nhắc một lần, activity quản lý xuất hiện. Chạy lại không tạo nhắc mới.
5. Ghi nhận phản hồi/khách từ chối/hủy báo giá: nhắc đang chờ được bỏ qua.
6. Quá hạn một lượt bước SLA: một cảnh báo; bước hoàn thành/on hold không bị cảnh báo như đang chạy.
7. Đến bước giao trả không có SO: hiện filter/cảnh báo. Có SO ở bất kỳ báo giá liên quan thì không cảnh báo, kể cả báo giá khác vẫn chưa có SO.
8. Hai model cùng dùng một dịch vụ, ghép hai dòng giá khác nhau: báo giá tự lấy đúng giá từng model; tính linh kiện + phí dịch vụ đủ trong PDF.
9. Kiểm tra account không có quyền quản trị không đọc token/hàng đợi và không thấy cấu hình công ty ngoài quyền.

Chưa kiểm thử cài module, render PDF hoặc gọi Microsoft trên hệ thống thật trong môi trường source hiện tại.
