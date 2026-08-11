# Tài liệu kết nối API Ticket theo Business Unit

## 1. Mục đích

API trả về toàn bộ ticket mà tài khoản đang đăng nhập được phép xem, giới hạn theo Business Unit của sản phẩm gắn với ticket.

Các Business Unit được hỗ trợ:

| Mã | Diễn giải |
| --- | --- |
| `AUT` | Automation |
| `ELE` | Elevator |

Business Unit được lấy từ trường `sap_business_unit` của sản phẩm liên kết với ticket. Ticket không có sản phẩm, không có Business Unit, hoặc thuộc mã khác sẽ không xuất hiện trong kết quả.

## 2. Thông tin chung

| Thuộc tính | Giá trị |
| --- | --- |
| Base URL | `https://<odoo-host>/api/v1` |
| Kiểu xác thực | Odoo session cookie (`session_id`) |
| Định dạng dữ liệu | JSON, UTF-8 |
| HTTP method | `GET` |
| Endpoint | `/tickets/by-business-units` |

> `odoo-host` phải được cấu hình `dbfilter` để trỏ tới đúng database, hoặc hệ thống chỉ được expose một database. API cần xác định được database trước khi đăng nhập.

## 3. Xác thực

### 3.1. Đăng nhập

Gửi yêu cầu:

```http
POST /api/v1/auth/login
Content-Type: application/json
```

Body:

```json
{
  "login": "integration_user",
  "password": "your_password"
}
```

Ví dụ response thành công:

```json
{
  "uuid": "f5e12f62-b13d-4b05-a906-46aeff70af82",
  "login": "integration_user",
  "name": "Integration User",
  "email": "integration@example.com",
  "phone": false,
  "mobile": false,
  "avatar_256_url": false,
  "lang": "vi_VN",
  "login_date": "2026-07-23T03:00:00Z"
}
```

Response đăng nhập có cookie `session_id`. Client phải lưu cookie này và gửi lại trong các request lấy ticket.

### 3.2. Gọi bằng session hiện có

```http
Cookie: session_id=<odoo_session_id>
Accept: application/json
```

Session hết hạn hoặc không hợp lệ sẽ nhận HTTP `401 Unauthorized`.

## 4. API lấy ticket

### 4.1. Lấy cả AUT và ELE

Không truyền `business_units`, API mặc định lấy cả hai mã:

```http
GET /api/v1/tickets/by-business-units
```

Có thể truyền tường minh bằng cách lặp query parameter:

```http
GET /api/v1/tickets/by-business-units?business_units=AUT&business_units=ELE
```

### 4.2. Chỉ lấy AUT

```http
GET /api/v1/tickets/by-business-units?business_units=AUT
```

### 4.3. Chỉ lấy ELE

```http
GET /api/v1/tickets/by-business-units?business_units=ELE
```

Không dùng định dạng `business_units=AUT,ELE`. Với nhiều mã, cần lặp lại tham số như ví dụ phía trên.

## 5. Response

API trả trực tiếp một JSON array. Không có `limit`, `offset` hoặc phân trang ở endpoint này.

Ví dụ:

```json
[
  {
    "uuid": "937f64ac-76f4-41b9-83f9-cb785dc56a2e",
    "priority_id": {
      "code": "high",
      "name": "High",
      "default": false
    },
    "name": "HCM-2607-00001",
    "subject": "Kiểm tra biến tần",
    "status": "in_progress",
    "customer_id": {
      "uuid": "0adf7567-d76d-4457-8568-f634635fa3a5",
      "name": "Công ty ABC",
      "phone": "0900000000",
      "email": "contact@example.com",
      "address": "TP. Hồ Chí Minh"
    },
    "ticket_type_id": {
      "uuid": "7663d441-485d-47e0-9daa-5e323a1460f9",
      "name": "Warranty"
    },
    "delivery_address": "TP. Hồ Chí Minh",
    "start_date": "2026-07-23T03:00:00Z",
    "deadline": "2026-07-24T03:00:00Z",
    "create_date": "2026-07-23T02:30:00Z",
    "assigned_user_id": {
      "uuid": "1bcc333f-6ff2-41aa-a216-04f89c2cbe98",
      "name": "Kỹ thuật viên A"
    },
    "business_unit": "AUT"
  }
]
```

Các trường quan hệ hoặc thông tin chưa có dữ liệu có thể nhận `null` hoặc `false`, theo dữ liệu hiện tại của Odoo.

Kết quả được sắp xếp theo thứ tự mặc định của ticket:

1. Độ ưu tiên giảm dần.
2. Ngày tạo giảm dần.
3. Mã ticket giảm dần.

Nếu không có ticket phù hợp, API trả:

```json
[]
```

## 6. Ví dụ kết nối

### 6.1. Windows PowerShell với curl.exe

Đăng nhập và lưu cookie:

```powershell
curl.exe -i `
  -c .\odoo-cookie.txt `
  -H "Content-Type: application/json" `
  -d '{"login":"integration_user","password":"your_password"}' `
  "https://techservice.example.com/api/v1/auth/login"
```

Lấy ticket AUT và ELE:

```powershell
curl.exe -sS `
  -b .\odoo-cookie.txt `
  -H "Accept: application/json" `
  "https://techservice.example.com/api/v1/tickets/by-business-units?business_units=AUT&business_units=ELE"
```

### 6.2. Python requests

```python
import requests


BASE_URL = "https://techservice.example.com/api/v1"

with requests.Session() as session:
    login_response = session.post(
        f"{BASE_URL}/auth/login",
        json={
            "login": "integration_user",
            "password": "your_password",
        },
        timeout=30,
    )
    login_response.raise_for_status()

    ticket_response = session.get(
        f"{BASE_URL}/tickets/by-business-units",
        params=[
            ("business_units", "AUT"),
            ("business_units", "ELE"),
        ],
        timeout=60,
    )
    ticket_response.raise_for_status()

    tickets = ticket_response.json()
    print(f"Số ticket nhận được: {len(tickets)}")
```

### 6.3. Postman

1. Tạo request `POST /api/v1/auth/login` với body JSON đăng nhập.
2. Gửi request và kiểm tra Postman đã lưu cookie `session_id` cho domain Odoo.
3. Tạo request `GET /api/v1/tickets/by-business-units`.
4. Thêm hai query parameter cùng tên `business_units`, lần lượt có giá trị `AUT` và `ELE`.
5. Gửi request. Postman sẽ tự động đính kèm cookie đã lưu nếu cùng domain.

## 7. HTTP status và xử lý lỗi

| HTTP status | Ý nghĩa | Hướng xử lý |
| --- | --- | --- |
| `200` | Thành công | Đọc JSON array trong response body. |
| `401` | Chưa đăng nhập hoặc session hết hạn | Đăng nhập lại và lưu `session_id` mới. |
| `422` | Query parameter không hợp lệ, ví dụ mã ngoài `AUT`/`ELE` | Kiểm tra lại tên và giá trị `business_units`. |
| `500` | Lỗi nội bộ hoặc module/database chưa cập nhật | Kiểm tra log Odoo và trạng thái module `dat_product`. |

Ví dụ truyền mã không hợp lệ:

```http
GET /api/v1/tickets/by-business-units?business_units=SOL
```

Request trên sẽ nhận HTTP `422` vì API hiện chỉ chấp nhận `AUT` và `ELE`.

## 8. Quyền dữ liệu

API không dùng `sudo()`. Kết quả luôn tuân thủ access rights và record rules của tài khoản Odoo đang đăng nhập.

“Toàn bộ ticket” trong tài liệu này có nghĩa là toàn bộ ticket `AUT`/`ELE` mà tài khoản tích hợp có quyền đọc. Nếu hệ thống tích hợp cần đọc tất cả ticket, cần tạo một tài khoản Odoo chuyên dụng và cấp đúng nhóm quyền Helpdesk cần thiết.

Khuyến nghị:

- Dùng tài khoản tích hợp riêng, không dùng tài khoản cá nhân.
- Chỉ cấp quyền đọc và phạm vi dữ liệu thực sự cần thiết.
- Luôn gọi API qua HTTPS.
- Không ghi password hoặc cookie `session_id` vào log ứng dụng.
- Khi nhận `401`, đăng nhập lại một lần rồi retry request; tránh retry vô hạn.

## 9. Triển khai và kiểm tra sau nâng cấp

Sau khi đưa source code lên server, restart Odoo và upgrade module `dat_product` để tạo trường/index Business Unit trên ticket và đăng ký router mới:

```bash
python odoo-bin -c /path/to/odoo.conf -d DATABASE_NAME -u dat_product --stop-after-init
```

Sau đó khởi động lại Odoo và kiểm tra:

```http
GET /api/v1/tickets/by-business-units?business_units=AUT
```

Nếu `core_fastapi.api_debug` đang bật, có thể kiểm tra OpenAPI tại `/api/v1/docs`. Production có thể tắt tài liệu OpenAPI theo cấu hình bảo mật hiện tại.
