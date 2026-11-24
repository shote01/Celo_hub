## Run it
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts inventory sales finance dashboard
python manage.py migrate
python manage.py seed_demo          # optional sample data
python manage.py test               # FIFO + payroll tests
python manage.py runserver
```
Demo logins (after `seed_demo`): `admin / celo-admin-123`, `cashier / celo-staff-123`.
Create real users in `/admin/` and set their **Role** (Admin or Staff). Change the demo passwords first.

## Charter -> code map
| Charter feature | Where |
|---|---|
| Product & menu management | `inventory` Product, `/inventory/products/` (admin) |
| Stock & expiration, FIFO | `inventory/services.py` `consume_fifo`, `/inventory/` |
| Sales transactions + receipt | `sales/services.py` `place_order`, `/sales/`, receipt page (printable) |
| Waste module (deducts stock & revenue) | `inventory` WasteRecord, `/inventory/waste/` |
| Expenses, rent, utilities | `finance` Expense, `/finance/expenses/` |
| Payroll & cash advances | `finance` PayrollRecord / CashAdvance, `/finance/payroll/` |
| Daily/weekly/monthly/yearly reports, bestsellers | `dashboard/services.py`, `/reports/` (+ CSV) |
| Login & roles, audit log | `accounts` User.role, AuditLog, `/audit/` |
| Customer lookup & profiles | `sales` Customer, `/sales/customers/` |

## Profile, employees and attendance pay
* **Profile settings** (`/account/profile/`, any user): change your name/email and your password. Click your name at the bottom of the sidebar.
* **Employees** (`/finance/employees/`, admin): add, edit, deactivate/reactivate or delete employees. When adding, an admin can create the
  employee's login at the same time. Employees with payroll or attendance history can only be deactivated, never deleted.
* **Attendance pay**: payroll can now be paid as *Attendance*. Daily rate = base salary / `CELO_WORK_DAYS_PER_PERIOD` (13, see settings);
  pay = daily rate x days present in the current 15-day period. A day counts once the employee timed in, even if they forgot to time out
  (those days are flagged). Every payroll record also stores the days and hours worked. Apply with `python manage.py migrate` (finance 0004).