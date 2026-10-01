from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ChatGroup, Contact


class ChatGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatGroup
        fields = ["id", "name", "users", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


class AddChatGroupUsersSerializer(serializers.Serializer):
    users = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(), many=True, allow_empty=False,
    )


class ContactSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.get_username", read_only=True)

    class Meta:
        model = Contact
        fields = ["id", "user", "username", "created_at"]
        read_only_fields = ["id", "username", "created_at"]

    def validate_user(self, user):
        if user.pk == self.context["request"].user.pk:
            raise serializers.ValidationError("Você não pode adicionar a si mesmo aos contatos.")
        return user
