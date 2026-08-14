from pathlib import Path
import hashlib
import json
import sqlite3


def create_skill_database(path: Path) -> None:
    db=sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE skill_trees(id TEXT PRIMARY KEY,name TEXT,normalized_name TEXT,tree_group TEXT,source_file TEXT,general_text TEXT,tier_requirements_json TEXT,weapon_restrictions_json TEXT,issues_json TEXT);
    CREATE TABLE skills(id TEXT PRIMARY KEY,tree_id TEXT,source_order INTEGER,name TEXT,normalized_name TEXT,tier INTEGER,required_level INTEGER,skill_type TEXT,mp_cost_text TEXT,mp_cost_value INTEGER,damage_type TEXT,element TEXT,cast_range_text TEXT,hit_range_text TEXT,cast_time_text TEXT,hit_count_text TEXT,description TEXT,game_description TEXT,raw_text TEXT,issues_json TEXT);
    CREATE TABLE skill_aliases(skill_id TEXT,position INTEGER,alias TEXT,normalized_alias TEXT,PRIMARY KEY(skill_id,position));
    CREATE TABLE skill_sections(id INTEGER PRIMARY KEY,skill_id TEXT,position INTEGER,label TEXT,normalized_label TEXT,body TEXT);
    CREATE TABLE skill_ailments(skill_id TEXT,position INTEGER,name TEXT,normalized_name TEXT,PRIMARY KEY(skill_id,position));
    CREATE TABLE skill_weapon_requirements(skill_id TEXT,position INTEGER,weapon TEXT,normalized_name TEXT,PRIMARY KEY(skill_id,position));
    CREATE TABLE skill_weapon_restrictions(skill_id TEXT,position INTEGER,weapon TEXT,normalized_name TEXT,PRIMARY KEY(skill_id,position));
    CREATE TABLE skill_tree_weapon_restrictions(tree_id TEXT,position INTEGER,weapon TEXT,normalized_weapon TEXT,PRIMARY KEY(tree_id,position));
    CREATE TABLE skill_search_documents(id TEXT PRIMARY KEY,skill_id TEXT,position INTEGER,kind TEXT,label TEXT,text TEXT,text_hash TEXT);
    CREATE VIRTUAL TABLE skill_fts USING fts5(document_id UNINDEXED,skill_id UNINDEXED,name,tree_name,text);
    ''')
    db.execute('INSERT INTO skill_trees VALUES (?,?,?,?,?,?,?,?,?)',(
        'shield_skills','Shield Skills','shield skills','Weapon Skills','shield.txt','Shield techniques.',json.dumps([[1,1],[2,20],[3,50],[4,110],[5,240]]),json.dumps(['Shield']),'[]'))
    skills=[
      ('shield_skills/guardian','shield_skills',0,'Guardian','guardian',4,110,'Support','600',600,None,None,None,None,None,None,'Creates an area that protects party members.','Protect allies with a defensive aura.','Guardian raw mechanics.','[]'),
      ('shield_skills/hard-hit','shield_skills',1,'Hard Hit','hard hit',1,1,'Active','100',100,'Physical',None,'3m',None,None,'1','A physical attack with a chance to flinch.','Strike the target strongly.','Hard Hit raw mechanics.','[]'),
      ('shield_skills/shield-bash','shield_skills',2,'Shield Bash','shield bash',2,20,'Active','200',200,'Physical',None,'3m',None,None,'1','Strikes with a shield and can inflict Stun.','Hit the target with a shield.','Shield Bash raw mechanics.','[]'),
    ]
    db.executemany('INSERT INTO skills VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',skills)
    db.execute("INSERT INTO skill_aliases VALUES ('shield_skills/hard-hit',0,'Hardhit','hardhit')")
    db.execute("INSERT INTO skill_sections VALUES (1,'shield_skills/hard-hit',0,'Skill Effect','skill effect','Stored Hard Hit mechanics.')")
    db.execute("INSERT INTO skill_ailments VALUES ('shield_skills/shield-bash',0,'Stun','stun')")
    db.execute("INSERT INTO skill_weapon_requirements VALUES ('shield_skills/shield-bash',0,'Shield','shield')")
    db.execute("INSERT INTO skill_tree_weapon_restrictions VALUES ('shield_skills',0,'Shield','shield')")
    for skill in skills:
        sid,_,_,name,_,tier,req,stype,mp_text,mp_value,damage,element,cast,hit,cast_time,hit_count,desc,game,raw,_issues=skill
        text='\n'.join(x for x in [f'Skill: {name}','Tree: Shield Skills',f'Tier: {tier}',f'Required Level: {req}',f'MP Cost: {mp_text}',desc,game,raw] if x)
        if sid.endswith('shield-bash'): text += '\nAilment: Stun\nCan inflict stun.'
        if sid.endswith('hard-hit'): text += '\nSkill Effect\nStored Hard Hit mechanics.'
        did=sid+'#summary'; h=hashlib.sha256(text.encode()).hexdigest()
        db.execute('INSERT INTO skill_search_documents VALUES (?,?,?,?,?,?,?)',(did,sid,0,'summary',None,text,h))
        db.execute('INSERT INTO skill_fts VALUES (?,?,?,?,?)',(did,sid,name,'Shield Skills',text))
    db.commit();db.close()
