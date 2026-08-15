from pathlib import Path
import sqlite3


def create_item_database(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE items(
      id INTEGER PRIMARY KEY, schema_version INTEGER, name TEXT, item_type TEXT,
      sell_price REAL, process_material TEXT, process_amount REAL, badge TEXT,
      note TEXT, api_url TEXT, page_url TEXT, json_path TEXT
    );
    CREATE TABLE item_stats(
      id INTEGER PRIMARY KEY, item_id INTEGER, position INTEGER, stat_name TEXT,
      amount REAL, conditions_json TEXT, condition_text TEXT,
      coryn_applies_to INTEGER, needs_condition_review INTEGER
    );
    CREATE TABLE item_sources(
      id INTEGER PRIMARY KEY, item_id INTEGER, position INTEGER, source_id INTEGER,
      source_name TEXT, level INTEGER, map TEXT, dye TEXT, source_url TEXT,
      lookup_error TEXT, raw_cells_json TEXT
    );
    CREATE TABLE item_images(
      id INTEGER PRIMARY KEY, item_id INTEGER, position INTEGER, category TEXT,
      gender TEXT, variant TEXT, local_path TEXT, source_url TEXT
    );
    ''')
    items = [
        (1, 1, 'Test Bow', 'Bow', 100, None, None, None, None, None, 'https://example.com/bow', ''),
        (2, 1, 'Crit Ring', 'Special', 100, None, None, None, None, None, 'https://example.com/ring', ''),
        (3, 1, 'Tank Armor', 'Armor', 100, None, None, None, None, None, 'https://example.com/armor', ''),
        (4, 1, 'Old Crystal', 'Normal Crysta', 100, None, None, None, None, None, 'https://example.com/old', ''),
        (5, 1, 'New Crystal', 'Normal Crysta', 100, None, None, None, None, None, 'https://example.com/new', ''),
        (6, 1, 'Low Aggro Ring', 'Special', 100, None, None, None, None, None, 'https://example.com/aggro', ''),
        (7, 1, 'Aggro Weapon Crystal', 'Weapon Crysta', 100, None, None, None, None, None, 'https://example.com/weapon-crysta', ''),
        (8, 1, 'Unrelated Dagger', 'Dagger', 100, None, None, None, None, None, 'https://example.com/dagger', ''),
    ]
    db.executemany('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', items)
    stats = [
        (1,1,0,'Critical Rate',25,'[]',None,None,0),
        (2,1,1,'MaxHP',500,'[]',None,None,0),
        (3,2,0,'Critical Rate',40,'[]',None,None,0),
        (7,2,1,'Aggro %',20,'[]',None,None,0),
        (4,3,0,'MaxHP',6000,'[]',None,None,0),
        (5,5,0,'Upgrade for',4,'[]',None,None,0),
        (6,6,0,'Aggro %',-10,'[]',None,None,0),
        (8,7,0,'Aggro %',15,'[]',None,None,0),
        (9,8,0,'Critical Rate',1,'[]',None,None,0),
        (10,7,1,'Aggro %',5,'[]','while condition is active',None,0),
    ]
    db.executemany('INSERT INTO item_stats VALUES (?,?,?,?,?,?,?,?,?)', stats)
    db.execute("INSERT INTO item_sources VALUES (1,1,0,10,'Test Monster',100,'Test Map',NULL,'https://example.com/monster',NULL,'[]')")
    db.execute("INSERT INTO item_images VALUES (1,1,0,'main',NULL,NULL,NULL,'https://example.com/test-bow.png')")
    db.commit(); db.close()


def add_registlet_contamination(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executemany(
        'INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        [
            (90, 1, 'Pierce Regislet Item', ' Regislet ', 0, None, None, None, None, None, 'https://example.com/regislet', ''),
            (91, 1, 'Critical Registlet Item', 'REGISTLET', 0, None, None, None, None, None, 'https://example.com/registlet-2', ''),
        ],
    )
    db.executemany(
        'INSERT INTO item_stats VALUES (?,?,?,?,?,?,?,?,?)',
        [
            (90, 90, 0, 'Physical Pierce %', 99, '[]', None, None, 0),
            (91, 91, 0, 'Critical Rate', 999, '[]', None, None, 0),
            (92, 5, 1, 'Upgrade for', 90, '[]', None, None, 0),
        ],
    )
    db.commit()
    db.close()
