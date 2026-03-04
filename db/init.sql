-- db/init.sql
-- Schema e dados climáticos de Belém extraídos do documento OrientalDoc128
-- Fonte: Embrapa Amazônia Oriental — "Aspectos Climáticos de Belém nos Últimos Cem Anos" (2002)
-- Executado automaticamente pelo PostgreSQL no primeiro `docker compose up`


-- tabela principal: médias mensais 1967-1996

CREATE TABLE IF NOT EXISTS clima_mensal (
    id              SERIAL PRIMARY KEY,
    mes             INT         NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nome_mes        VARCHAR(20) NOT NULL,
    temp_max        NUMERIC(4,1),   -- temperatura máxima média (°C)
    temp_min        NUMERIC(4,1),   -- temperatura mínima média (°C)
    temp_max_abs    NUMERIC(4,1),   -- temperatura máxima absoluta (°C)
    temp_min_abs    NUMERIC(4,1),   -- temperatura mínima absoluta (°C)
    temp_media      NUMERIC(4,1),   -- temperatura média (°C)
    umidade_rel     INT,            -- umidade relativa média (%)
    chuva_total     NUMERIC(6,1),   -- precipitação total mensal (mm)
    chuva_max_24h   INT,            -- chuva máxima em 24h (mm)
    insolacao_h     NUMERIC(6,1),   -- insolação total mensal (horas)
    vento_dir       VARCHAR(5),     -- direção predominante do vento
    vento_vel       NUMERIC(3,1)    -- velocidade média do vento (m/s)
);

INSERT INTO clima_mensal VALUES
    (1,  'Janeiro',   31.1, 22.9, 34.3, 20.0, 26.0, 88, 378.1, 107, 140.9, 'NE', 1.3),
    (2,  'Fevereiro', 30.7, 23.0, 34.7, 20.2, 25.8, 89, 426.6, 130, 108.4, 'NE', 1.3),
    (3,  'Março',     30.7, 23.1, 36.0, 20.5, 26.0, 89, 441.2, 136, 111.5, 'NE', 1.3),
    (4,  'Abril',     31.2, 23.3, 34.0, 20.7, 26.2, 89, 381.5, 125, 134.2, 'E',  1.3),
    (5,  'Maio',      31.8, 23.3, 34.6, 21.0, 26.4, 86, 299.8, 105, 190.4, 'E',  1.4),
    (6,  'Junho',     32.0, 22.9, 33.9, 19.9, 26.4, 83, 172.0,  95, 236.7, 'E',  1.6),
    (7,  'Julho',     32.0, 22.5, 34.0, 20.0, 26.2, 82, 160.7, 101, 259.0, 'E',  1.5),
    (8,  'Agosto',    32.4, 22.6, 35.2, 20.5, 26.5, 81, 140.0,  88, 268.4, 'E',  1.5),
    (9,  'Setembro',  32.5, 22.6, 35.2, 19.4, 26.6, 81, 139.8,  54, 242.5, 'NE', 1.6),
    (10, 'Outubro',   32.6, 22.7, 35.0, 20.0, 26.8, 80, 119.3,  73, 244.2, 'NE', 1.6),
    (11, 'Novembro',  32.7, 22.9, 35.7, 20.0, 27.0, 80, 122.7,  59, 214.8, 'NE', 1.6),
    (12, 'Dezembro',  32.2, 23.0, 36.6, 20.4, 26.7, 83, 219.6, 109, 187.3, 'NE', 1.4);


-- tabela de séries históricas: comparativo entre períodos

CREATE TABLE IF NOT EXISTS series_historicas (
    id          SERIAL PRIMARY KEY,
    periodo     VARCHAR(20) NOT NULL,   -- ex: '1896-1922'
    mes         INT         NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nome_mes    VARCHAR(20) NOT NULL,
    temp_max    NUMERIC(4,1),
    temp_min    NUMERIC(4,1),
    temp_media  NUMERIC(4,1),
    umidade_rel INT,
    chuva_total NUMERIC(6,1),
    chuva_max_24h NUMERIC(6,1)
);

-- período 1896-1922 (Tabela 3 do documento)
INSERT INTO series_historicas (periodo, mes, nome_mes, temp_max, temp_min, temp_media, umidade_rel, chuva_total, chuva_max_24h) VALUES
    ('1896-1922', 1,  'Janeiro',   31.2, 22.2, 25.3, 92, 317.9,  96.0),
    ('1896-1922', 2,  'Fevereiro', 30.8, 22.2, 25.0, 92, 347.1, 206.0),
    ('1896-1922', 3,  'Março',     30.7, 22.4, 25.2, 92, 384.1, 125.0),
    ('1896-1922', 4,  'Abril',     30.9, 22.5, 25.4, 92, 338.5, 131.5),
    ('1896-1922', 5,  'Maio',      31.4, 22.6, 25.7, 90, 262.4,  92.3),
    ('1896-1922', 6,  'Junho',     31.5, 22.0, 25.6, 88, 181.8,  63.0),
    ('1896-1922', 7,  'Julho',     31.5, 21.7, 25.5, 87, 172.8,  87.0),
    ('1896-1922', 8,  'Agosto',    31.8, 21.7, 25.7, 87, 125.2,  50.5),
    ('1896-1922', 9,  'Setembro',  32.1, 21.6, 25.9, 87,  96.4,  71.3),
    ('1896-1922', 10, 'Outubro',   32.5, 21.6, 26.1, 86,  79.9,  41.0),
    ('1896-1922', 11, 'Novembro',  32.9, 21.8, 26.4, 86,  70.0,  44.2),
    ('1896-1922', 12, 'Dezembro',  32.3, 21.9, 25.6, 88, 162.0, 141.5);

-- período 1930-1960 (Tabela 4 do documento)
INSERT INTO series_historicas (periodo, mes, nome_mes, temp_max, temp_min, temp_media, umidade_rel, chuva_total, chuva_max_24h) VALUES
    ('1930-1960', 1,  'Janeiro',   31.0, 22.6, 25.6, 89, 318.1,  78.2),
    ('1930-1960', 2,  'Fevereiro', 30.4, 22.7, 25.5, 91, 407.1, 118.2),
    ('1930-1960', 3,  'Março',     30.3, 22.8, 25.4, 91, 436.3, 102.1),
    ('1930-1960', 4,  'Abril',     30.8, 23.8, 25.7, 90, 381.9, 101.1),
    ('1930-1960', 5,  'Maio',      31.4, 22.9, 26.0, 87, 264.5, 125.6),
    ('1930-1960', 6,  'Junho',     31.8, 22.5, 26.0, 84, 164.7,  63.0),
    ('1930-1960', 7,  'Julho',     31.7, 22.2, 25.9, 83, 160.9, 102.0),
    ('1930-1960', 8,  'Agosto',    32.0, 22.1, 26.0, 83, 116.2,  54.6),
    ('1930-1960', 9,  'Setembro',  31.9, 22.0, 26.0, 84, 119.7,  64.3),
    ('1930-1960', 10, 'Outubro',   32.0, 22.0, 26.2, 83, 104.6,  61.3),
    ('1930-1960', 11, 'Novembro',  32.2, 22.1, 26.5, 82,  90.0,  98.4),
    ('1930-1960', 12, 'Dezembro',  31.8, 22.4, 26.3, 85, 197.3,  84.6);


-- tabela de resumo anual por período (para queries de tendência)

CREATE TABLE IF NOT EXISTS resumo_anual (
    id              SERIAL PRIMARY KEY,
    periodo         VARCHAR(20) NOT NULL,
    temp_media_anual NUMERIC(4,1),
    chuva_total_anual NUMERIC(7,1),
    umidade_media   INT,
    fonte           TEXT
);

INSERT INTO resumo_anual (periodo, temp_media_anual, chuva_total_anual, umidade_media, fonte) VALUES
    ('1896-1922', 25.6, 2538.1, 89, 'Cunha & Bastos (1973)'),
    ('1930-1960', 25.9, 2752.0, 86, 'Brasil (1968) / INMET'),
    ('1967-1996', 26.4, 3001.3, 84, 'Embrapa Amazônia Oriental');
