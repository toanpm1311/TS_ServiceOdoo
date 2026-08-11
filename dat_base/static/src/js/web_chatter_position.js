/** @odoo-module **/

import {FormCompiler} from "@web/views/form/form_compiler";
import {patch} from "@web/core/utils/patch";
import {append, setAttributes} from "@web/core/utils/xml";
import {SIZES} from "@web/core/ui/ui_service";

patch(FormCompiler.prototype, {
    /**
     * @override
     */
    compile(node, params) {
        const res = super.compile(node, params);
        const webClientViewAttachmentViewHookXml = res.querySelector(
            ".o_attachment_preview"
        );
        const chatterContainerHookXml = res.querySelector(
            ".o-mail-Form-chatter:not(.o-isInFormSheetBg)"
        );
        if (!chatterContainerHookXml) {
            return res; // No chatter, keep the result as it is
        }
        const chatterContainerXml = chatterContainerHookXml.querySelector(
            "t[t-component='__comp__.mailComponents.Chatter']"
        );
        const formSheetBgXml = res.querySelector(".o_form_sheet_bg");
        const parentXml = formSheetBgXml && formSheetBgXml.parentNode;
        if (!parentXml) {
            return res; // Miss-config: a sheet-bg is required for the rest
        }

        if (webClientViewAttachmentViewHookXml) {
            setAttributes(webClientViewAttachmentViewHookXml, {
                "t-if": "false",
            });
        }

        if (webClientViewAttachmentViewHookXml) {
            const sheetBgChatterContainerHookXml = res.querySelector(
                ".o-mail-Form-chatter.o-isInFormSheetBg"
            );
            setAttributes(sheetBgChatterContainerHookXml, {
                "t-if": "true",
            });
            setAttributes(chatterContainerHookXml, {
                "t-if": "false",
            });
        } else {
            const sheetBgChatterContainerHookXml =
                chatterContainerHookXml.cloneNode(true);
            sheetBgChatterContainerHookXml.classList.add("o-isInFormSheetBg");
            setAttributes(sheetBgChatterContainerHookXml, {
                "t-if": "true",
                "t-attf-class": `{{ (__comp__.uiService.size >= ${SIZES.XXL}) ? "o-aside" : "mt-4 mt-md-0" }}`,
            });
            append(formSheetBgXml, sheetBgChatterContainerHookXml);
            const sheetBgChatterContainerXml =
                sheetBgChatterContainerHookXml.querySelector(
                    "t[t-component='__comp__.mailComponents.Chatter']"
                );

            setAttributes(sheetBgChatterContainerXml, {
                isInFormSheetBg: "true",
            });
            setAttributes(chatterContainerHookXml, {
                "t-if": "false",
            });
        }

        return res;
    },
});
