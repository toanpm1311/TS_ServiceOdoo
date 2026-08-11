TS Techservice Flow Guard - Odoo 17

Target: Odoo 17

Main scope:
- Block DXVT when material proposal / quotation is rejected
- Audit quotation and price edits after SO
- Track source/intermediate/target warehouse flow
- Generate Techservice master code
- Notify internal team and optional ZNS when quotation is created
- Sync replacement serial automatically from completed delivery

Dependencies:
- dat_website_helpdesk
- dat_sale
- dat_zalo_zns
- sale_stock
- mail

Notes:
- ZNS only sends when ir.config_parameter ts_techservice_flow_guard.zns_template_xmlid is configured
- Built as a safe separate addon to reduce impact on existing modules


Extended scope:
- Rule check button for Techservice data review
- Price impact review marker when prices/materials change
- Merge SO wizard
- Create secondary SO for dual-side SO flow
- Bind order from intermediate warehouse stage

Consolidated customer quotation:
- Select draft Techservice quotations in the quotation list and use
  "Gộp báo giá Techservice", or open the merge wizard from a draft quotation.
- The first quotation is retained as the customer-facing quotation. Source
  lines are copied without quantity aggregation so each product remains
  traceable, while the PDF and customer payment use one grand total.
- Source quotations are cancelled and linked to the consolidated quotation.
- Only draft, unsynchronized quotations with matching customer, company,
  currency, price list, addresses, payment terms, warehouses and SAP document
  settings can be consolidated.
