import sys
import os

# 添加项目路径
sys.path.append('/home/engine/project')

# 设置环境变量
os.environ['FLASK_APP'] = 'project'
os.environ['FLASK_ENV'] = 'development'

def test_api_endpoints():
    """测试API端点是否正确添加"""
    print("🔍 测试API端点...")
    
    try:
        # 导入应用
        from project import create_app
        from project.api import api_bp
        
        # 创建应用实例
        app = create_app()
        
        # 获取所有路由
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(str(rule.rule))
        
        # 查找支付相关路由
        payment_routes = [r for r in routes if 'payment' in r]
        
        print(f"✅ 找到 {len(payment_routes)} 个支付相关路由:")
        for route in payment_routes:
            print(f"  - {route}")
        
        # 检查测试端点
        test_endpoints = [r for r in payment_routes if 'test' in r]
        print(f"\n🧪 测试端点 ({len(test_endpoints)} 个):")
        for endpoint in test_endpoints:
            print(f"  - {endpoint}")
        
        if test_endpoints:
            print("\n🎉 测试端点添加成功！")
            return True
        else:
            print("\n❌ 未找到测试端点")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("🚀 支付API端点测试")
    print("=" * 60)
    
    success = test_api_endpoints()
    
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 测试失败，请检查代码")

if __name__ == "__main__":
    main()