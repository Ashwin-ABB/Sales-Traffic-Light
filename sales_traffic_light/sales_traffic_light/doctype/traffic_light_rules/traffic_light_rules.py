import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sales_traffic_light.traffic_light import SHEET_FIELDS


class TrafficLightRules(Document):
	def validate(self):
		chosen = [d.designation for d in self.get("designations", [])]
		if len(chosen) != len(set(chosen)):
			frappe.throw(_("A designation is listed more than once."))
		maxima = {"total": 100}
		for fieldname, _label, maximum in SHEET_FIELDS[self.sheet]:
			maxima[fieldname] = maximum
		for row in self.rules:
			green, yellow, red = flt(row.green_from), flt(row.yellow_from), flt(row.red_from)
			maximum = maxima.get(row.column_key, 100)
			if not (0 <= red < yellow < green <= maximum):
				frappe.throw(
					_("Row {0} ({1}): limits must satisfy 0 <= Red < Yellow < Green <= {2}.").format(
						row.idx, row.column_label, maximum
					)
				)
