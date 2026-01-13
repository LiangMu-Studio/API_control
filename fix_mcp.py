# -*- coding: utf-8 -*-
import sqlite3
import shutil
import os

db_path = 'd:/Dropbox/AI_tools/API_control/mcp_data/mcp_registry.db'
new_path = 'd:/Dropbox/AI_tools/API_control/mcp_data/mcp_registry_new.db'

if os.path.exists(new_path):
    os.remove(new_path)

conn_old = sqlite3.connect(db_path)
conn_new = sqlite3.connect(new_path)

# 只复制主表结构和数据，跳过 FTS 相关
c_old = conn_old.cursor()
c_new = conn_new.cursor()

# 获取表结构
c_old.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='servers'")
create_sql = c_old.fetchone()[0]
c_new.execute(create_sql)
print('Table created')

# 复制数据
c_old.execute("SELECT * FROM servers")
rows = c_old.fetchall()
c_old.execute("PRAGMA table_info(servers)")
cols = len(c_old.fetchall())
placeholders = ','.join(['?'] * cols)
c_new.executemany(f"INSERT INTO servers VALUES ({placeholders})", rows)
print(f'Copied {len(rows)} rows')

# 更新分类
official_servers = [
    '@modelcontextprotocol/server-filesystem',
    '@modelcontextprotocol/server-fetch',
    '@modelcontextprotocol/server-memory',
    '@modelcontextprotocol/server-sequential-thinking'
]

for name in official_servers:
    c_new.execute('UPDATE servers SET category = ? WHERE name = ?', ('官方', name))
    print(f'Updated: {name}, rows: {c_new.rowcount}')

conn_new.commit()
conn_old.close()
conn_new.close()

# 替换
if os.path.exists(db_path + '.old3'):
    os.remove(db_path + '.old3')
shutil.move(db_path, db_path + '.old3')
shutil.move(new_path, db_path)
print('Done')
