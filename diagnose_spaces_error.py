#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速诊断脚本 - 检查spaces访问错误
"""

import sys
import traceback

# 测试导入
try:
    print("1. Testing imports...")
    from project import create_app
    from project.database import load_db, init_db
    print("   ✓ Imports OK")
except Exception as e:
    print(f"   ✗ Import error: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试应用创建
try:
    print("\n2. Creating app...")
    app = create_app()
    print("   ✓ App created")
except Exception as e:
    print(f"   ✗ App creation error: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试数据库初始化
try:
    print("\n3. Testing database init...")
    with app.app_context():
        init_db()
    print("   ✓ Database initialized")
except Exception as e:
    print(f"   ✗ Database init error: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试数据库加载
try:
    print("\n4. Loading database...")
    with app.app_context():
        db = load_db()
        print(f"   ✓ Database loaded")
        print(f"   - Spaces: {len(db.get('spaces', {}))}")
        print(f"   - Users: {len(db.get('users', {}))}")
        
        # 检查第一个space
        spaces = db.get('spaces', {})
        if spaces:
            first_space_id = list(spaces.keys())[0]
            first_space = spaces[first_space_id]
            print(f"\n5. Checking first space...")
            print(f"   - ID: {first_space_id}")
            print(f"   - Name: {first_space.get('name', 'N/A')}")
            print(f"   - Card type: {first_space.get('card_type', 'N/A')}")
            print(f"   - Has remote_inference_timeout_seconds: {'remote_inference_timeout_seconds' in first_space}")
            if 'cerebrium_timeout_seconds' in first_space:
                print(f"   - WARNING: Still has cerebrium_timeout_seconds!")
        else:
            print("\n5. No spaces in database")
            
except Exception as e:
    print(f"   ✗ Database load error: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试视图渲染
try:
    print("\n6. Testing space view...")
    with app.test_client() as client:
        # 测试首页
        response = client.get('/')
        print(f"   - Homepage status: {response.status_code}")
        
        # 测试第一个space
        if spaces:
            space_url = f'/ai_project/{first_space_id}'
            response = client.get(space_url)
            print(f"   - Space view status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   ✗ ERROR: {response.status_code}")
                print(f"   Response: {response.data[:500]}")
        else:
            print("   - No spaces to test")
            
except Exception as e:
    print(f"   ✗ View test error: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All checks passed!")
