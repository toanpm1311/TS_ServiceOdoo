/* @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Record } from "@web/model/relational_model/record";
import { markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { escape } from "@web/core/utils/strings";


patch(Record.prototype, {
    _checkValidity({ silent, displayNotification } = {}) {
        const unsetRequiredFields = [];
        const checkValidityNumber = (fieldName) => {
            if (this.data[fieldName] === false && this._isRequired(fieldName)) {
                unsetRequiredFields.push(fieldName);
            }
        };

        for (const fieldName in this.activeFields) {
            const fieldType = this.fields[fieldName].type;
            if (this._isInvisible(fieldName) || this.fields[fieldName].relatedPropertyField) {
                continue;
            }
            switch (fieldType) {
                case "boolean":
                case "float":
                    checkValidityNumber(fieldName);
                    break;
                case "integer":
                    checkValidityNumber(fieldName);
                    break;
                case "monetary":
                    continue;
                case "html":
                    if (this._isRequired(fieldName) && this.data[fieldName].length === 0) {
                        unsetRequiredFields.push(fieldName);
                    }
                    break;
                case "one2many":
                case "many2many": {
                    const list = this.data[fieldName];
                    if (
                        (this._isRequired(fieldName) && !list.count) ||
                        !list.records.every((r) => !r.dirty || r._checkValidity({ silent }))
                    ) {
                        unsetRequiredFields.push(fieldName);
                    }
                    break;
                }
                case "properties": {
                    const value = this.data[fieldName];
                    if (value) {
                        const ok = value.every(
                            (propertyDefinition) =>
                                propertyDefinition.name &&
                                propertyDefinition.name.length &&
                                propertyDefinition.string &&
                                propertyDefinition.string.length
                        );
                        if (!ok) {
                            unsetRequiredFields.push(fieldName);
                        }
                    }
                    break;
                }
                case "json": {
                    if (
                        this._isRequired(fieldName) &&
                        (!this.data[fieldName] || !Object.keys(this.data[fieldName]).length)
                    ) {
                        unsetRequiredFields.push(fieldName);
                    }
                    break;
                }
                default:
                    if (!this.data[fieldName] && this._isRequired(fieldName)) {
                        unsetRequiredFields.push(fieldName);
                    }
            }
        }

        if (silent) {
            return !unsetRequiredFields.length;
        }

        for (const fieldName of Array.from(this._unsetRequiredFields)) {
            this._invalidFields.delete(fieldName);
        }
        this._unsetRequiredFields.clear();
        for (const fieldName of unsetRequiredFields) {
            this._unsetRequiredFields.add(fieldName);
            this._setInvalidField(fieldName);
        }
        const isValid = !this._invalidFields.size;
        if (!isValid && displayNotification) {
            const items = [...this._invalidFields].map((fieldName) => {
                return `<li>${escape(this.fields[fieldName].string || fieldName)}</li>`;
            }, this);
            this._closeInvalidFieldsNotification = this.model.notification.add(
                markup(`<ul>${items.join("")}</ul>`),
                {
                    title: _t("Invalid fields: "),
                    type: "danger",
                }
            );
        }
        return isValid;
    }
});
