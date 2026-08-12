import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Read only the required columns. Some legacy product fields in this database
    # are still plain text, so prefetching the complete ORM product record during
    # a module upgrade can incorrectly apply a JSON translation operator to them.
    cr.execute(
        """
        SELECT sale_order.id,
               sale_order.document_note,
               stock_lot.name AS serial_number,
               product_product.default_code,
               COALESCE(
                   product_template.name->>'vi_VN',
                   product_template.name->>'en_US',
                   ''
               ) AS product_name
          FROM sale_order
          JOIN ticket_helpdesk
            ON ticket_helpdesk.id = sale_order.ticket_id
     LEFT JOIN stock_lot
            ON stock_lot.id = ticket_helpdesk.stock_lot_id
     LEFT JOIN product_product
            ON product_product.id = stock_lot.product_id
     LEFT JOIN product_template
            ON product_template.id = product_product.product_tmpl_id
        """
    )

    updates = []
    for order_id, existing_note, serial_number, product_code, product_name in cr.fetchall():
        device_note_parts = []
        serial_number = (serial_number or "").strip()
        product_code = (product_code or "").strip()
        product_name = (product_name or "").strip()

        if serial_number:
            device_note_parts.append("Số series: %s" % serial_number)
        if product_name:
            device_name = "[%s] %s" % (product_code, product_name) if product_code else product_name
            device_note_parts.append("Tên thiết bị: %s" % device_name)

        device_note = " - ".join(device_note_parts)
        existing_note = (existing_note or "").strip()
        if not device_note or device_note in existing_note:
            continue
        document_note = " - ".join(
            part for part in (existing_note, device_note) if part
        )
        updates.append((document_note, order_id))

    for document_note, order_id in updates:
        cr.execute(
            "UPDATE sale_order SET document_note = %s WHERE id = %s",
            (document_note, order_id),
        )

    _logger.info(
        "Appended ticket serial and device name to %s existing quotations.",
        len(updates),
    )
