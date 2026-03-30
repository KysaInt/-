#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试Unity导出功能"""

import json
from pathlib import Path
from unity_exporter import export_unity_component, build_unity_export_path, normalize_unity_project_dir

def test_export():
    # 加载水母触须预设
    preset_path = Path('presets/水母触须.json')
    if not preset_path.exists():
        print('✗ 找不到预设文件')
        return
    
    config = json.loads(preset_path.read_text(encoding='utf-8'))
    print(f'✓ 加载预设: {preset_path.name}')
    print(f'  触手开启: {config.get("tentacle_on")}')
    
    # 测试路径生成
    project_dir = r'C:\Users\94230\Desktop\UNITY PROJECT\AYE_P01'
    normalized = normalize_unity_project_dir(project_dir)
    print(f'✓ Unity项目路径: {normalized}')
    
    # 测试导出路径
    export_path = build_unity_export_path(project_dir, 'ShuiMuChuXu')
    print(f'✓ 导出路径: {export_path}')
    
    try:
        # 尝试导出
        result = export_unity_component(
            config,
            preset_name='水母触须',
            output_path=export_path,
            class_name='ShuiMuChuXu'
        )
        print(f'✓ 导出成功: {result}')
        print(f'  文件存在: {result.exists()}')
        
        # 检查文件内容前100行
        if result.exists():
            lines = result.read_text(encoding='utf-8').split('\n')
            print(f'  文件行数: {len(lines)}')
            print('\n前20行预览:')
            for i, line in enumerate(lines[:20], 1):
                print(f'  {i:3}: {line}')
                
    except Exception as e:
        print(f'✗ 导出失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_export()
