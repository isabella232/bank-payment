# Copyright 2020 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    selected_for_payment = fields.Boolean("To Pay")

    def action_select_for_payment(self):
        self.filtered(lambda rec: not rec.selected_for_payment).write(
            {"selected_for_payment": True}
        )

    def action_unselect_for_payment(self):
        self.filtered(lambda rec: rec.selected_for_payment).write(
            {"selected_for_payment": False}
        )
