"""
Tests for tags API
"""
from decimal import Decimal

from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.utils import create_user as _create_user
from core.models import Tag, Recipe
from recipe.serializers import TagSerializer


TAGS_URL = reverse("recipe:tag-list")

def detail_url(tag_id):
    return reverse("recipe:tag-detail", args=[tag_id])


def create_user(email="user@example.com", password="testpass123"):
    return _create_user(email, password)


class PublicTagsApiTests(TestCase):
    """Test un-authed API requests for tags"""
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required for getting tags"""
        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTagsApiTests(TestCase):
    """Test un-authed API requests for tags"""
    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self):
        """Test retrieving a list of tags for user"""
        Tag.objects.create(user=self.user, name="Vegan")
        Tag.objects.create(user=self.user, name="Dessert")

        res = self.client.get(TAGS_URL)

        tags = Tag.objects.all().order_by("-name")
        serializer = TagSerializer(tags, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_tags_limited_to_user(self):
        user2 = create_user(email="other@example.com")
        Tag.objects.create(user=user2, name="Vegan")
        tag = Tag.objects.create(user=self.user, name="Dessert")

        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], tag.name)
        self.assertEqual(res.data[0]["id"], tag.id)

    def test_update_tag(self):
        tag = Tag.objects.create(user=self.user, name="After Dinner")
        payload = {"name": "Before Dinner"}

        url = detail_url(tag.id)
        res = self.client.patch(url, payload)
        tag.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(tag.name, payload["name"])

    def test_delete_tag(self):
        tag = Tag.objects.create(user=self.user, name="Breakfast")

        url = detail_url(tag.id)
        res = self.client.delete(url)
        tags = Tag.objects.filter(user=self.user)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(tags.exists())

    def test_filter_tags_assigned_to_recipes(self):
        """Test filtering for tags by those assigned to recipes."""
        tag1 = Tag.objects.create(user=self.user, name="Milky")
        tag2 = Tag.objects.create(user=self.user, name="Chocolaty")
        recipe = Recipe.objects.create(
            user=self.user,
            title="Pudding",
            time_minutes=5,
            price=Decimal("2.4"),
        )
        recipe.tags.add(tag1)
        res = self.client.get(TAGS_URL, {"assigned_only": 1})
        s1 = TagSerializer(tag1)
        s2 = TagSerializer(tag2)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filtered_tags_unique(self):
        """Test filtered tags doesn't return duplicates."""
        tag = Tag.objects.create(user=self.user, name="Eggy")
        Tag.objects.create(user=self.user, name="Lentily")
        recipe1 = Recipe.objects.create(
            user=self.user,
            title="Eggs Benedict",
            time_minutes=60,
            price=Decimal("7.0"),
        )
        recipe2 = Recipe.objects.create(
            user=self.user,
            title="Herb Eggs",
            time_minutes=20,
            price=Decimal("4.0"),
        )
        recipe1.tags.add(tag)
        recipe2.tags.add(tag)

        res = self.client.get(TAGS_URL, {"assigned_only": 1})

        self.assertEqual(len(res.data), 1)
