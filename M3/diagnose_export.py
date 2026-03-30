#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断Unity导出参数"""

import re
from pathlib import Path

def check_exported_parameters():
    # 读取PyStyleVisualizer.cs
    pysv_path = Path(r"C:\Users\94230\Desktop\UNITY PROJECT\AYE_P01\Assets\Scripts\PyStyleVisualizer.cs")
    if not pysv_path.exists():
        print("✗ 找不到PyStyleVisualizer.cs")
        return
    
    pysv_content = pysv_path.read_text(encoding='utf-8')
    
    # 提取所有public字段
    field_pattern = re.compile(r'\bpublic\s+(?:readonly\s+)?(?P<type>[A-Za-z0-9_<>,\[\]]+)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*[=;]')
    pysv_fields = {match.group('name') for match in field_pattern.finditer(pysv_content)}
    
    print(f"✓ PyStyleVisualizer 公开字段数: {len(pysv_fields)}")
    
    # 读取导出的文件
    export_path = Path(r"C:\Users\94230\Desktop\UNITY PROJECT\AYE_P01\Assets\Scripts\ShuiMuChuXu.cs")
    if not export_path.exists():
        print("✗ 找不到导出文件")
        return
    
    export_content = export_path.read_text(encoding='utf-8')
    
    # 提取所有visualizer.xxx = 的赋值
    assign_pattern = re.compile(r'visualizer\.([A-Za-z_][A-Za-z0-9_]*)\s*=')
    assignments = list(assign_pattern.finditer(export_content))
    
    print(f"✓ 导出文件参数赋值数: {len(assignments)}")
    
    # 检查每个赋值的字段是否存在
    missing = []
    found = []
    for match in assignments:
        field_name = match.group(1)
        if field_name not in pysv_fields:
            missing.append(field_name)
        else:
            found.append(field_name)
    
    print(f"\n✓ 有效参数: {len(found)}")
    if missing:
        print(f"\n✗ 缺失的参数 ({len(missing)}):")
        for name in sorted(set(missing)):
            print(f"  - {name}")
    else:
        print("✓ 所有参数都在PyStyleVisualizer中存在")
    
    # 检查文件是否有语法错误标记
    if 'visualizer.kpBind' in export_content or 'visualizer.kp_bind' in export_content:
        print("\n✗ 警告: 导出了kp绑定参数到visualizer（应该被过滤）")
    
    print(f"\n导出的前10个参数:")
    for i, match in enumerate(assignments[:10], 1):
        field_name = match.group(1)
        status = "✓" if field_name in pysv_fields else "✗"
        print(f"  {status} {field_name}")

if __name__ == '__main__':
    check_exported_parameters()
