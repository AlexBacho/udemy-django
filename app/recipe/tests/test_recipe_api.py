import tempfile
import os
from decimal import Decimal

from PIL import Image

from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag, Ingredient
from core.utils import create_user as _create_user
from recipe.serializers import RecipeSerializer, RecipeDetailSerializer


RECIPES_URL = reverse("recipe:recipe-list")


def detail_url(recipe_id):
    """Create and return a recipe detail URL."""
    return reverse("recipe:recipe-detail", args=[recipe_id])


def image_upload_url(recipe_id):
    return reverse("recipe:recipe-upload-image", args=[recipe_id])


def create_recipe(user, **params):
    defaults = {
        "title": "Sample recipe title",
        "time_minutes": 22,
        "price": Decimal("5.25"),
        "description": "Sample description",
        "link": "http://example.com/recipe.pdf",
    }
    defaults.update(params)
    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


def create_user(email="user@example.com", password="testpass123", **params):
    """Create and return a new user"""
    return _create_user(email, password, **params)


class PublicRecipeAPITests(TestCase):
    """Test un-auther API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that auth is required to call API"""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Test authed API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="user@example.com", password="testpass123")
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """test GET recipes for authed user"""
        create_recipe(user=self.user, title="res1")
        create_recipe(user=self.user, title="res2")

        res = self.client.get(RECIPES_URL)
        recipes = Recipe.objects.all().order_by("-id")
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        other_user = create_user(email="other@example.com", password="password321")
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)
        recipes = Recipe.objects.all().filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        "Test get detailed view for specific recipe."
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe."""
        payload = {
            "title": "sample recipe",
            "time_minutes": 30,
            "price": Decimal("5.99"),
        }
        res = self.client.post(RECIPES_URL, payload)
        recipe = Recipe.objects.get(id=res.data["id"])

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        """Test a partial update of a recipe"""
        original_link = "https://example.com/recipe.pdf"
        recipe = create_recipe(
            user=self.user, title="sample recipe title", link=original_link
        )
        payload = {"title": "New Recipe Title"}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload)
        recipe.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.title, payload["title"])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        recipe = create_recipe(
            user=self.user,
            title="sample recipe title",
            link="https://example.com/recipe.pdf",
            description="Sample description.",
        )
        payload = {
            "title": "New Recipe Title",
            "link": "https://new-link.com/recipe-new.pdf",
            "description": "New desc.",
            "time_minutes": 10,
            "price": Decimal("2.50"),
        }
        url = detail_url(recipe.id)
        res = self.client.put(url, payload)
        recipe.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_updating_user_raises_error(self):
        """Test that trying to change the recipes user raises an error."""
        new_user = create_user(email="other@example.com", password="somepass")
        recipe = create_recipe(user=self.user)

        payload = {"user": new_user.id}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)
        recipe.refresh_from_db()

        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Test deleting a recipe"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_deleting_other_users_recipe_raises(self):
        """Test if trying to delete other users recipe fails as expected."""
        other_user = create_user(email="other@example.com", password="otherpass")
        recipe = create_recipe(user=other_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with new tags."""
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 30,
            "price": Decimal("2.50"),
            "tags": [{"name": "Thai"}, {"name": "Dinner"}]
        }
        res = self.client.post(RECIPES_URL, payload, format="json")
        recipes = Recipe.objects.filter(user=self.user)
        recipe = recipes[0]

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(recipes.count(), 1)
        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload["tags"]:
            exists = recipe.tags.filter(
                name=tag["name"],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_assign_tag_to_recipe(self):
        """Test creating recipe with existing tag"""
        tag_indian = Tag.objects.create(user=self.user, name="Indian")
        payload = {
            "title": "Pongal",
            "time_minutes": 60,
            "price": Decimal("4.5"),
            "tags": [{"name": "Indian"}, {"name": "breakfast"}]
        }
        res = self.client.post(RECIPES_URL, payload, format="json")
        recipes = Recipe.objects.filter(user=self.user)
        recipe = recipes[0]

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag_indian, recipe.tags.all())
        for tag in payload["tags"]:
            exists = recipe.tags.filter(
                name=tag["name"],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_tag_on_update(self):
        """Test create tag when updating recipe"""
        recipe = create_recipe(user=self.user)
        payload = {"tags": [{"name": "Lunch"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        new_tag = Tag.objects.get(user=self.user, name="Lunch")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assigning an existing tag when updating a recipe"""
        tag_breakfast = Tag.objects.create(user=self.user, name="Breakfast")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name="Lunch")
        payload = {"tags": [{"name": "Lunch"}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test cleating a recipes tags."""
        tag = Tag.objects.create(user=self.user, name="Dessert")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {"tags": []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """Test creating a recipe with new ingredients."""
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 30,
            "price": Decimal("2.50"),
            "ingredients": [{"name": "prawn"}, {"name": "curry"}]
        }
        res = self.client.post(RECIPES_URL, payload, format="json")
        recipes = Recipe.objects.filter(user=self.user)
        recipe = recipes[0]

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(recipes.count(), 1)
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload["ingredients"]:
            exists = recipe.ingredients.filter(
                name=ingredient["name"],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_assign_ingredient_to_recipe(self):
        """Test creating recipe with existing ingredient"""
        ingredient = Ingredient.objects.create(user=self.user, name="Milk")
        payload = {
            "title": "Hot Chocolate",
            "time_minutes": 60,
            "price": Decimal("4.5"),
            "ingredients": [{"name": "Milk"}, {"name": "Chocolate"}]
        }
        res = self.client.post(RECIPES_URL, payload, format="json")
        recipes = Recipe.objects.filter(user=self.user)
        recipe = recipes[0]

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(ingredient, recipe.ingredients.all())
        for ingredient in payload["ingredients"]:
            exists = recipe.ingredients.filter(
                name=ingredient["name"],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_ingredient_on_update(self):
        """Test create ingredient when updating recipe"""
        recipe = create_recipe(user=self.user)
        payload = {"ingredients": [{"name": "Egg"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        new_ingredient = Ingredient.objects.get(user=self.user, name="Egg")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assigning an existing ingredient when updating a recipe"""
        ingredient1 = Ingredient.objects.create(user=self.user, name="Milk")
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient1)

        ingredient2 = Ingredient.objects.create(user=self.user, name="Egg")
        payload = {"ingredients": [{"name": "Egg"}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        """Test cleating a recipes ingredients."""
        ingredient = Ingredient.objects.create(user=self.user, name="Egg")
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {"ingredients": []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)

    def test_filter_by_tags(self):
        """Test filtering recipes by tags."""
        recipe1 = create_recipe(user=self.user, title="Curry")
        recipe2 = create_recipe(user=self.user, title="Pizza")
        tag1 = Tag.objects.create(user=self.user, name="Vegan")
        tag2 = Tag.objects.create(user=self.user, name="Vegetarian")
        recipe1.tags.add(tag1)
        recipe2.tags.add(tag2)
        recipe3 = create_recipe(user=self.user, title="Burger")

        params = {"tags": f"{tag1.id},{tag2.id}"}
        res = self.client.get(RECIPES_URL, params)

        s1 = RecipeSerializer(recipe1)
        s2 = RecipeSerializer(recipe2)
        s3 = RecipeSerializer(recipe3)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)
        self.assertEqual(len(res.data), 2)

    def test_filter_by_ingredients(self):
        """Test filtering recipes by ingredients."""
        recipe1 = create_recipe(user=self.user, title="Curry")
        recipe2 = create_recipe(user=self.user, title="Pizza")
        ingr1 = Ingredient.objects.create(user=self.user, name="Meat")
        ingr2 = Ingredient.objects.create(user=self.user, name="cheese")
        recipe1.ingredients.add(ingr1)
        recipe2.ingredients.add(ingr2)
        recipe3 = create_recipe(user=self.user, title="Burger")

        params = {"ingredients": f"{ingr1.id},{ingr2.id}"}
        res = self.client.get(RECIPES_URL, params)

        s1 = RecipeSerializer(recipe1)
        s2 = RecipeSerializer(recipe2)
        s3 = RecipeSerializer(recipe3)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)
        self.assertEqual(len(res.data), 2)

class ImageUploadTests(TestCase):
    """Tests for the image uplaod API"""
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        """Test uploading an image to recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            img = Image.new("RGB", (10, 10))
            img.save(image_file, format="JPEG")
            image_file.seek(0)
            payload = {"image": image_file}
            res = self.client.post(url, payload, format="multipart")

        self.recipe.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading invalid image."""
        url = image_upload_url(self.recipe.id)
        payload = {"image": "not an image"}
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
