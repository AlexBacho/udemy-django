"""Tests for the ingredients API"""
from decimal import Decimal

from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.utils import create_user as _create_user
from core.models import Ingredient, Recipe
from recipe.serializers import IngredientSerializer

INGREDIENT_URL = reverse("recipe:ingredient-list")


def detail_url(ingredient_id):
    return reverse("recipe:ingredient-detail", args=[ingredient_id])


def create_user(email="user@example.com", password="testpass123"):
    return _create_user(email, password)


class PublicIngredientsApiTests(TestCase):
    """Test un-authed API requests for tags"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required for getting tags"""
        res = self.client.get(INGREDIENT_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsApiTests(TestCase):
    """Test un-authed API requests for tags"""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self):
        """Test retrieving a list of tags for user"""
        Ingredient.objects.create(user=self.user, name="Salt")
        Ingredient.objects.create(user=self.user, name="Pepper")

        res = self.client.get(INGREDIENT_URL)

        ingredients = Ingredient.objects.all().order_by("-name")
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_tags_limited_to_user(self):
        user2 = create_user(email="other@example.com")
        Ingredient.objects.create(user=user2, name="Salt")
        ingredient = Ingredient.objects.create(user=self.user, name="Pepper")

        res = self.client.get(INGREDIENT_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], ingredient.name)
        self.assertEqual(res.data[0]["id"], ingredient.id)

    def test_update_ingredient(self):
        ingredient = Ingredient.objects.create(user=self.user, name="Milk")
        payload = {"name": "Chocolate"}

        url = detail_url(ingredient.id)
        res = self.client.patch(url, payload)
        ingredient.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(ingredient.name, payload["name"])

    def test_delete_ingredient(self):
        ingredient = Ingredient.objects.create(user=self.user, name="Milk")

        url = detail_url(ingredient.id)
        res = self.client.delete(url)
        ingredients = Ingredient.objects.filter(user=self.user)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ingredients.exists())

    def test_filter_ingredients_assigned_to_recipes(self):
        """Test filtering for ingredients by those assigned to recipes."""
        ingr1 = Ingredient.objects.create(user=self.user, name="Milk")
        ingr2 = Ingredient.objects.create(user=self.user, name="Chocolate")
        recipe = Recipe.objects.create(
            user=self.user,
            title="Pudding",
            time_minutes=5,
            price=Decimal("2.4"),
        )
        recipe.ingredients.add(ingr1)
        res = self.client.get(INGREDIENT_URL, {"assigned_only": 1})
        s1 = IngredientSerializer(ingr1)
        s2 = IngredientSerializer(ingr2)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filtered_ingredients_unique(self):
        """Test filtered ingredients doesn't return duplicates."""
        ingr = Ingredient.objects.create(user=self.user, name="Eggs")
        Ingredient.objects.create(user=self.user, name="Lentils")
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
        recipe1.ingredients.add(ingr)
        recipe2.ingredients.add(ingr)

        res = self.client.get(INGREDIENT_URL, {"assigned_only": 1})

        self.assertEqual(len(res.data), 1)
