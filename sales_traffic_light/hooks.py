app_name = "sales_traffic_light"
app_title = "Sales Team Traffic Light"
app_publisher = "Pupa"
app_description = "Monthly traffic light score sheets for the sales team"
app_email = "admin@example.com"
app_license = "mit"
required_apps = ["frappe", "hrms"]

after_install = "sales_traffic_light.traffic_light.ensure_rule_sets"
after_migrate = ["sales_traffic_light.traffic_light.ensure_rule_sets"]
