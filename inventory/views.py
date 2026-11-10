from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import AuditLog
from accounts.permissions import admin_required

from . import services
from .forms import ProductForm, ReceiveStockForm, WasteForm
from .models import Product, WasteRecord


@login_required
def stock_list(request):
    """Design screen: 'Stock & expiration'. Menu items and ingredients are listed separately."""
    kind = request.GET.get("kind", "")
    q = request.GET.get("q", "").strip()
    products = Product.objects.filter(is_active=True)
    if q:
        batch_no = q.lstrip("#")
        match = Q(name__icontains=q)
        if batch_no.isdigit():
            match |= Q(batches__id=int(batch_no))
        products = products.filter(match).distinct()
    menu = products.filter(kind=Product.Kind.MENU) if kind != Product.Kind.INGREDIENT else Product.objects.none()
    ingredients = products.filter(kind=Product.Kind.INGREDIENT) if kind != Product.Kind.MENU else Product.objects.none()
    return render(request, "inventory/stock_list.html", {
        "menu": menu, "ingredients": ingredients, "kind": kind, "q": q,
        "show_menu": kind != Product.Kind.INGREDIENT, "show_ingredients": kind != Product.Kind.MENU,
    })


@login_required
def receive_stock(request):
    form = ReceiveStockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        batch = services.receive_stock(
            product=d["product"], quantity=d["amount"], expiry_date=d["expiry_date"], user=request.user
        )
        AuditLog.record(request.user, "Received stock", f"{d['amount']} {d['product'].unit} {d['product']} (batch #{batch.pk})")
        messages.success(request, f"Saved: {d['amount']} {d['product'].unit} of {d['product']}.")
        return redirect("inventory:stock")
    return render(request, "form_card.html", {
        "title": "Receive stock", "form": form, "submit": "Save record", "cancel_url": "inventory:stock",
    })


@login_required
def waste_list(request):
    return render(request, "inventory/waste_list.html", {"records": WasteRecord.objects.select_related("product")[:100]})


@login_required
def record_waste(request):
    form = WasteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            w = services.record_waste(product=d["product"], quantity=d["quantity"], reason=d["reason"],
                                      note=d["note"], user=request.user)
        except services.InsufficientStock as exc:
            form.add_error("quantity", str(exc))
        else:
            AuditLog.record(request.user, "Logged waste", f"{w.quantity} {w.product.unit} {w.product} = PHP {w.cost}")
            messages.success(request, f"Waste logged (PHP {w.cost}).")
            return redirect("inventory:waste")
    return render(request, "form_card.html", {
        "title": "Log waste", "form": form, "submit": "Save record", "cancel_url": "inventory:waste",
    })


# ---- product & menu management (admin) -------------------------------------
@admin_required
def product_list(request):
    return render(request, "inventory/product_list.html", {"products": Product.objects.all()})


@admin_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        AuditLog.record(request.user, "Edited product" if product else "Added product", obj.name)
        return redirect("inventory:products")
    return render(request, "form_card.html", {
        "title": "Edit product" if product else "Add product", "form": form,
        "submit": "Save", "cancel_url": "inventory:products",
    })


@admin_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        name = product.name
        try:
            product.delete()
        except ProtectedError:  # protected by waste/sales history -> archive instead
            product.is_active = False
            product.save(update_fields=["is_active"])
            messages.info(request, f"{name} has history, so it was archived instead of deleted.")
        else:
            messages.success(request, f"{name} deleted.")
        AuditLog.record(request.user, "Removed product", name)
        return redirect("inventory:products")
    return render(request, "confirm_delete.html", {"object": product, "cancel_url": "inventory:products"})
