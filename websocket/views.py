from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ChatGroup, Contact
from .serializers import AddChatGroupUsersSerializer, ChatGroupSerializer, ContactSerializer


class ChatGroupListCreateView(generics.ListCreateAPIView):
    queryset = ChatGroup.objects.prefetch_related("users").all()
    serializer_class = ChatGroupSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            group = serializer.save(created_by=self.request.user)
            group.users.add(self.request.user)


class MyChatGroupListView(generics.ListAPIView):
    serializer_class = ChatGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.chat_groups.prefetch_related("users").all()


class ChatGroupAddUsersView(generics.GenericAPIView):
    serializer_class = AddChatGroupUsersSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatGroup.objects.filter(users=self.request.user)

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            group.users.add(*serializer.validated_data["users"])
        return Response(ChatGroupSerializer(group).data)


class ContactListCreateView(generics.ListCreateAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Contact.objects.filter(owner=self.request.user).select_related("user")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact, created = Contact.objects.get_or_create(
            owner=request.user, user=serializer.validated_data["user"],
        )
        return Response(
            self.get_serializer(contact).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ContactDestroyView(generics.DestroyAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Contact.objects.filter(owner=self.request.user)
