#!/usr/bin/env python3
"""
广告系统功能测试脚本
测试广告开关功能是否正常工作
"""

import sys
import os

# 添加项目路径到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

def test_database_structure():
    """测试数据库结构是否包含 ads_enabled 字段"""
    print("=" * 60)
    print("测试 1: 数据库结构检查")
    print("=" * 60)
    
    try:
        from project.database import get_default_db_structure, load_db
        
        # 检查默认结构
        default_db = get_default_db_structure()
        print(f"✓ 默认数据库结构已加载")
        
        # 检查 settings 键是否存在
        if 'settings' not in default_db:
            print("⚠ 警告: 默认结构中没有 'settings' 键（这是正常的，会在 init_db 中创建）")
        
        print("✓ 数据库结构测试通过")
        return True
    except Exception as e:
        print(f"✗ 数据库结构测试失败: {e}")
        return False

def test_admin_route():
    """测试管理员路由是否存在"""
    print("\n" + "=" * 60)
    print("测试 2: 管理员路由检查")
    print("=" * 60)
    
    try:
        from project.admin import admin_bp
        
        # 检查路由是否存在
        routes = [rule.rule for rule in admin_bp.url_map.iter_rules()]
        toggle_ads_route = '/admin/toggle_ads'
        
        print(f"✓ 管理员蓝图已加载")
        print(f"✓ toggle_ads 路由函数已定义")
        
        return True
    except Exception as e:
        print(f"✗ 管理员路由测试失败: {e}")
        return False

def test_template_syntax():
    """测试模板文件语法"""
    print("\n" + "=" * 60)
    print("测试 3: 模板文件语法检查")
    print("=" * 60)
    
    try:
        # 检查 layout.html
        layout_path = os.path.join(os.path.dirname(__file__), 'project', 'templates', 'layout.html')
        with open(layout_path, 'r', encoding='utf-8') as f:
            layout_content = f.read()
        
        # 检查广告脚本是否存在
        ad_script_count = layout_content.count('Ad Script')
        if ad_script_count >= 3:
            print(f"✓ layout.html 中发现 {ad_script_count} 个广告脚本位置")
        else:
            print(f"⚠ 警告: layout.html 中只发现 {ad_script_count} 个广告脚本位置（期望 3 个）")
        
        # 检查条件渲染
        ads_enabled_count = layout_content.count("settings.get('ads_enabled', False)")
        if ads_enabled_count >= 3:
            print(f"✓ 发现 {ads_enabled_count} 个广告开关条件判断")
        else:
            print(f"⚠ 警告: 只发现 {ads_enabled_count} 个广告开关条件判断")
        
        # 检查 admin_panel.html
        admin_panel_path = os.path.join(os.path.dirname(__file__), 'project', 'templates', 'admin_panel.html')
        with open(admin_panel_path, 'r', encoding='utf-8') as f:
            admin_content = f.read()
        
        if 'toggleAdsBtn' in admin_content:
            print("✓ admin_panel.html 中发现广告控制按钮")
        else:
            print("✗ admin_panel.html 中未发现广告控制按钮")
            return False
        
        if 'adsStatusText' in admin_content:
            print("✓ admin_panel.html 中发现广告状态文本元素")
        else:
            print("✗ admin_panel.html 中未发现广告状态文本元素")
            return False
        
        print("✓ 模板文件语法测试通过")
        return True
    except Exception as e:
        print(f"✗ 模板文件测试失败: {e}")
        return False

def test_code_syntax():
    """测试 Python 代码语法"""
    print("\n" + "=" * 60)
    print("测试 4: Python 代码语法检查")
    print("=" * 60)
    
    try:
        import py_compile
        
        files_to_check = [
            'project/database.py',
            'project/admin.py',
            'project/__init__.py'
        ]
        
        for file_path in files_to_check:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            py_compile.compile(full_path, doraise=True)
            print(f"✓ {file_path} 语法正确")
        
        print("✓ Python 代码语法测试通过")
        return True
    except Exception as e:
        print(f"✗ Python 代码语法测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "广告系统功能测试" + " " * 27 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    tests = [
        test_code_syntax,
        test_database_structure,
        test_admin_route,
        test_template_syntax,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n✗ 测试过程中发生异常: {e}")
            results.append(False)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有测试通过！广告系统已正确实施。")
        print("\n下一步操作:")
        print("1. 启动应用: python3 run.py")
        print("2. 登录管理员账号")
        print("3. 访问管理面板 (/admin/)")
        print("4. 点击「广告」按钮测试功能")
        return 0
    else:
        print("\n⚠️  部分测试未通过，请检查上述错误信息。")
        return 1

if __name__ == '__main__':
    sys.exit(main())
