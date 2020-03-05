# © 2014-2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# © 2014 Serv. Tecnol. Avanzados - Pedro M. Baeza
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo import api, fields, models
from odoo.fields import first

from odoo.addons.base.models.ir_ui_view import (
    transfer_field_to_modifiers,
    transfer_modifiers_to_node,
    transfer_node_to_modifiers,
)


def setup_modifiers(node, field=None, context=None, in_tree_view=False):
    """ Processes node attributes and field descriptors to generate
    the ``modifiers`` node attribute and set it on the provided node.

    Alters its first argument in-place.

    :param node: ``field`` node from an OpenERP view
    :type node: lxml.etree._Element
    :param dict field: field descriptor corresponding to the provided node
    :param dict context: execution context used to evaluate node attributes
    :param bool in_tree_view: triggers the ``column_invisible`` code
                              path (separate from ``invisible``): in
                              tree view there are two levels of
                              invisibility, cell content (a column is
                              present but the cell itself is not
                              displayed) with ``invisible`` and column
                              invisibility (the whole column is
                              hidden) with ``column_invisible``.
    :returns: nothing
    """
    modifiers = {}
    if field is not None:
        transfer_field_to_modifiers(field, modifiers)
    transfer_node_to_modifiers(
        node, modifiers, context=context, in_tree_view=in_tree_view
    )
    transfer_modifiers_to_node(modifiers, node)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    partner_bank_id = fields.Many2one(
        comodel_name="res.partner.bank",
        string="Partner Bank Account",
        help="Bank account on which we should pay the supplier",
    )
    bank_payment_line_id = fields.Many2one(
        comodel_name="bank.payment.line", readonly=True, index=True
    )
    payment_line_ids = fields.One2many(
        comodel_name="account.payment.line",
        inverse_name="move_line_id",
        string="Payment lines",
    )

    def _prepare_payment_line_vals(self, payment_order):
        self.ensure_one()
        assert payment_order, "Missing payment order"
        aplo = self.env["account.payment.line"]
        # default values for communication_type and communication
        communication_type = "normal"
        communication = self.ref or self.name
        # change these default values if move line is linked to an invoice
        if self.move_id.is_invoice():
            if self.move_id.reference_type != "none":
                communication = self.move_id.ref
                ref2comm_type = aplo.invoice_reference_type2communication_type()
                communication_type = ref2comm_type[self.move_id.reference_type]
            else:
                if (
                    self.move_id.type in ("in_invoice", "in_refund")
                    and self.move_id.ref
                ):
                    communication = self.move_id.ref
                elif "out" in self.move_id.type:
                    # Force to only put invoice number here
                    communication = self.move_id.name
        if self.currency_id:
            currency_id = self.currency_id.id
            amount_currency = self.amount_residual_currency
        else:
            currency_id = self.company_id.currency_id.id
            amount_currency = self.amount_residual
            # TODO : check that self.amount_residual_currency is 0
            # in this case
        if payment_order.payment_type == "outbound":
            amount_currency *= -1
        partner_bank_id = self.partner_bank_id.id or first(self.partner_id.bank_ids).id
        vals = {
            "order_id": payment_order.id,
            "partner_bank_id": partner_bank_id,
            "partner_id": self.partner_id.id,
            "move_line_id": self.id,
            "communication": communication,
            "communication_type": communication_type,
            "currency_id": currency_id,
            "amount_currency": amount_currency,
            # date is set when the user confirms the payment order
        }
        return vals

    def create_payment_line_from_move_line(self, payment_order):
        vals_list = []
        for mline in self:
            vals_list.append(mline._prepare_payment_line_vals(payment_order))
        return self.env["account.payment.line"].create(vals_list)

    @api.model
    def fields_view_get(
        self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):
        # When the user looks for open payables or receivables, in the
        # context of payment orders, she should focus primarily on amount that
        # is due to be paid, and secondarily on the total amount. In this
        # method we are forcing to display both the amount due in company and
        # in the invoice currency.
        # We then hide the fields debit and credit, because they add no value.
        result = super(AccountMoveLine, self).fields_view_get(
            view_id, view_type, toolbar=toolbar, submenu=submenu
        )

        doc = etree.XML(result["arch"])
        if view_type == "tree" and self._module == "account_payment_order":
            if not doc.xpath("//field[@name='balance']"):
                for placeholder in doc.xpath("//field[@name='amount_currency']"):
                    elem = etree.Element(
                        "field", {"name": "balance", "readonly": "True"}
                    )
                    setup_modifiers(elem)
                    placeholder.addprevious(elem)
            if not doc.xpath("//field[@name='amount_residual_currency']"):
                for placeholder in doc.xpath("//field[@name='amount_currency']"):
                    elem = etree.Element(
                        "field",
                        {"name": "amount_residual_currency", "readonly": "True"},
                    )
                    setup_modifiers(elem)
                    placeholder.addnext(elem)
            if not doc.xpath("//field[@name='amount_residual']"):
                for placeholder in doc.xpath("//field[@name='amount_currency']"):
                    elem = etree.Element(
                        "field", {"name": "amount_residual", "readonly": "True"}
                    )
                    setup_modifiers(elem)
                    placeholder.addnext(elem)
            # Remove credit and debit data - which is irrelevant in this case
            for elem in doc.xpath("//field[@name='debit']"):
                doc.remove(elem)
            for elem in doc.xpath("//field[@name='credit']"):
                doc.remove(elem)
            result["arch"] = etree.tostring(doc)
        return result
