# -*- coding: utf-8 -*-
# Copyright (c) 2019, 9T9IT and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from erpnext.controllers.item_variant import (ItemVariantExistsError,
		copy_attributes_to_variant, get_variant, make_variant_item_code, validate_item_variant_attributes)
from frappe.utils import (cint, cstr, flt, formatdate, get_timestamp, getdate,
						  now_datetime, random_string, strip)

def before_naming(doc, method):
	"""
		item_group_abbr: used in Item naming_series
		forced_name: temporary field to handle manual_item_code
	"""
	doc.item_group_abbr = (
		frappe.db.get_value("Item Group", doc.item_group, "item_group_abbr") or "XX"
	)
	if doc.manual_item_code:
		doc.forced_name = doc.item_code

def custom_autoname_before_insert(doc, method):
	try:
		if doc.item_code == '' or doc.item_code == None or not doc.item_code:
			if frappe.db.get_default("item_naming_by") == "Naming Series":
				if doc.variant_of:
					if not doc.item_code:
						template_item_name = frappe.db.get_value("Item", doc.variant_of, "item_name")
						doc.item_code = make_variant_item_code(doc.variant_of, template_item_name, doc)
				else:
					from frappe.model.naming import set_name_by_naming_series
					set_name_by_naming_series(doc)
					doc.item_code = doc.name

			doc.item_code = strip(doc.item_code)
			doc.name = doc.item_code
	except Exception as e:
		  frappe.throw(f"{e}")

def autoname(doc, method):
	if doc.get("forced_name"):
		doc.name = doc.forced_name
		doc.item_code = doc.forced_name
	if doc.item_code == '' or doc.item_code == None or not doc.item_code:
		custom_autoname_before_insert(doc, method)
		


def validate(doc, method):
	existing_item_name = frappe.db.exists(
		"Item", {"item_name": doc.item_name, "name": ("!=", doc.name)}
	)
	if existing_item_name:
		frappe.throw(
			frappe._("Item Name '{}' already exists in Item {}").format(
				doc.item_name, existing_item_name
			)
		)
	existing_description = frappe.db.exists(
		"Item", {"description": doc.description, "name": ("!=", doc.name)}
	)
	if existing_description:
		frappe.throw(
			frappe._("Item Description '{}' already exists in Item {}").format(
				doc.description, existing_description
			)
		)

	if doc.is_gift_card and not doc.gift_card_value:
		frappe.throw(_("Gift Card value is required."))
	if doc.is_gift_card and doc.no_of_months:
		frappe.throw(_("No of Months for Deferred Revenue needs to be zero."))


def after_insert(doc, method):
	def add_price(price_list, price):
		if flt(price) and frappe.db.exists(
			"Price List", {"price_list_name": price_list}
		):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": price_list,
					"item_code": doc.item_code,
					"currency": frappe.defaults.get_global_default("currency"),
					"price_list_rate": price,
				}
			).insert()

	field_pl_map = {
		"Minimum Selling": doc.os_minimum_selling_rate,
		"Minimum Selling 2": doc.os_minimum_selling_2_rate,
		"Wholesale": doc.os_wholesale_rate,
		"Standard Buying": doc.os_cost_price,
	}
	map(lambda x: add_price(*x), field_pl_map.items())


def before_save(doc, method):
	if doc.is_gift_card:
		doc.has_serial_no = 1
		doc.enable_deferred_revenue = 1
		doc.no_of_months = 0
		if not doc.deferred_revenue_account:
			doc.deferred_revenue_account = frappe.db.get_single_value(
				"Optical Store Settings", "gift_card_deferred_revenue"
			)
	if not doc.os_has_commission:
		doc.os_commissions = []
