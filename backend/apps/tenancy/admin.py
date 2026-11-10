from django.contrib import admin

from .models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "ownership", "status", "city")
    list_editable = ("status",)
    list_filter = ("status",)
    search_fields = ("name", "slug")
