from django.contrib import admin
from .models import ChatGroup


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "created_at"]
    search_fields = ["name"]
    filter_horizontal = ["users"]

# Register your models here.
