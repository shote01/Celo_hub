from django.contrib import admin

from .models import Product, StockBatch, WasteRecord

admin.site.register(Product)
admin.site.register(StockBatch)
admin.site.register(WasteRecord)
