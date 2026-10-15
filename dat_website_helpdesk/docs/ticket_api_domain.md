# Domain của API phiếu hỗ trợ

API nhận request tại đường dẫn tương đối:

```text
GET /api/v1/tickets
```

Đường dẫn được đăng ký qua FastAPI tích hợp trong Odoo:

- `core_fastapi/data/fastapi_endpoint_data.xml`: root path `/api/v1`.
- `dat_website_helpdesk/routers/__init__.py`: prefix `/tickets`.
- `dat_website_helpdesk/routers/tickets.py`: GET `""` và `"/"`.

Route không chứa hostname hoặc port, nên dùng được với domain đang phục vụ
Odoo, tương tự cách `@http.route('/api/...')` đăng ký đường dẫn. Khi đổi domain,
giữ nguyên đường dẫn API. Domain mới cần được trỏ tới cùng dịch vụ Odoo và
database phù hợp.

## Dữ liệu trả về trong danh sách

GET `/api/v1/tickets` và `/api/v1/tickets/` trả về `count` và `items` dùng
schema chi tiết `TicketHelpdesk`. Trước đây response model của route dùng
`TicketHelpdeskBase`, nên FastAPI lọc bỏ các trường chi tiết khỏi JSON.

Ngoài các trường cũ, mỗi phần tử trong `items` có thêm:

- Sản phẩm: `product_id` (ID, UUID nếu có, tên, tên hiển thị, mã sản phẩm),
  `stock_lot_id`, `stock_name`, `serial_number`, `replace_serial_number`, `new_stock_lot_id`,
  `new_serial_number`, `board_serial_line_ids` (seri bo cũ/mới, ngày).
- Người sở hữu: `owner_phone`, `owner_email`, `owner_address`; người bán hàng,
  phòng ban và thông tin SAP của phiếu.
- Quy trình: `workflow_id`, `step_id`, `step_external_id`, người xử lý từng
  bước, ngày kết thúc, lý do từ chối/tạm dừng, đánh giá.
- Sửa chữa/bảo hành, khảo sát/tư vấn, báo giá, triển khai, nghiệm thu; ghi chú,
  lịch dự kiến, checklist, lỗi triển khai và liên kết tệp đính kèm.
- Các addon mở rộng: `ts_defective_return_status`, thông tin đồng bộ seri
  `ts_serial_synced`, `ts_last_serial_sync_at`, `ts_last_serial_sync_note`,
  `bnk_replacement_serial_sync_*`, bảo hành nhà sản xuất/nhà cung cấp,
  kho nguồn/trung gian/đích, tiến độ khách hàng và SO trả hàng.
  Các trường từ addon chưa cài trả về `null`.

### Phản hồi báo giá và kết quả kiểm tra công việc

Các trường này có trong mỗi phần tử `items[]` của GET danh sách và trong
đối tượng trả về của GET chi tiết `/api/v1/tickets/{uuid}`:

| Nội dung giao diện | Trường JSON | Giá trị |
| --- | --- | --- |
| Phản hồi báo giá | `sale_order_feedback` | `agree` = Đồng ý, `refuse` = Từ chối, `false` = chưa phản hồi |
| Lý do từ chối báo giá | `sale_order_feedback_comment` | Nội dung phản hồi |
| Ghi chú SO | `note_SO` | Ghi chú, giữ nguyên chữ hoa trong tên trường |
| Số SO SAP / trạng thái | `sap_sale_order_number`, `sap_so_status` | Giá trị đang lưu trên phiếu |
| Phiếu kiểm tra công việc | `checklist_ids[]` | Mã, nội dung, bước, người phụ trách và kết quả từng dòng |
| Hoàn thành công việc | `checklist_ids[].is_done` | `true` = hoàn thành, `false` = chưa hoàn thành |
| Ngày hoàn thành | `checklist_ids[].done_date` | ISO 8601 UTC hoặc `false` nếu chưa có |
| Ghi chú kết quả | `checklist_ids[].note` | Nội dung ghi chú của công việc |

Nội dung **Kết quả kiểm tra** trên bản in phiếu lấy giá trị có nội dung đầu
tiên theo thứ tự `survey_result_description`, `completed_task_description`,
`implementation_work_note`. API đã trả cả ba trường gốc này. Không có trường
`result` riêng trên từng dòng checklist; kết quả dòng gồm `is_done`,
`done_date`, `note`.

### Tiến độ và các bảng chi tiết trên phiếu

`ticket_step_status_ids` trả đầy đủ các dòng của tab **Tiến độ**, theo thứ tự
lưu trong Odoo. Nếu một bước được thực hiện nhiều lần, API giữ từng dòng riêng
với `id` riêng; không gộp theo tên bước.

| Cột giao diện | Trường JSON trong `ticket_step_status_ids[]` |
| --- | --- |
| Tên bước | `step_name`, `step_id` (ID, UUID nếu có, tên, mã, thứ tự) |
| Người phụ trách | `assignee_ids[]` (UUID, tên), hỗ trợ nhiều người |
| Ngày bắt đầu | `start_date` |
| Thời hạn | `deadline` |
| Thời gian SLA | `time_sla` |
| Thời gian đã sử dụng | `time_spent` |
| Trạng thái | `status` |

`status` dùng các mã: `not_started` (chưa bắt đầu), `in_progress` (đang thực
hiện), `on_hold` (tạm dừng), `done` (hoàn thành), `rejected` (từ chối).
Trạng thái từng dòng độc lập với `status` của phiếu, ví dụ phiếu có thể đã
`closed` trong khi lịch sử bước dùng mã `done`.

Mỗi dòng còn có `end_date`, `hold_date`, `hold_time`, `time_alert`,
`time_check`, `deadline_notification_sent`. Các thời điểm dùng ISO 8601 UTC
(đuôi `Z`); client đổi sang múi giờ hiển thị. Thời lượng là số giờ thập phân:
`4.0` tương ứng `04:00`, `6.7833333333` tương ứng khoảng `06:47`.
`time_spent` là giá trị được lưu bởi Odoo, không tính lại thời lượng ở API.

Các bảng nghiệp vụ khác cũng được trả về dưới dạng mảng đối tượng:

- `ticket_step_ids`: các bước liên quan; `waiting_for_assignment`: đang chờ
  phân công; `total_time_spent`: tổng thời gian từ addon dashboard, đơn vị giờ.
- `task_allocation_ids`: thứ tự, người phụ trách, trọng số `weight` (0–1),
  điểm và ghi chú; `kpi_coefficient_ids`: người phụ trách và hệ số KPI.
- `checklist_ids`, `checklist_count`: mã/nội dung công việc, bước, người phụ
  trách, hoàn thành, ngày hoàn thành, ghi chú và số phiếu kiểm tra.
- `technical_proposal_ids`: thông tin, phiên bản, người/ngày tạo, trạng thái
  khóa, cấu hình thiết bị, mô tả giải pháp, tệp đính kèm và chi tiết vật tư
  `technical_proposal_line_ids` (sản phẩm, mã, đơn vị, hãng, số lượng, tồn kho,
  ghi chú); `material_proposal_create_count`: số lần tạo đề xuất vật tư.
- `external_document_ids`, `external_document_count`: nghiệp vụ, mã chứng từ,
  báo giá liên quan, ngày tạo và số chứng từ.

Các bảng không có dòng trả `[]`. Trường thuộc addon chưa cài trả `null`;
ngày/quan hệ chưa nhập có thể trả `false` theo Odoo. Schema này cũng áp dụng
cho GET chi tiết `/api/v1/tickets/{uuid}` với xác thực session hiện có.

Đối chiếu các cột seri trên giao diện Odoo:

| Cột giao diện | Trường JSON |
| --- | --- |
| Seri / Số Sê-ri | `stock_name`, `serial_number`, `stock_lot_id.name` |
| Seri thay thế | `replace_serial_number`, `new_serial_number`, `new_stock_lot_id.name` nếu có |
| Số seri bo | `board_serial_line_ids[].old_board_serial`, `board_serial_line_ids[].new_board_serial` |
| Trạng thái gửi sản phẩm lỗi | `ts_defective_return_status`: `not_sent`, `sent`, `received` |

`serial_number` là tên bổ sung cho `stock_name`, không thay đổi trường cũ.
Nếu phiếu chưa có seri mới, `new_stock_lot_id` trả về `false` thay vì đối
tượng có `id: 0`; `replace_serial_number` và `new_serial_number` vẫn trống.

Các trường trống có thể trả về `false`, `null` hoặc mảng rỗng theo kiểu dữ
liệu. API dùng danh sách trường nghiệp vụ khai báo trong schema, không xuất
tự động toàn bộ trường kỹ thuật của Odoo, chatter hay nội dung binary/base64.
File đính kèm dùng schema `Attachment` với `uuid`, `name`, `local_url`;
tải file vẫn tuân theo quyền truy cập của route tải file Odoo.

Phân trang, bộ lọc, JSON body `card_code` và xác thực `X-API-Key` giữ nguyên.
Khởi động lại tiến trình Odoo sau khi cập nhật code Python để nạp schema và
route mới; thay đổi này không yêu cầu tạo lại API key.

## Gọi từ website Odoo

Dùng URL bắt đầu bằng `/` để trình duyệt tự lấy protocol, domain và port của
trang hiện tại. Ví dụ sau dùng session Odoo đã đăng nhập để lấy danh sách:

```javascript
const response = await fetch('/api/v1/tickets?page=1&page_size=80', {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
});
if (!response.ok) {
    throw new Error(`Không lấy được phiếu hỗ trợ: HTTP ${response.status}`);
}
const tickets = await response.json();
```

## Gọi từ Postman

Postman cần URL tuyệt đối và không có domain của trang hiện tại để tự suy ra.
Collection `odoo_tickets.postman_collection.json` để trống `base_url`, không
đặt mặc định domain hoặc port.

1. Tạo/chọn Environment và đặt biến `base_url` bằng URL gốc của Odoo đang dùng,
   gồm `http://` hoặc `https://`, không có dấu `/` cuối.
2. Điền `username`, `password` đúng với môi trường đó. Không cần điền `db`.
3. Chạy request đăng nhập trước để nhận cookie `session_id` cho domain đó.
4. Chạy request lấy phiếu tại `{{base_url}}/api/v1/tickets`.

Nếu dùng API key, điền `api_key` và chạy trực tiếp request **5. Lấy phiếu hỗ
trợ bằng API key**; không cần chạy request đăng nhập. Xem hướng dẫn bên dưới.

Khi đổi domain, cập nhật `base_url` trong Environment và đăng nhập lại trên
domain mới.

## Đăng nhập không truyền database

Endpoint riêng trong module `core_fastapi`:

```text
POST /api/session/authenticate
Content-Type: application/json
```

Body JSON-RPC:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "login": "{{username}}",
    "password": "{{password}}"
  },
  "id": 1
}
```

Server lấy danh sách database được cấu hình Odoo cho phép với host hiện tại
và chỉ đăng nhập khi có đúng một database phù hợp. Việc chọn database không
dựa vào tham số `db` của client hay database trong cookie cũ. Endpoint dùng
lại xử lý đăng nhập của Odoo, trả kết quả trong `result` và tạo cookie
`session_id` khi đăng nhập thành công. Với tài khoản có MFA, `result.uid` có
thể là `null`; cần hoàn tất MFA qua luồng đăng nhập Odoo trước khi gọi API.

Ví dụ server chỉ phục vụ một database:

```ini
[options]
db_name = your_production_database
dbfilter = ^your_production_database$
list_db = False
```

Thay `your_production_database` bằng tên database đã deploy. Endpoint vẫn
tự xác định database khi `list_db = False`. Nếu triển khai nhiều database
theo subdomain với tên database bằng phần đầu của host, có thể dùng
`dbfilter = ^%d$`; mỗi host cần khớp đúng một database.

Khi chạy sau reverse proxy, chuyển tiếp đúng host và cấu hình `proxy_mode`
cho Odoo phù hợp để bộ lọc domain hoạt động đúng.

Cần cài đặt module `core_fastapi` trên database đích và khởi động lại Odoo
sau khi cập nhật code để nạp controller. Domain phải được Odoo xác định
đúng database trước khi định tuyến tới controller của module; cấu hình sai
hoặc nhiều database phù hợp có thể khiến route chưa được tìm thấy. Nếu request
đến được controller nhưng không xác định được đúng một database, endpoint
trả lỗi và không thử đăng nhập vào database bất kỳ.

## Lấy tickets bằng API key, không cần đăng nhập

GET `/api/v1/tickets` và `/api/v1/tickets/` chấp nhận header `X-API-Key` thay
cho cookie đăng nhập. Các bộ lọc và phân trang hiện có giữ nguyên; JSON body
`card_code` cũng dùng được với API key như khi gọi bằng session.

Module tự tạo `core_fastapi.api_key` với Value ngẫu nhiên khi Odoo nạp một
database đã cài `core_fastapi`, bao gồm khi cài module và khi chuyển sang
database khác. Nếu thông số đã tồn tại, Value được giữ nguyên. Với database
đã được nạp trước khi cập nhật code này, khởi động lại Odoo một lần để áp dụng;
không cần tạo thông số thủ công hoặc nâng cấp module chỉ để tạo khóa.

Lấy key trên chính database đang phục vụ domain:

1. Đăng nhập Odoo bằng tài khoản quản trị và bật chế độ nhà phát triển.
2. Mở **Cài đặt → Kỹ thuật → Tham số → Thông số hệ thống**, tìm
   `core_fastapi.api_key` đã được tạo tự động:

   | Khóa | Giá trị |
   | --- | --- |
   | `core_fastapi.api_key` | Chuỗi bí mật ngẫu nhiên được tạo tự động. |

3. Sao chép **Giá trị** vào biến `api_key` của Postman Environment. Bạn có thể
   thay Value bằng chuỗi bí mật riêng và lưu lại. Cột **Khóa** luôn là
   `core_fastapi.api_key`, tên này đã được gắn cố định trong code.
4. Đặt `base_url` bằng domain hiện tại của Odoo, rồi chạy request 5.

Không cần tạo `core_fastapi.api_key_endpoint` hoặc
`core_fastapi.api_key_user_login`. Không điền URL hay đường dẫn API vào Value.
Khóa trong Thông số hệ thống cấp quyền đọc danh sách
phiếu và dữ liệu liên quan trên toàn database, bao gồm các công ty trong
database đó. Không cần chọn User hoặc Company của FastAPI Endpoint để dùng
khóa. Có thể xóa các thông số cấu hình cũ nếu đã tạo trước đó.

Ví dụ chạy local, có thể đổi Value của thông số đã có:

| Khóa | Giá trị ví dụ |
| --- | --- |
| `core_fastapi.api_key` | `test1` |

Trong Postman, gọi GET `http://localhost:5050/api/v1/tickets` với header
`X-API-Key: test1`; không cần đăng nhập trước. `test1` là giá trị minh họa local;
trên production dùng chuỗi bí mật ngẫu nhiên làm Value.

Ví dụ request:

```http
GET /api/v1/tickets?page=1&page_size=80
Accept: application/json
X-API-Key: test1
```

Không cần gửi `login`, `password`, `db` hoặc cookie `session_id`. Server kiểm
tra header `X-API-Key` khớp **Giá trị** của thông số `core_fastapi.api_key`
rồi dùng quyền hệ thống để đọc phiếu và
các dữ liệu liên quan. Quyền đọc này không phụ thuộc User, Company hoặc
record rules của Endpoint. Key không tạo session đăng nhập và không cấp
quyền gọi API tạo, sửa hoặc xóa phiếu. Khi không gửi key, session vẫn được
kiểm tra theo quyền truy cập của tài khoản đã đăng nhập.

Đường dẫn GET `/api/v1/tickets` đã được đăng ký trong code, độc lập với Value
của thông số. Domain là địa chỉ Odoo đang phục vụ database (ví dụ
`http://localhost:5050`), không cần gắn domain trong code. Có hoặc không có
dấu `/` cuối đều được chấp nhận; các query filter như `page`, `page_size`,
`card_code` không ảnh hưởng việc xác thực.

Đổi Value hoặc xóa bản ghi `core_fastapi.api_key` tại **Thông số hệ thống** để thu hồi khóa;
request tiếp theo với key cũ sẽ bị từ chối. Nếu xóa bản ghi, khóa ngẫu nhiên
mới sẽ được tạo khi Odoo nạp lại database; khóa cũ không còn hợp lệ.
Value đang tồn tại, kể cả Value trống, không bị ghi đè khi nạp lại.
Không cần khởi động lại Odoo khi
đổi giá trị thông số. Key sai, rỗng, thiếu cấu hình, đường dẫn không khớp hoặc
Endpoint không tồn tại/đã vô hiệu hóa trả `401`. Xác thực bằng khóa chỉ được
thực hiện cho phương thức GET. Khi chuyển database, thông số được tạo tự
động nếu chưa có. Mỗi database tạo một Value riêng; sao chép Value của
database mới vào Postman. Bảo đảm module API đã được cài và domain trỏ tới
đúng database; không cần cấu hình thêm User của Endpoint.

Khi có header `X-API-Key`, server ưu tiên key và không dùng cookie để bỏ qua
key không hợp lệ. Khi không có header này, GET tickets vẫn chấp nhận session
như trước. Hiện API key được hỗ trợ cho GET danh sách tickets; các endpoint
khác vẫn yêu cầu phương thức xác thực hiện có.

Server cần xác định đúng database theo domain bằng `dbfilter` / `db_name`,
như cấu hình ở trên. Giữ key trong Environment hoặc cấu hình bí mật của
client và dùng HTTPS khi gọi trên production.
