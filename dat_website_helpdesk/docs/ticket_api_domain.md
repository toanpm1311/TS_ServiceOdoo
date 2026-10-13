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

Tạo key trên chính database đang phục vụ domain:

1. Đăng nhập Odoo bằng tài khoản có quyền đọc phiếu hỗ trợ.
2. Mở **My Profile / Preferences → Account Security → API Keys → New API Key**.
3. Đặt tên key, xác nhận mật khẩu nếu Odoo yêu cầu và sao chép key được hiển thị.
4. Trong Postman Environment, đặt `base_url` và `api_key`, rồi chạy request 5.

Ví dụ request:

```http
GET /api/v1/tickets?page=1&page_size=80
Accept: application/json
X-API-Key: <odoo-api-key>
```

Không cần gửi `login`, `password`, `db` hoặc cookie `session_id`. Server kiểm
tra key bằng cơ chế `res.users.apikeys` của Odoo và thực thi truy vấn bằng
tài khoản sở hữu key, với quyền model, record rules và công ty của tài khoản
đó. Truy vấn tickets không dùng `sudo()`. Key không tạo session đăng nhập.

Key có thể bị thu hồi bằng cách xóa tại **Account Security → API Keys**;
request tiếp theo với key đã xóa sẽ bị từ chối. Key sai, rỗng hoặc thuộc tài
khoản đã vô hiệu hóa trả `401`; tài khoản không có quyền đọc dữ liệu trả lỗi
quyền truy cập `403`. Record rules giới hạn các phiếu được trả trong danh sách.

Khi có header `X-API-Key`, server ưu tiên key và không dùng cookie để bỏ qua
key không hợp lệ. Khi không có header này, GET tickets vẫn chấp nhận session
như trước. Hiện API key được hỗ trợ cho GET danh sách tickets; các endpoint
khác vẫn yêu cầu phương thức xác thực hiện có.

Server cần xác định đúng database theo domain bằng `dbfilter` / `db_name`,
như cấu hình ở trên. Giữ key trong Environment hoặc cấu hình bí mật của
client và dùng HTTPS khi gọi trên production.
