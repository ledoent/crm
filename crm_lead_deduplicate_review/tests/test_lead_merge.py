# Copyright 2026 Ledo Enterprises
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestLeadMerge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reviewer = new_test_user(
            cls.env,
            login="cld_reviewer",
            groups="base.group_user,sales_team.group_sale_salesman,"
            "base_deduplicate_review.group_deduplicate_reviewer",
        )
        cls.manager = new_test_user(
            cls.env,
            login="cld_manager",
            groups="base.group_user,sales_team.group_sale_salesman,"
            "base_deduplicate_review.group_deduplicate_manager",
        )
        Stage = cls.env["crm.stage"]
        cls.early = Stage.create({"name": "CLD early", "sequence": 1})
        cls.late = Stage.create({"name": "CLD late", "sequence": 90})
        cls.Lead = cls.env["crm.lead"]

    def setUp(self):
        super().setUp()
        self.keep = self.Lead.create(
            {"name": "CLD Keep", "type": "lead", "email_from": "k@example.com"}
        )
        self.gone = self.Lead.create(
            {
                "name": "CLD Gone",
                "type": "opportunity",
                "stage_id": self.late.id,
                "email_from": "g@example.com",
                "probability": 80,
            }
        )

    def merge(self):
        return self.Lead._deduplicate_merge(self.keep, self.gone)

    def test_the_chosen_lead_survives_even_when_crm_would_keep_the_other(self):
        self.assertEqual(
            (self.keep | self.gone)._sort_by_confidence_level(reverse=True)[0],
            self.gone,
            "the fixture must be one CRM's own merge would get the other way round",
        )
        self.merge()
        self.assertTrue(self.keep.exists())
        self.assertFalse(self.gone.exists())
        self.assertEqual(self.keep.type, "opportunity")

    def test_followers_who_never_posted_are_kept(self):
        watcher = self.env["res.partner"].create({"name": "CLD Watcher"})
        self.gone.message_subscribe(partner_ids=watcher.ids)
        self.merge()
        self.assertIn(watcher, self.keep.message_partner_ids)

    def test_messages_activities_and_events_move(self):
        self.gone.message_post(body="CLD note")
        activity = self.gone.activity_schedule(
            "mail.mail_activity_data_todo", summary="CLD call"
        )
        start = fields.Datetime.now()
        event = self.env["calendar.event"].create(
            {
                "name": "CLD meeting",
                "start": start,
                "stop": start + timedelta(hours=1),
                "opportunity_id": self.gone.id,
                "res_model_id": self.env["ir.model"]._get("crm.lead").id,
                "res_id": self.gone.id,
            }
        )
        self.merge()
        self.assertIn("CLD note", "".join(self.keep.message_ids.mapped("body")))
        self.assertEqual(activity.res_id, self.keep.id)
        self.assertEqual(event.opportunity_id, self.keep)

    def test_tags_are_a_union(self):
        Tag = self.env["crm.tag"]
        one, two = Tag.create({"name": "CLD one"}), Tag.create({"name": "CLD two"})
        self.keep.tag_ids = one
        self.gone.tag_ids = one | two
        self.merge()
        self.assertEqual(self.keep.tag_ids, one | two)

    def test_identifiers_of_the_merged_lead_are_kept(self):
        with patch.object(
            type(self.Lead), "_deduplicate_alias_fields", lambda self: ["email_from"]
        ):
            self.merge()
        self.assertEqual(
            self.env["deduplicate.alias"].resolve_identifiers(
                "crm.lead", "email_from", ["g@example.com"]
            ),
            {"g@example.com": self.keep.id},
        )

    def test_the_review_flow_merges_leads_without_any_override(self):
        twin = self.Lead.create(
            {"name": "CLD Keep twin", "type": "lead", "email_from": "K@example.com"}
        )
        rule = self.env.ref("crm_lead_deduplicate_review.rule_lead_email")
        self.assertFalse(rule.active)
        rule.write({"active": True, "domain": "[('name', '=like', 'CLD %')]"})
        rule._find_duplicates()
        group = self.env["deduplicate.group"].search(
            [("rule_id", "=", rule.id), ("record_ids.res_id", "=", twin.id)]
        )
        self.assertEqual(
            set(group.record_ids.mapped("res_id")), {self.keep.id, twin.id}
        )
        group.with_user(self.reviewer).action_validate()
        group.with_user(self.manager).action_merge()
        self.assertFalse(twin.exists())
        self.assertTrue(self.keep.exists())
