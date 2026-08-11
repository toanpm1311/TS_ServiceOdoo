# DAT Ticket ELE/AUT API

Addon Odoo 17 cung cấp API công khai (không cần token) để lấy dữ liệu ticket có
Salesperson thuộc SAP Business Area `ELE` hoặc `AUT`.

`SOL` (Energy) không nằm trong phạm vi API này.

## Endpoint

- Danh sách: `GET /api/v1/tickets/ele-aut/full-data`
- Chi tiết: `GET /api/v1/tickets/ele-aut/{identifier}/full-data`

`identifier` nhận database ID, UUID hoặc mã ticket (`name`).

Ví dụ:

```bash
curl "https://service.datgroup.com.vn/api/v1/tickets/ele-aut/full-data?limit=100&include_archived=true&updated_since=2026-08-02T00:00:00Z&updated_until=2026-08-04T13:00:00Z"
curl "https://service.datgroup.com.vn/api/v1/tickets/ele-aut/full-data?limit=100&include_archived=true&cursor=<next_cursor>"
curl "https://service.datgroup.com.vn/api/v1/tickets/ele-aut/REQ-00001/full-data"
```

Không gửi `Authorization`, cookie đăng nhập hoặc access token.

## Các mốc thời gian và trạng thái đồng bộ

Mỗi ticket ở cả response danh sách và chi tiết có các field tường minh:

- `created_at`: thời điểm tạo (`create_date`).
- `updated_at`: thời điểm cập nhật gần nhất (`write_date`).
- `start_date`: giá trị gốc hiện có trên ticket. Luồng nghiệp vụ hiện ghi field
  này khi tiếp nhận và có thể ghi lại khi phân công, nên không coi đây là một mốc
  “tiếp nhận đầu tiên” bất biến.
- `end_date`: giá trị gốc do luồng đóng ticket ghi nhận. API không tự thay bằng
  `write_date` khi field này trống.
- `replied_date`: giá trị gốc được ghi khi nhân viên gửi email qua composer. Dữ
  liệu hiện tại chưa đảm bảo đây là phản hồi đầu tiên và có thể để trống.
- `active`: `false` khi ticket đã được archive, `true` khi còn active.

Các field này vẫn tồn tại trong `ticket.data`; bản top-level giúp hệ thống tích
hợp đọc ổn định mà không phụ thuộc danh sách field động.

Ticket đã bị xóa vật lý bằng `unlink()` không còn tồn tại trong PostgreSQL nên
endpoint này không thể trả tombstone. Để đồng bộ trạng thái ngừng sử dụng, phía
Odoo cần archive ticket và phía đọc phải luôn gửi `include_archived=true`.

## Tham số danh sách

- `updated_since`: chỉ lấy record có `write_date >= updated_since`.
- `updated_until`: chỉ lấy record đến mốc này. Nếu bỏ trống, API chốt mốc theo
  thời gian máy chủ lúc bắt đầu trang đầu.
- `limit`: 1-100, mặc định 20.
- `cursor`: cursor opaque do `next_cursor` của trang trước trả về.
- `include_archived`: lấy cả ticket đã archive; nên đặt `true` khi đồng bộ.
- `offset`: giữ lại để tương thích client cũ; không được dùng cùng `cursor`.
- `q`: tìm mã ticket, tiêu đề hoặc khách hàng.
- `status`: có thể lặp lại để lọc nhiều trạng thái, gồm cả `closed` và
  `rejected` nếu được yêu cầu.
- `area`: `ELE` hoặc `AUT`; có thể lặp lại, mặc định lấy cả hai.
- `include_related`: bung dữ liệu các One2many nghiệp vụ.
- `include_chatter`: lấy tin nhắn và hoạt động.
- `include_binary`: nhúng nội dung binary/base64; mặc định tắt.
- `related_limit`: giới hạn từng mảng dữ liệu liên quan.

Kết quả được sắp xếp ổn định theo `write_date ASC, id ASC`. Response bổ sung:

- `next_cursor`: cursor của trang kế tiếp, hoặc `null` khi đã hết dữ liệu.
- `has_more`: còn trang kế tiếp hay không.
- `snapshot_at`: cận trên cố định của toàn bộ lượt phân trang.
- `server_time`: thời gian máy chủ lúc xử lý request.
- `updated_since`, `updated_until`: cửa sổ thời gian thực tế của lượt đọc.

Khi đọc trang tiếp theo, giữ nguyên các filter của trang đầu và gửi nguyên
`next_cursor`. Không gửi lại `offset` và `updated_until`; snapshot cố định đã nằm
trong cursor.

Endpoint chi tiết mặc định bật `include_related` và `include_chatter`. Cursor và
limit không áp dụng vì endpoint này chỉ trả tối đa một ticket.

## Cài đặt

1. Update Apps List.
2. Cài hoặc upgrade module **DAT Ticket ELE AUT API**
   (`dat_ticket_ele_aut_api`).
3. Nếu tài liệu API đang bật, kiểm tra route tại `/api/v1/docs`.

> API dùng `sudo()` và không xác thực theo yêu cầu tích hợp. Chỉ nên publish qua
> mạng nội bộ, VPN hoặc reverse proxy có giới hạn IP.
