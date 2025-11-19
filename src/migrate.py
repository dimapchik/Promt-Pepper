import json
import psycopg2
from pathlib import Path

# Подключение
conn = psycopg2.connect(
    dbname="fridge_bd",
    user="d1m4p",
    password="turkeyseal72",
    host="localhost"
)
cur = conn.cursor()

# Загружаем JSON
data = json.load(open(Path("fridges.json"), encoding="utf-8"))

# --- Миграция пользователей и холодильников ---
user_cache = {}  # username -> user_id

for fridge_key, fridge_data in data["fridges"].items():
    # Вставляем холодильник
    cur.execute("INSERT INTO fridge_bd.fridges (name) VALUES (%s) RETURNING fridge_id;",
                (fridge_data["name"],))
    fridge_id = cur.fetchone()[0]

    # Вставляем владельцев
    for owner in fridge_data.get("owners", []):
        if owner not in user_cache:
            cur.execute("INSERT INTO fridge_bd.users (username) VALUES (%s) RETURNING user_id;",
                        (owner,))
            user_cache[owner] = cur.fetchone()[0]
        user_id = user_cache[owner]
        cur.execute("INSERT INTO fridge_bd.fridge_owners (fridge_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                    (fridge_id, user_id))

    # Вставляем продукты
    for product in fridge_data.get("products", []):
        cur.execute(
            """
            INSERT INTO fridge_bd.products (fridge_id, name, quantity, unit, expires)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                fridge_id,
                product["name"],
                product["quantity"],
                product.get("unit"),
                product.get("expires") if product.get("expires") else None
            )
        )

conn.commit()
cur.close()
conn.close()

print("✅ Данные успешно перенесены в БД")
