from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import AuditLog
from celo.utils import range_start
from inventory.models import Product
from inventory.services import InsufficientStock

from . import services
from .forms import CustomerForm, SaleHeaderForm
from .models import Customer, Order

RANGES = {"today": 0, "7": 6, "15": 14}


def since_for(range_key):
    return range_start(RANGES.get(range_key, 0))


@login_required
def sale_list(request):
    range_key = request.GET.get("range", "today")
    orders = Order.objects.filter(created_at__gte=since_for(range_key)).select_related("customer", "created_by")
    if not request.user.is_celo_admin:        # staff see their own transactions only
        orders = orders.filter(created_by=request.user)
    gross = orders.aggregate(t=Sum("total"))["t"] or Decimal("0")
    return render(request, "sales/sale_list.html", {
        "orders": orders[:200], "gross": gross, "range": range_key,
    })


@login_required
def sale_new(request):
    """Tap-to-order screen: one stepper per menu item (fields named qty_<product id>)."""
    menu = list(Product.objects.filter(kind=Product.Kind.MENU, is_active=True).order_by("category", "name"))
    quantities = {}
    if request.method == "POST":
        for p in menu:
            raw = request.POST.get(f"qty_{p.pk}", "").strip()
            if raw.isdigit() and int(raw) > 0:
                quantities[p.pk] = int(raw)
    header = SaleHeaderForm(request.POST or None)

    if request.method == "POST" and header.is_valid():
        lines = [(p, quantities[p.pk]) for p in menu if p.pk in quantities]
        if not lines:
            messages.error(request, "Add at least one item to the order.")
        else:
            try:
                order = services.place_order(
                    user=request.user, customer=header.cleaned_data["customer"],
                    order_type=header.cleaned_data["order_type"],
                    payment_method=header.cleaned_data["payment_method"], lines=lines,
                )
            except InsufficientStock as exc:
                messages.error(request, str(exc))
            else:
                AuditLog.record(request.user, "New sale", f"{order} PHP {order.total}")
                return redirect("sales:receipt", pk=order.pk)

    items = [{"p": p, "stock": p.on_hand, "qty": quantities.get(p.pk, 0)} for p in menu]
    return render(request, "sales/sale_form.html", {"header": header, "items": items})


@login_required
def receipt(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer", "created_by"), pk=pk)
    if not request.user.is_celo_admin and order.created_by_id != request.user.id:
        return redirect("sales:list")
    return render(request, "sales/receipt.html", {"order": order, "items": order.items.select_related("product")})


@login_required
def customer_lookup(request):
    q = request.GET.get("q", "").strip()
    customers = Customer.objects.all()
    if q:
        customers = customers.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    return render(request, "sales/customer_list.html", {"customers": customers[:50], "q": q})


@login_required
def customer_edit(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk) if pk else None
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("sales:customers")
    return render(request, "form_card.html", {
        "title": "Edit customer" if customer else "Add customer", "form": form,
        "submit": "Save", "cancel_url": "sales:customers",
    })
