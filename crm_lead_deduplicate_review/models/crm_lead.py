# Copyright 2026 Ledo Enterprises
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Leads merge through CRM's own merge steps, into the lead a person chose.

``crm.lead._merge_opportunity`` always picks its own head -- the most advanced
lead -- so a reviewer's choice of the lead to keep cannot be honoured through
it. The steps it is made of can: field values (with every module's extension
of them, e.g. sale orders and event registrations), followers, the summary
note, messages, attachments and calendar events. They run here on the chosen
head. Then the engine's safe merge moves whatever they leave behind, notably
the followers CRM keeps only when they posted in the last 30 days.
"""

from odoo import models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    _deduplicate_has_strategy = True

    def _deduplicate_merge_records(self, master, sources):
        leads = master | sources  # head first: its values take priority
        merged_data = leads._merge_data(self._merge_get_fields())
        merged_followers = master._merge_followers(sources)
        master._merge_log_summary(merged_followers, sources)
        master._merge_dependences(sources)
        if merged_data.get("team_id"):
            stages = self.env["crm.stage"].search(
                [
                    "|",
                    ("team_ids", "in", merged_data["team_id"]),
                    ("team_ids", "=", False),
                ],
                order="sequence, id",
            )
            if merged_data.get("stage_id") not in stages.ids:
                merged_data["stage_id"] = stages[:1].id
        for fname in ("user_id", "team_id"):
            if fname in merged_data and master[fname].id == merged_data[fname]:
                merged_data.pop(fname)
        master.write(merged_data)
        return self._deduplicate_merge_generic(master, sources)

    def _deduplicate_log_merge(self, master, summary, aliases):
        # CRM's merge already logged its summary on the lead kept.
        if aliases.identifier_ids:
            return super()._deduplicate_log_merge(master, summary, aliases)
