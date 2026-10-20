# TechService: báo giá, cảnh báo và email/Teams qua n8n

Module Odoo 17: `ts_techservice_n8n`. Workflow import: [techservice_email_teams_v2.json](n8n/techservice_email_teams_v2.json).
Workflow không chứa credential hoặc secret, mặc định chưa kích hoạt. Không cần tạo workflow trực tiếp qua MCP.

## Tính năng

### Cập nhật 17.0.1.0.4

- Sửa thêm nhánh đổi người mua trên báo giá nháp: bỏ dependency công ty/tiền tệ khỏi compute đơn giá. Đổi người mua có thể tính lại bảng giá và tiền tệ dù vẫn là VND; trước đây nhánh này gọi giá sản phẩm 1đ khi chưa có số SO SAP, làm mất giá đã nhập, kể cả giá 0đ.
- Đưa bảo vệ giá đã chốt xuống `dat_sale` **17.0.1.0.26**, dùng chung cho giá DAT và giá dịch vụ. Bao phủ cả trạng thái riêng `status = confirmed/cancelled/rejected` khi `state` Odoo vẫn là nháp, cùng các đơn đã xác nhận/hủy theo Odoo hoặc có số SAP.
- Đổi người mua, công ty, tiền tệ hoặc ngày đơn không tự cập nhật đơn giá. Khi thực sự cần tính lại giá theo công ty/tiền tệ/ngày mới, dùng nút cập nhật Price List. Đổi sản phẩm, đơn vị, số lượng hoặc model vẫn tính giá theo luồng hiện có trên báo giá nháp.
- Khởi động lại các Odoo worker và nâng cấp cả `dat_sale` lẫn `ts_techservice_n8n` để nạp code mới. Migration **17.0.1.0.4** tự rà lại các dòng đã về 1đ và phục hồi khi có giá gốc duy nhất trong log SO SAP thành công, kể cả database đã chạy migration phục hồi cũ. Mỗi lần chạy lưu bản sao và danh sách dòng thiếu/mâu thuẫn bằng chứng trong tệp đính kèm; xem [RESTORE_PRICES.md](RESTORE_PRICES.md). Báo giá nháp chưa có bằng chứng giá gốc sẽ được báo lại để đối chiếu, không lấy bảng giá hiện tại thay cho giá đã chốt.
- Test ORM bổ sung bao gồm: đổi khách trực tiếp và đổi bảng giá cùng tiền tệ; lưu/đọc lại báo giá; đổi chủ sở hữu ticket rồi đồng bộ người mua/địa chỉ; giữ giá, chiết khấu và tổng tiền; trạng thái xác nhận riêng DAT; giá dịch vụ mới và nút lấy giá tường minh. Chạy trên database thử nghiệm có Odoo bằng `--test-enable --test-tags /ts_techservice_n8n`.

### Cập nhật 17.0.1.0.3

- Bỏ phụ thuộc ngày đơn hàng khỏi tính đơn giá để đổi ngày/xác nhận không tự kéo giá thương lượng về bảng giá. Giữ chặn tính lại giá trên đơn TechService đã xác nhận hoặc đã có SO SAP.
- Khi nâng cấp, đồng bộ mô tả lỗi của các báo giá có ticket về nội dung hiện tại trên ticket, bao gồm những bản chép cũ đã lệch. Nội dung nhập riêng trên báo giá cũng được thay bằng nội dung ticket trong lần đồng bộ này; các giá trị cũ được lưu trong tệp đính kèm `quotation-fault-sync-17.0.1.0.3.json` của tài khoản quản trị. Log `[TS_FAULT_SYNC]` ghi ID tệp. Các PDF đã gửi vẫn giữ nguyên.
- Khởi động lại Odoo rồi nâng cấp addon `ts_techservice_n8n` để nạp code, dependency mới và migration. Sao lưu và kiểm thử trên bản sao database trước khi áp dụng. Kiểm tra ORM bằng `--test-enable --test-tags /ts_techservice_n8n` trên database thử nghiệm.
- Ca CTH-26-006231: payload Main là 27.015.002đ, LT là 9.151.000đ, tổng 36.166.002đ; thấp hơn mức 42.000.000đ ghi trong nhật ký 5.833.998đ. Payload đã chứa giá sau khi lệch nên không đủ căn cứ để khôi phục giá chốt của từng dòng. Cần báo giá/PDF gốc được khách đồng ý để đối chiếu, đồng thời kiểm tra chứng từ đã tạo trên SAP.

- Dùng nút gửi báo giá hiện có để xếp hàng email đính kèm PDF và tin nhắn Teams riêng cho sale phụ trách ticket.
- “Mô tả lỗi” trên báo giá cập nhật khi sửa `product_error_note` hoặc `product_error_description` trên ticket, kể cả khi xóa nội dung hay đổi ticket. Có thể nhập riêng trên báo giá trước khi gửi; lần sửa mô tả lỗi tiếp theo trên ticket sẽ thay nội dung đó. PDF xuất mới dùng nội dung hiện tại; PDF đã gửi và tệp dùng để nhắc vẫn giữ nguyên phiên bản đã gửi.
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
