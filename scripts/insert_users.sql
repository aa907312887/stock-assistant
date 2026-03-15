-- 添加用户：杨佳兴、王悦，密码均为 123456
-- 使用前请先执行 scripts/init.sql 建库建表，并 USE stock_assistant;

USE stock_assistant;

INSERT INTO user (username, password_hash) VALUES
('杨佳兴', '$2b$12$ifXFJPsOvloeMZis2.TLbeuVd9klaNca/ZX8PZMD0qe5.hvNqjZ8G'),
('王悦',   '$2b$12$ifXFJPsOvloeMZis2.TLbeuVd9klaNca/ZX8PZMD0qe5.hvNqjZ8G');
