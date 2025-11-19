import json
from pathlib import Path
from datetime import datetime

FRIDGE_FILE = Path("/home/d1m4p/fridge/src/fridges.json")


class ApiExec:
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()

    def load_data(self):
        if FRIDGE_FILE.exists():
            with open(FRIDGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"fridges": {}}

    def save_data(self):
        with open(FRIDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_name(self, fridge_id: str):
        return self.data["fridges"].get(fridge_id)["name"]

    def get_list(self, fridge_id: str):
        fridge = self.data["fridges"].get(fridge_id)
        if not fridge:
            return f"Холодильник {fridge_id} не найден."

        products = fridge.get("products", [])
        if not products:
            return "Продуктов пока нет."

        lines = []
        today = datetime.today().date()

        for p in products:
            line = f"{p['name']} — {p['quantity']} {p.get('unit', '')}".strip()

            expires = p.get("expires")
            if expires:
                try:
                    exp_date = datetime.strptime(expires, "%Y-%m-%d").date()
                    days_left = (exp_date - today).days
                    if days_left < 0:
                        line += f" ⛔️ срок вышел ({expires})"
                    elif days_left == 0:
                        line += f" ⚠️ последний день (до {expires})"
                    elif days_left < 7:
                        line += f" ⚠️ до конца срока {days_left} дн. (до {expires})"
                    else:
                        line += f" (годен до {expires})"
                except ValueError:
                    line += f" (дата некорректна: {expires})"

            lines.append(line)

        return "\n".join(lines)

    def add_product(self, fridge_id: str, name: str, quantity: int, unit: str = "шт", expires: str = None):
        fridge = self.data["fridges"].get(fridge_id)
        if not fridge:
            return f"Холодильник {fridge_id} не найден."

        products = fridge.setdefault("products", [])

        # Проверка: если продукт уже есть → обновляем количество
        for p in products:
            if p["name"].lower() == name.lower():
                p["quantity"] += quantity
                if expires:  # обновим срок годности, если пришёл
                    p["expires"] = expires
                self.save_data()
                return f"Добавлено {quantity} {unit} к {name}. Теперь всего: {p['quantity']}."

        # Новый продукт
        new_id = max((p["id"] for p in products), default=0) + 1
        products.append({
            "id": new_id,
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "expires": expires
        })
        self.save_data()
        return f"{name} добавлен в холодильник {fridge['name']}."

    def remove_product(self, fridge_id: str, name: str, quantity: int):
        fridge = self.data["fridges"].get(fridge_id)
        if not fridge:
            return f"Холодильник {fridge_id} не найден."

        products = fridge.get("products", [])

        for p in products:
            if p["name"].lower() == name.lower():
                if p["quantity"] <= quantity:
                    products.remove(p)
                    self.save_data()
                    return f"{name} полностью удалён из холодильника."
                else:
                    p["quantity"] -= quantity
                    self.save_data()
                    return f"Удалено {quantity} из {name}. Осталось {p['quantity']}."

        return f"{name} не найден в холодильнике."

    def check_admin(self, fridge_id: str, user: str):
        fridge = self.data["fridges"].get(fridge_id)
        if not fridge:
            return False
        return user in fridge.get("owners")
    
    def create_fridge(self, name: str, owner: str):
        fridges = self.data["fridges"]
        new_id = f"fridge_{len(fridges) + 1}"
        fridges[new_id] = {"name": name, "owners": [owner], "products": []}
        self.save_data()
        return f"🆕 Холодильник «{name}» создан (ID: {new_id})"

    def remove_fridge(self, fridge_id: str, user: str):
        fridge = self.data["fridges"].get(fridge_id)
        if not fridge:
            return f"❌ Холодильник {fridge_id} не найден."
        if user not in fridge.get("owners"):
            return "❌ Только владелец может удалить холодильник."
        del self.data["fridges"][fridge_id]
        self.save_data()
        return f"❌ Холодильник «{fridge['name']}» удалён."

