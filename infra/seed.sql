CREATE TABLE projects (
    id integer PRIMARY KEY,
    name text NOT NULL,
    owner_name text NOT NULL,
    budget numeric(12, 2) NOT NULL
);
INSERT INTO projects VALUES
    (1, 'Автоматизация библиотеки', 'Иванова', 120000),
    (2, 'Учёт оборудования', 'Петров', 85000),
    (3, 'Резервное копирование', 'Смирнов', 65000);
