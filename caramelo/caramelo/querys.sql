-- Asegura que tu usuario pueda usar y crear en el esquema public
GRANT USAGE, CREATE ON SCHEMA public TO caramelo_user;

-- (Opcional pero útil) que pueda trabajar con objetos ya existentes
GRANT ALL PRIVILEGES ON DATABASE caramelo_db TO caramelo_user;

-- Para tablas/secuencias futuras creadas por otros, deja defaults (opcional)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON TABLES TO caramelo_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON SEQUENCES TO caramelo_user;
