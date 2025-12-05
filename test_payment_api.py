#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys

# 配置你的API密钥和服务器地址
API_KEY = "your_api_key_here"  # 请替换为你的API密钥
BASE_URL = "http://localhost:5000"  # 请根据你的服务器地址修改

def test_create_test_order():
    """创建测试订单"""
    print("\n📝 创建测试订单...")
    
    url = f"{BASE_URL}/api/payment/test/create-order"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "amount": "5.00",
        "currency": "USD"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 201:
            result = response.json()
            if result.get('success'):
                print("✅ 测试订单创建成功！")
                return result
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def test_get_orders():
    """查询所有订单"""
    print("\n📋 查询订单列表...")
    
    url = f"{BASE_URL}/api/payment/test/orders"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print(f"✅ 用户: {result['username']}")
                print(f"📊 订单总数: {result['total_count']}")
                
                if result['orders']:
                    print("\n📝 订单详情:")
                    for i, order in enumerate(result['orders'], 1):
                        print(f"{i}. 订单号: {order['order_id']}")
                        print(f"   金额: {order['currency']}{order['amount']}")
                        print(f"   状态: {order['status']}")
                        print(f"   创建时间: {order['created_at'][:19].replace('T', ' ')}")
                        print(f"   测试订单: {'是' if order.get('is_test') else '否'}")
                        print()
                else:
                    print("📭 暂无订单")
                
                return result
            else:
                print(f"❌ 响应错误: {result}")
                return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def test_simulate_payment(order_id):
    """模拟支付成功"""
    print(f"\n💳 模拟支付订单: {order_id}")
    
    url = f"{BASE_URL}/api/payment/test/simulate-payment/{order_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        response = requests.post(url, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ 支付模拟成功！会员已升级")
                if result.get('membership_expiry'):
                    print(f"🗓️ 会员到期时间: {result['membership_expiry'][:10]}")
                return result
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def test_cleanup():
    """清理测试订单"""
    print("\n🧹 清理测试订单...")
    
    url = f"{BASE_URL}/api/payment/test/cleanup"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        response = requests.delete(url, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"✅ 已删除 {result['deleted_count']} 个测试订单")
                return result
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def main():
    """主测试流程"""
    print("=" * 60)
    print("🚀 支付API测试脚本")
    print("=" * 60)
    
    if API_KEY == "your_api_key_here":
        print("❌ 请先修改脚本中的API_KEY变量")
        sys.exit(1)
    
    # 1. 创建测试订单
    order_result = test_create_test_order()
    if not order_result or not order_result.get('success'):
        print("❌ 创建测试订单失败")
        return
    
    order_id = order_result['order']['order_id']
    
    # 2. 查询订单列表
    test_get_orders()
    
    # 3. 模拟支付
    payment_result = test_simulate_payment(order_id)
    if payment_result and payment_result.get('success'):
        print("\n🔄 支付后的订单状态:")
        test_get_orders()
    
    # 4. 询问是否清理测试订单
    cleanup = input("\n🤔 是否清理测试订单？(y/N): ").lower().strip()
    if cleanup in ['y', 'yes']:
        test_cleanup()

if __name__ == "__main__":
    main()