import json, os
from win11_theme import save_color_config, load_color_config, CONFIG_FILE, USER_CONFIG_FILE
cfg = load_color_config()
print('loaded from:', CONFIG_FILE if os.path.exists(CONFIG_FILE) else (USER_CONFIG_FILE if os.path.exists(USER_CONFIG_FILE) else 'default'))
cfg['light']['bg'] = '#abcdef'
ok = save_color_config(cfg)
print('save ok:', ok)
new = load_color_config()
print('new light bg:', new['light']['bg'])
