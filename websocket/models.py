from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class ChatGroup(models.Model):
    name = models.CharField(
        max_length=80,
        validators=[RegexValidator(
            regex=r"\A[A-Za-z0-9_.-]{1,80}\Z",
            message="Use de 1 a 80 letras, números, '.', '_' ou '-'.",
        )],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_chat_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="chat_groups", blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contacts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_by_contacts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "user"], name="unique_owner_contact"),
            models.CheckConstraint(condition=~models.Q(owner=models.F("user")), name="contact_not_self"),
        ]
