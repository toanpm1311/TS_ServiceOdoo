from odoo import _, models, api
from odoo.exceptions import UserError


class TechnicalProposal(models.Model):
    _name = 'technical.proposal'
    _inherit = ['technical.proposal', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/GetAvailableInventory'

    def action_update_stock(self):

        for order in self:
            if not order.technical_proposal_line_ids:
                raise UserError(_('Please add at least one line before check on hand quantity.'))

            product_ids = order.get_product_list()
            stock_data = self.sync_stock_data(product_ids)
            if not stock_data:
                continue

            stock_dict = {}

            for item in stock_data:
                code = item.get('ItemCode')
                qty = item.get('TonKhaDung', 0)
                stock_dict[code] = qty
            for line in order.technical_proposal_line_ids:
                code = line.product_id.default_code
                line.onhand_quantity = stock_dict.get(code, 0)

        return True

    def get_product_list(self):
        codes = [line.product_id.default_code for line in self.technical_proposal_line_ids]
        return list(dict.fromkeys(codes))

    @api.model
    def sync_stock_data(self, product_code_lst: list[str]):
        try:
            if len(product_code_lst) == 0:
                return
            list_product_code_str = ",".join(product_code_lst)
            json_vendor_data = {
                "Item": list_product_code_str,
            }

            sap_vendor_result = self.get_result(json=json_vendor_data, result_text='ListAvailableInventory')
            return sap_vendor_result
        except UserError as err:
            raise UserError(str(err))

