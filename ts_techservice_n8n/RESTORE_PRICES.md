# Khôi phục đơn giá TechService bị về 1đ

## Tự phục hồi khi nâng cấp addon

Phiên bản **17.0.1.0.2** tự chạy migration phục hồi khi nâng cấp từ phiên bản cũ.
Copy toàn bộ addon `ts_techservice_n8n` mới lên máy chủ, khởi động lại Odoo để nạp
code Python mới, rồi bấm **Nâng cấp** addon **TS TechService Alerts and n8n**.
Hoặc chạy bằng CLI theo cách triển khai hiện tại:

```bash
./odoo-bin -c /path/to/odoo.conf -d DATABASE -u ts_techservice_n8n --stop-after-init
```

Migration tự rà các dòng TechService giá đúng 1đ, áp dụng các dòng có giá gốc duy
nhất theo log SO SAP thành công và bỏ qua các dòng thiếu/mâu thuẫn bằng chứng.
Không bảo đảm phục hồi được mọi đơn nếu lịch sử không đủ. Hãy sao lưu database
và kiểm thử nâng cấp trên bản sao trước khi chạy production.

Log `[TS_PRICE_RECOVERY]` ghi số dòng đã sửa, số dòng bỏ qua và ID file sao lưu
trong `ir.attachment` (tên `so-price-recovery-....json`). File chứa đầy đủ mục
`repairs` và `skipped`, kể cả khi không có dòng nào đủ điều kiện sửa.
Trong chế độ nhà phát triển, quản trị viên có thể tìm file này ở
**Thiết lập → Kỹ thuật → Tệp đính kèm**.

Migration chỉ chạy một lần khi phiên bản đã cài tăng lên **17.0.1.0.2**; không
chạy khi cài mới, restart hoặc nâng cấp lại cùng phiên bản. Nếu nâng cấp lỗi,
Odoo rollback lần nâng cấp và dữ liệu phục hồi cùng nhau. Không có cron chạy
phục hồi lặp lại. Không cần chạy Odoo shell cho cách này.

Công cụ không gọi SAP, không tạo SO mới,
không đổi chiết khấu, số lượng, trạng thái hay bảng giá sản phẩm.

## Chạy thủ công (tùy chọn)

Nếu muốn xem danh sách trước khi sửa, dùng các bước dưới trên database chưa
chạy migration (hoặc khi rà lại các dòng còn bỏ qua).

## 1. Tạo danh sách đề xuất

Mở Odoo shell bằng cấu hình và database đang sử dụng, với tài khoản quản trị:

```bash
./odoo-bin shell -c /path/to/odoo.conf -d DATABASE --no-http
```

Trong shell, thay đường dẫn bằng thư mục addons thực tế trên máy chủ:

```python
import runpy
recovery = runpy.run_path('/path/to/addons/ts_techservice_n8n/tools/restore_so_prices.py')
plan = recovery['build_plan'](env)
recovery['save_plan'](plan, '/tmp/so-price-recovery-review.json')
print('Dòng đề xuất sửa:', len(plan['repairs']))
print('Dòng bỏ qua:', len(plan['skipped']))
```

Mặc định rà tất cả các đơn TechService có dòng đơn giá **đúng 1đ**, trong phạm vi
quyền truy cập của tài khoản chạy. Có thể giới hạn theo ID nội bộ của đơn:

```python
plan = recovery['build_plan'](env, order_ids=[123, 456])
```

Đọc file JSON, kiểm tra mục `repairs`: tên đơn, ID dòng, sản phẩm, số lượng,
chiết khấu, tiền tệ, `old_price`, `new_price` và ID thông điệp làm bằng chứng.
`skipped` chứa lý do những dòng chưa đủ căn cứ. File được tạo mới, không ghi đè
file cũ. Lưu file tại thư mục riêng, có quyền truy cập phù hợp.

Nguồn giá là `U_OrigiPrice` trong payload SO, đi kèm thông điệp tạo SO SAP thành
công đúng số chứng từ đã lưu. Log request đơn lẻ có thể thuộc giao dịch thất bại
nên không được dùng. Với SO gộp, tìm thêm log trên các đơn cùng số SO SAP, công ty
và tiền tệ. Hai phía Main/LT được đối chiếu riêng.

Chỉ đề xuất sửa khi mọi bằng chứng khớp mã hàng cho một giá gốc duy nhất. Giá 0đ
được giữ đúng 0đ. Dòng phí có cả giá 0đ và 1đ trong payload gộp bị bỏ qua;
không đoán giá theo thứ tự dòng. Dòng đã xuất hóa đơn hoặc đơn hủy cũng bị bỏ qua.
Chưa hỗ trợ đơn không lưu số chứng từ của LT bridge hoặc thiếu log thành công.
Đề xuất vẫn cần đối chiếu nghiệp vụ, vì log SAP không chứng minh một thay đổi giá
sau đó là lỗi hay là người dùng chủ động sửa.

## 2. Áp dụng toàn bộ danh sách đã rà soát

Trong Odoo shell, sau khi rà soát file:

```python
import json
with open('/tmp/so-price-recovery-review.json', encoding='utf-8') as stream:
    reviewed_plan = json.load(stream)
result = recovery['apply_plan'](env, reviewed_plan)
print(result)
env.cr.commit()
```

Chỉ commit sau khi hàm thành công. Hàm kiểm tra lại giá và bằng chứng, khóa các
đơn/dòng liên quan, lưu bản sao JSON vào `ir.attachment` gắn với tài khoản quản trị,
rồi ghi giá qua ORM để tính lại thành tiền. Kết quả trả số dòng đã sửa và ID bản sao.
Nếu bất kỳ dòng nào thay đổi từ lúc rà soát hoặc ghi giá không đúng, toàn bộ lần
áp dụng bị rollback. Tạo lại danh sách rồi kiểm tra lại khi gặp lỗi này. Không sửa
tay các mục trong file để ép áp dụng. Chạy lại bước rà soát để xem phần còn bỏ qua.

Đây là phục hồi dữ liệu Odoo. Không sửa lại giá SO hoặc hóa đơn trên SAP. Nhật ký
kiểm soát hiện có vẫn ghi thay đổi dòng; công cụ không kích hoạt luồng yêu cầu
duyệt giá mới cho lần phục hồi.

## Kiểm tra parser độc lập

Không cần Odoo để chạy các kiểm tra đọc log, giá gốc, chứng từ thành công và mã trùng:

```bash
python -B ts_techservice_n8n/tools/test_restore_so_prices.py
```

Các kiểm tra này không thay thế kiểm thử ORM trên database thử nghiệm sao chép từ
database thật trước khi áp dụng cho production.
