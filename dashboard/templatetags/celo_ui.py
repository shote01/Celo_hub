from django import template
from django.urls import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def nav_items(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return []

    is_admin = getattr(user, "is_celo_admin", False)
    path = getattr(request, "path", "")

    def item(label, icon, url_name, active_prefix):
        href = reverse(url_name)
        return {
            "label": label,
            "icon": icon,
            "href": href,
            "active": path.startswith(active_prefix),
        }

    groups = [
        {
            "label": "Overview",
            "items": [item("Dashboard", "home", "dashboard:home", "/")],
        },
        {
            "label": "Operations",
            "items": [
                item("Sales", "sale", "sales:list", "/sales/"),
                item("Inventory", "box", "inventory:stock", "/inventory/"),
            ],
        },
        {
            "label": "People & Finance",
            "items": [
                item("Attendance", "clock", "finance:attendance", "/finance/attendance/"),
            ],
        },
    ]

    if is_admin:
        groups[1]["items"].append(
            item("Customers", "users", "sales:customers", "/sales/customers/")
        )
        groups[2]["items"].extend([
            item("Employees", "briefcase", "finance:employees", "/finance/employees/"),
            item("Expenses", "receipt", "finance:expenses", "/finance/expenses/"),
            item("Payroll", "wallet", "finance:payroll", "/finance/payroll/"),
        ])
        groups.append({
            "label": "Administration",
            "items": [
                item("Reports", "chart", "dashboard:reports", "/reports/"),
                item("Audit log", "shield", "dashboard:audit", "/audit/"),
            ],
        })

    # Highlight only the most specific match (so /sales/customers/ lights up Customers, not Sales too).
    best = None
    for group in groups:
        for nav_item in group["items"]:
            href = nav_item["href"]
            matches = path == "/" if href == "/" else path.startswith(href)
            if matches and (best is None or len(href) > len(best["href"])):
                best = nav_item
            nav_item["active"] = False
    if best is not None:
        best["active"] = True

    return groups
