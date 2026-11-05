import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]

# Designations that belong to each sheet (matched case-insensitively)
DESIGNATIONS = {
	"BDE Traffic Light": [
		"SENIOR BUSINESS DEVELOPNMENT EXECUTIVE",
		"SENIOR BUSINESS DEVELOPMENT EXECUTIVE",
		"BUSINESS DEVELOPMENT EXECUTIVE",
	],
	"ASM Traffic Light": ["AREA SALES MANAGER"],
	"Home Care Traffic Light": ["EXECUTIVE BUSINESS DEVELOPMENT"],
	"Inshop Traffic Light": ["EXECUTIVE BUSINESS DEVELOPMENT"],
	"Gallery Traffic Light": ["SALES EXECUTIVE -GALLERY", "GALLERY INCHARGE"],
}

# Score columns of each sheet: (fieldname, label, maximum). Every sheet adds up to 100.
SHEET_FIELDS = {
	"BDE Traffic Light": [
		("feedback_internal", "Feedback Internal", 5),
		("feedback_external", "Feedback External", 10),
		("meeting", "Meeting", 20),
		("promoter_visit", "Promoter Visit", 10),
		("promoter_conversion", "Promoter Conversion", 15),
		("testimonial", "Testimonial", 5),
		("sales_collection", "Sales & Collection", 35),
	],
	"ASM Traffic Light": [
		("feedback_internal", "Feedback Internal", 5),
		("feedback_external", "Feedback External", 10),
		("meeting", "Meeting", 20),
		("promoter_visit", "Promoter Visit", 10),
		("promoter_conversion", "Promoter Conversion", 15),
		("testimonial", "Testimonial", 5),
		("sales_collection", "Sales & Collection", 35),
	],
	"Home Care Traffic Light": [
		("internal_feedback", "Internal Feedback", 10),
		("external_feedback", "External Feedback", 10),
		("sales_collection", "Sales & Collection", 45),
		("road_show", "Road Show", 20),
		("demo_video", "Demo Video", 15),
	],
	"Inshop Traffic Light": [
		("internal_feedback", "Internal Feedback", 10),
		("external_feedback", "External Feedback", 10),
		("sales_collection", "Sales & Collection", 25),
		("project_conversion", "Project Conversion / Secondary Sales - Inshop", 20),
		("project_visit", "Project Visit / New Product Billing", 5),
		("tea_shop_road_show", "Tea Shop / Road Show", 15),
		("testimonial", "Testimonial", 5),
		("dressing_code", "Dressing Code", 5),
		("display_cleaning", "Display Cleaning", 5),
	],
	"Gallery Traffic Light": [
		("feedback_internal", "Feedback Internal", 10),
		("feedback_external", "Feedback External", 10),
		("sales", "Sales", 40),
		("promoters_meeting", "Promoters Meeting", 20),
		("google_review", "Google Review", 10),
		("makkal_kural_360", "Makkal Kural, 360 Degree", 10),
	],
}

# Starting colour limits for the BDE / ASM columns, fitted to the colours in the Sep'26 BDE sheet.
# fieldname -> (green from, yellow from). Editable later in "Traffic Light Rules".
BDE_DEFAULTS = {
	"feedback_internal": (4, 3),
	"feedback_external": (8, 6),
	"meeting": (15, 10),
	"promoter_visit": (8, 5),
	"promoter_conversion": (11, 8),
	"testimonial": (5, 3),
	"sales_collection": (30, 20),
}
DEFAULTS_BY_SHEET = {"BDE Traffic Light": BDE_DEFAULTS, "ASM Traffic Light": BDE_DEFAULTS}


def get_designations(sheet):
	"""Designations chosen in Traffic Light Rules, otherwise the built-in defaults."""
	chosen = frappe.get_all(
		"Traffic Light Designation",
		filters={"parent": sheet, "parenttype": "Traffic Light Rules"},
		pluck="designation",
		order_by="idx asc",
	)
	return [d for d in chosen if d] or DESIGNATIONS[sheet]


def default_rules(sheet):
	"""key -> {green, yellow, red}. A value >= green is Green, >= yellow Yellow, >= red Red, lower Grey."""
	rules = {"total": {"green": 70, "yellow": 50, "red": 40}}
	for fieldname, _label, maximum in SHEET_FIELDS[sheet]:
		green, yellow = DEFAULTS_BY_SHEET.get(sheet, {}).get(
			fieldname, (round(maximum * 0.8, 2), round(maximum * 0.6, 2))
		)
		rules[fieldname] = {"green": green, "yellow": yellow, "red": 0}
	return rules


def rating_for(value, rule):
	value = flt(value)
	if value >= rule["green"]:
		return "Green"
	if value >= rule["yellow"]:
		return "Yellow"
	if value >= rule["red"]:
		return "Red"
	return "Grey"


@frappe.whitelist()
def get_rules(doctype):
	"""Colour limits for a sheet: Traffic Light Rules if present, otherwise the defaults."""
	if doctype not in SHEET_FIELDS:
		frappe.throw(_("Unknown sheet type."))
	rules = default_rules(doctype)
	if frappe.db.exists("Traffic Light Rules", doctype):
		for row in frappe.get_doc("Traffic Light Rules", doctype).rules:
			rules[row.column_key] = {
				"green": flt(row.green_from),
				"yellow": flt(row.yellow_from),
				"red": flt(row.red_from),
			}
	return rules


def ensure_rule_sets():
	"""Create the five rule sets (and add rows for any new column). Runs after install and migrate."""
	for sheet in SHEET_FIELDS:
		defaults = default_rules(sheet)
		if frappe.db.exists("Traffic Light Rules", sheet):
			doc = frappe.get_doc("Traffic Light Rules", sheet)
		else:
			doc = frappe.new_doc("Traffic Light Rules")
			doc.sheet = sheet
		existing = {r.column_key for r in doc.get("rules", [])}
		entries = [("total", "Total", 100)] + [(fn, label, mx) for fn, label, mx in SHEET_FIELDS[sheet]]
		changed = doc.is_new()
		for key, label, maximum in entries:
			if key not in existing:
				d = defaults[key]
				doc.append(
					"rules",
					{
						"column_key": key,
						"column_label": label,
						"maximum": maximum,
						"green_from": d["green"],
						"yellow_from": d["yellow"],
						"red_from": d["red"],
					},
				)
				changed = True
		# first time only: pre-select the designations that exist in your Designation master
		if not doc.get("designations"):
			for name in DESIGNATIONS[sheet]:
				actual = frappe.db.get_value("Designation", name, "name")
				if actual and actual not in {d.designation for d in doc.get("designations", [])}:
					doc.append("designations", {"designation": actual})
					changed = True
		if changed:
			doc.flags.ignore_permissions = True
			doc.save()
	frappe.db.commit()


def _filter_designations(doctype, designation):
	"""The designations a sheet may list: the chosen one (it must belong to the sheet) or all of them."""
	allowed = get_designations(doctype)
	if designation:
		if designation.casefold() not in {x.casefold() for x in allowed}:
			frappe.throw(_("{0} is not one of the designations for this sheet.").format(designation))
		return [designation]
	return allowed


@frappe.whitelist()
def get_filter_options(doctype, designation=None, branch=None):
	"""Options for the form's filters: the sheet's designations, and the departments that actually
	exist among the matching active employees (so Department follows the other selections)."""
	if doctype not in DESIGNATIONS:
		frappe.throw(_("Unknown sheet type."))
	frappe.has_permission(doctype, "create", throw=True)

	filters = {"designation": ["in", _filter_designations(doctype, designation)], "status": "Active"}
	if branch:
		filters["branch"] = branch
	departments = {d for d in frappe.get_all("Employee", filters=filters, pluck="department") if d}
	return {"designations": get_designations(doctype), "departments": sorted(departments)}


@frappe.whitelist()
def load_employees(doctype, designation=None, department=None, branch=None):
	"""Active employees for the sheet, narrowed by the designation / department / branch picked on the form."""
	if doctype not in DESIGNATIONS:
		frappe.throw(_("Unknown sheet type."))
	frappe.has_permission(doctype, "create", throw=True)

	filters = {"designation": ["in", _filter_designations(doctype, designation)], "status": "Active"}
	if department:
		filters["department"] = department
	if branch:
		filters["branch"] = branch
	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name as employee", "employee_name", "branch"],
		order_by="employee_name asc",
	)

class TrafficLightDocument(Document):
	def validate(self):
		d = getdate(self.date)
		self.month = MONTHS[d.month - 1]
		self.year = d.year
		self.validate_rows()
		self.check_other_sheets()

	def validate_rows(self):
		if not self.items:
			frappe.throw(_("The sheet has no employees."))
		allowed = {x.casefold() for x in get_designations(self.doctype)}
		rules = get_rules(self.doctype)
		seen = set()
		for row in self.items:
			if row.employee in seen:
				frappe.throw(_("Row {0}: {1} is listed more than once.").format(row.idx, row.employee))
			seen.add(row.employee)

			designation = frappe.db.get_value("Employee", row.employee, "designation") or ""
			if designation.casefold() not in allowed:
				frappe.throw(
					_("Row {0}: {1} has designation '{2}', which does not belong to this sheet.").format(
						row.idx, row.employee, designation
					)
				)

			total = 0
			ratings = {}
			for fieldname, label, maximum in SHEET_FIELDS[self.doctype]:
				value = flt(row.get(fieldname))
				if value < 0 or value > maximum:
					frappe.throw(
						_("Row {0} ({1}): {2} must be between 0 and {3}.").format(
							row.idx, row.employee_name or row.employee, label, maximum
						)
					)
				total += value
				ratings[fieldname] = rating_for(value, rules[fieldname])
			row.total = round(total, 2)
			row.rating = rating_for(row.total, rules["total"])
			ratings["total"] = row.rating
			row.ratings = json.dumps(ratings)

	def check_other_sheets(self):
		"""An employee can be scored only once per month on a given sheet type."""
		child_doctype = self.meta.get_field("items").options
		employees = tuple(r.employee for r in self.items)
		rows = frappe.db.sql(
			f"""
			select c.employee, p.name
			from `tab{child_doctype}` c
			inner join `tab{self.doctype}` p on p.name = c.parent
			where p.month = %s and p.year = %s and p.docstatus < 2
				and p.name != %s and c.employee in %s
			""",
			(self.month, self.year, self.name or "", employees),
		)
		if rows:
			frappe.throw(
				_("{0} is already scored for {1} {2} in {3}.").format(
					rows[0][0], self.month, self.year, rows[0][1]
				)
			)
