# DAT Ticket ELE/AUT API

Addon Odoo 17 cung cấp API công khai (không cần token) để lấy dữ liệu đầy đủ
của ticket có Salesperson thuộc SAP Business Area `ELE` hoặc `AUT`.

`SOL` (Energy) không nằm trong phạm vi API này.

## Endpoint

- Danh sách: `GET /api/v1/tickets/ele-aut/full-data`
- Chi tiết: `GET /api/v1/tickets/ele-aut/{identifier}/full-data`

`identifier` nhận database ID, UUID hoặc mã ticket (`name`).

Ví dụ theo cổng hiện tại trong `odoo.conf` của ANFY:

```bash
curl "http://localhost:8080/api/v1/tickets/ele-aut/full-data?limit=20&offset=0"
curl "http://localhost:8080/api/v1/tickets/ele-aut/full-data?area=ELE"
curl "http://localhost:8080/api/v1/tickets/ele-aut/REQ-00001/full-data"
```

Không gửi `Authorization`, cookie đăng nhập hoặc access token.

## Tham số danh sách

- `limit`: 1-100, mặc định 20.
- `offset`: vị trí bắt đầu, mặc định 0.
- `q`: tìm mã ticket, tiêu đề hoặc khách hàng.
- `status`: có thể lặp lại để lọc nhiều trạng thái.
- `area`: `ELE` hoặc `AUT`; có thể lặp lại, mặc định lấy cả hai.
- `include_archived`: lấy cả ticket lưu trữ.
- `include_related`: bung dữ liệu các One2many nghiệp vụ.
- `include_chatter`: lấy tin nhắn và hoạt động.
- `include_binary`: nhúng nội dung binary/base64; mặc định tắt.
- `related_limit`: giới hạn từng mảng dữ liệu liên quan.

Endpoint chi tiết mặc định bật `include_related` và `include_chatter`.

## Cài đặt

1. Update Apps List.
2. Cài module **DAT Ticket ELE AUT API** (`dat_ticket_ele_aut_api`).
3. Nếu tài liệu API đang được bật, kiểm tra route tại `/api/v1/docs`.

> Lưu ý: API dùng `sudo()` và không xác thực theo yêu cầu tích hợp. Chỉ nên
> publish qua mạng nội bộ, VPN hoặc reverse proxy có giới hạn IP.
