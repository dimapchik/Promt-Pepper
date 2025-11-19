"""
One-time database setup script.
Run this to initialize the vector database with recipe embeddings.
"""

import ast
from os import getenv

import chromadb
import kagglehub
from datasets import Dataset, load_dataset
from dotenv import load_dotenv
from kagglehub import KaggleDatasetAdapter
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def parse_r_list(text):
    """Parse list string (Python style or R-style) to Python list."""
    if not text or not isinstance(text, str):
        return []

    text = text.strip()

    # Try parsing as a Python literal (handles ["a", "b"] correctly)
    try:
        val = ast.literal_eval(text)
        if isinstance(val, list):
            return val
    except (ValueError, SyntaxError):
        pass

    # Fallback for R-style c() lists
    if text.startswith('c(') and text.endswith(')'):
        text = text[2:-1]  # Remove c( and )
    elif text.startswith('[') and text.endswith(']'):
        text = text[1:-1]  # Remove [ and ]

    # Split by comma and clean quotes
    items = []
    for item in text.split('", "'):
        item = item.strip(' "')
        if item:
            items.append(item)
    return items


def setup_database(force_rebuild: bool = False):
    """
    Initialize ChromaDB with recipe embeddings.

    Args:
        force_rebuild: If True, delete existing collection and rebuild from scratch
    """

    EMBEDDING_MODEL = getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHROMA_PATH = getenv("CHROMA_PATH", "./chroma_db")
    COLLECTION_NAME = getenv("COLLECTION_NAME", "recipes")

    DATASET_NAME = getenv("DATASET_NAME", "AkashPS11/recipes_data_food.com")
    DATASET_SPLIT = getenv("DATASET_SPLIT", "train")
    MAX_RECIPES = int(getenv("MAX_RECIPES", "0"))

    print(f"Initializing database at {CHROMA_PATH}...")

    # Connect to persistent ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Check if collection exists
    try:
        collection = client.get_collection(COLLECTION_NAME)
        if not force_rebuild:
            count = collection.count()
            print(f"✓ Collection '{COLLECTION_NAME}' already exists with {count} recipes")
            print("Use force_rebuild=True to rebuild from scratch")
            return
        else:
            print(f"Deleting existing collection '{COLLECTION_NAME}'...")
            client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    # Create new collection
    print(f"Creating new collection '{COLLECTION_NAME}'...")
    collection = client.create_collection(COLLECTION_NAME)

    # Load dataset
    print(f"Loading dataset '{DATASET_NAME}'...")
    if DATASET_NAME == "paultimothymooney/recipenlg":
        idx_column = "Unnamed: 0"
        title_column = "title"
        ingredients_column = "ingredients"
        instructions_column = "directions"
        dataset = kagglehub.load_dataset(
            KaggleDatasetAdapter.HUGGING_FACE,
            "paultimothymooney/recipenlg",
            "RecipeNLG_dataset.csv",
            pandas_kwargs={"compression": "zip"}
        )
    elif DATASET_NAME == "AkashPS11/recipes_data_food.com":
        idx_column = "RecipeId"
        title_column = "Name"
        ingredients_column = "RecipeIngredientParts"
        instructions_column = "RecipeInstructions"
        dataset = load_dataset(DATASET_NAME, split=DATASET_SPLIT)

    # Determine how many recipes to process
    max_recipes = MAX_RECIPES if MAX_RECIPES > 0 else len(dataset)
    max_recipes = min(max_recipes, len(dataset))
    print(f"Processing {max_recipes} recipes...")

    # Load embedding model
    print(f"Loading embedding model '{EMBEDDING_MODEL}'...")
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    # Process in batches to avoid memory issues
    batch_size = 100
    recipe_id = 0

    for i in tqdm(range(0, max_recipes, batch_size), desc="Creating embeddings"):
        end_idx = min(i + batch_size, max_recipes)
        batch_data = dataset[i:end_idx]

        # Build full recipe text combining name, ingredients, and instructions
        texts = []
        metadatas = []

        for idx in range(len(batch_data[idx_column])):
            # Extract fields
            name = batch_data[title_column][idx]
            ingredients_raw = batch_data[ingredients_column][idx]
            instructions_raw = batch_data[instructions_column][idx]
            if not name or not ingredients_raw or not instructions_raw:
                continue  # Skip incomplete recipes

            # Parse R-style lists
            ingredients = parse_r_list(ingredients_raw.replace('\r\n', ''))
            instructions = parse_r_list(instructions_raw.replace('\r\n', ''))

            # Build combined text document
            ingredients_text = "\n- ".join(ingredients) if ingredients else "No ingredients listed"
            instructions_text = "\n".join(instructions) if instructions else "No instructions provided"

            recipe_text = f"Recipe: {name}\n\nIngredients:\n- {ingredients_text}\n\nInstructions:\n{instructions_text}"

            texts.append(recipe_text)
            metadatas.append({
                "recipe_id": str(batch_data[idx_column][idx]),
                "name": name
            })        # Generate embeddings
        embeddings = embedder.encode(texts, show_progress_bar=False)

        if not embeddings.tolist():
            continue

        # Add to collection
        collection.add(
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=[f"recipe-{recipe_id + idx}" for idx in range(len(texts))]
        )

        recipe_id += len(texts)

    final_count = collection.count()
    print(f"\n✓ Database setup complete! Added {final_count} recipes")


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    load_dotenv()
    setup_database(force_rebuild=force)
