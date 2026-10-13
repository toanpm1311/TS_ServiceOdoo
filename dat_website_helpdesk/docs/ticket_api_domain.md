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
2. Điền `db`, `username`, `password` đúng với môi trường đó.
3. Chạy request đăng nhập trước để nhận cookie `session_id` cho domain đó.
4. Chạy request lấy phiếu tại `{{base_url}}/api/v1/tickets`.

Khi đổi domain, cập nhật `base_url` trong Environment và đăng nhập lại trên
domain mới.
