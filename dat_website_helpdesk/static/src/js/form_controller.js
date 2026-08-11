/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { evaluateExpr } from "@web/core/py_js/py";
import { FormController} from "@web/views/form/form_controller";

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        let context = clickParams.context;
        if (context) {
            if (typeof context === "string") {
                context = evaluateExpr(context);
            }
            if (context.reject_button && context.reject_button === true) {
                return true;
            }
        }
        return super.beforeExecuteActionButton(clickParams);
    }
});
