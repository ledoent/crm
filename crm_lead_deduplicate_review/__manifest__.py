# Copyright 2026 Ledo Enterprises
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "CRM Lead Deduplication Review",
    "summary": "Review duplicate leads and merge them into the one you choose",
    "version": "20.0.1.0.0",
    "author": "Ledo Enterprises, Odoo Community Association (OCA)",
    "maintainers": ["dnplkndll"],
    "development_status": "Alpha",
    "website": "https://github.com/OCA/crm",
    "category": "Sales/CRM",
    "license": "AGPL-3",
    "depends": ["base_deduplicate_review", "crm"],
    "data": [
        "data/deduplicate_rule_data.xml",
        "views/crm_lead_views.xml",
    ],
    "installable": True,
}
