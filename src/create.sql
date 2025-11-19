CREATE SCHEMA fridge_db;

-- Пользователи
CREATE TABLE fridge_db.users (
    user_id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL
);

-- Холодильники
CREATE TABLE fridge_db.fridges (
    fridge_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

-- Взаимосвязь "владельцы ↔ холодильники" (многие-ко-многим)
CREATE TABLE fridge_db.fridge_owners (
    fridge_id INT NOT NULL REFERENCES fridge_db.fridges(fridge_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES fridge_db.users(user_id) ON DELETE CASCADE,
    PRIMARY KEY (fridge_id, user_id)
);

-- Продукты
CREATE TABLE fridge_db.products (
    product_id SERIAL PRIMARY KEY,
    fridge_id INT NOT NULL REFERENCES fridge_db.fridges(fridge_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    quantity INT NOT NULL,
    unit TEXT,
    expires DATE  -- NULL если нет срока
);
