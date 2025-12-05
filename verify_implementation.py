#!/usr/bin/env python3
"""
充值会员系统 - 实现验证脚本
不需要 Flask 依赖，可以独立运行
"""

import os
import sys
import re
from pathlib import Path

class Colors:
    """颜色定义"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class Verifier:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.root = Path('/home/engine/project')
        
    def print_header(self, text):
        print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}{Colors.BOLD}{text:^60}{Colors.END}")
        print(f"{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}\n")
        
    def test(self, name, condition, details=""):
        status = "✓" if condition else "✗"
        color = Colors.GREEN if condition else Colors.RED
        
        print(f"{color}{status}{Colors.END} {name}")
        if details:
            print(f"  {details}")
            
        if condition:
            self.passed += 1
        else:
            self.failed += 1
            
    def check_file_exists(self, file_path):
        """检查文件是否存在"""
        full_path = self.root / file_path
        return full_path.exists()
        
    def check_file_not_exists(self, file_path):
        """检查文件是否不存在"""
        full_path = self.root / file_path
        return not full_path.exists()
        
    def check_file_contains(self, file_path, pattern, count=None):
        """检查文件是否包含某个模式"""
        full_path = self.root / file_path
        if not full_path.exists():
            return False
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                matches = len(re.findall(pattern, content))
                
            if count is not None:
                return matches == count
            else:
                return matches > 0
        except Exception as e:
            print(f"  错误: {e}")
            return False
            
    def check_file_not_contains(self, file_path, pattern):
        """检查文件是否不包含某个模式"""
        full_path = self.root / file_path
        if not full_path.exists():
            return True
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                matches = len(re.findall(pattern, content))
            return matches == 0
        except Exception as e:
            print(f"  错误: {e}")
            return False
            
    def count_pattern_in_file(self, file_path, pattern):
        """计数文件中某个模式的出现次数"""
        full_path = self.root / file_path
        if not full_path.exists():
            return 0
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return len(re.findall(pattern, content))
        except Exception as e:
            print(f"  错误: {e}")
            return 0
            
    def check_python_syntax(self, file_path):
        """检查 Python 文件语法"""
        full_path = self.root / file_path
        if not full_path.exists():
            return False
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                compile(f.read(), str(full_path), 'exec')
            return True
        except SyntaxError as e:
            print(f"  语法错误: {e}")
            return False
        except Exception as e:
            print(f"  错误: {e}")
            return False
    
    def run_all_tests(self):
        """运行所有验证"""
        
        # ============ 第一部分：Python 编译检查 ============
        self.print_header("第一部分：Python 文件编译检查")
        
        python_files = [
            'project/membership.py',
            'project/database.py',
            'project/auth.py',
            'project/api.py',
            'project/admin.py',
            'project/main.py',
        ]
        
        for file_path in python_files:
            result = self.check_python_syntax(file_path)
            self.test(f"编译 {file_path}", result)
        
        # ============ 第二部分：文件存在检查 ============
        self.print_header("第二部分：文件存在性检查")
        
        # 新增文件
        new_files = [
            ('project/membership.py', '核心会员模块'),
            ('project/templates/admin_membership_settings.html', '管理员会员设置页面'),
            ('MEMBERSHIP_API_IMPLEMENTATION.md', 'API 文档'),
            ('MEMBERSHIP_QUICK_START.md', '快速开始指南'),
            ('TESTING_GUIDE.md', '测试指南'),
        ]
        
        for file_path, desc in new_files:
            result = self.check_file_exists(file_path)
            self.test(f"存在: {file_path}", result, desc)
        
        # 已删除的文件
        deleted_files = [
            ('project/templates/pro_apply.html', 'Pro 申请页面'),
            ('project/templates/admin_pro_settings.html', 'Pro Admin 设置页面'),
        ]
        
        for file_path, desc in deleted_files:
            result = self.check_file_not_exists(file_path)
            self.test(f"已删除: {file_path}", result, desc)
        
        # ============ 第三部分：代码引用检查 ============
        self.print_header("第三部分：代码引用完整性检查")
        
        # Pro 会员引用（应该为 0）
        pro_patterns = ['pro_apply', 'is_pro', 'pro_submission', 'manage_pro']
        pro_files = ['project/main.py', 'project/admin.py', 'project/templates/profile.html', 
                     'project/templates/admin_users.html', 'project/templates/admin_panel.html']
        
        pro_count = 0
        for py_file in pro_files:
            full_path = self.root / py_file
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for pattern in pro_patterns:
                        pro_count += len(re.findall(pattern, content))
        
        self.test("Pro 会员代码已清理", pro_count == 0, 
                  f"找到 {pro_count} 条引用（应为 0）")
        
        # ============ 第四部分：会员功能检查 ============
        self.print_header("第四部分：会员功能实现检查")
        
        # 检查会员函数
        membership_funcs = self.count_pattern_in_file(
            'project/membership.py',
            r'def\s+(is_membership_enabled|is_user_member|get_user_membership_status|set_user_membership|revoke_user_membership)'
        )
        self.test("会员核心函数", membership_funcs >= 4, 
                  f"找到 {membership_funcs} 个函数")
        
        # 检查 API 端点
        api_endpoints = self.count_pattern_in_file(
            'project/api.py',
            r"@api_bp\.route\('/membership"
        )
        self.test("会员 API 端点", api_endpoints == 3, 
                  f"找到 {api_endpoints} 个端点（应为 3）")
        
        # 检查 Admin 路由
        admin_routes = self.count_pattern_in_file(
            'project/admin.py',
            r"@admin_bp\.route\('/membership"
        )
        self.test("会员 Admin 路由", admin_routes == 3, 
                  f"找到 {admin_routes} 个路由（应为 3）")
        
        # ============ 第五部分：数据库结构检查 ============
        self.print_header("第五部分：数据库初始化检查")
        
        # 会员设置初始化
        membership_settings = self.check_file_contains(
            'project/database.py',
            r'membership_settings.*enabled.*price_usd.*duration_days'
        )
        self.test("会员设置初始化", membership_settings, 
                  "包含 enabled, price_usd, duration_days")
        
        # 用户会员字段
        user_member_fields = self.count_pattern_in_file(
            'project/database.py',
            r"(is_member|member_expiry_date|payment_history)"
        )
        self.test("用户会员字段初始化", user_member_fields >= 3, 
                  f"找到 {user_member_fields} 个字段")
        
        # ============ 第六部分：模板检查 ============
        self.print_header("第六部分：模板集成检查")
        
        # 个人资料页面
        profile_membership = self.check_file_contains(
            'project/templates/profile.html',
            r'membership_enabled'
        )
        self.test("个人资料: 会员卡片", profile_membership)
        
        # Admin 面板按钮
        admin_panel_button = self.check_file_contains(
            'project/templates/admin_panel.html',
            r'manage_membership_settings'
        )
        self.test("Admin 面板: 会员设置按钮", admin_panel_button)
        
        # 用户列表会员状态
        users_membership_status = self.check_file_contains(
            'project/templates/admin_users.html',
            r'is_member'
        )
        self.test("用户列表: 会员状态列", users_membership_status)
        
        # ============ 第七部分：导入检查 ============
        self.print_header("第七部分：导入和依赖检查")
        
        # 检查 membership 模块被正确导入
        membership_import = self.check_file_contains(
            'project/api.py',
            r'from\s+\.membership\s+import'
        )
        self.test("API: membership 模块导入", membership_import)
        
        membership_import_admin = self.check_file_contains(
            'project/admin.py',
            r'from\s+\.membership\s+import'
        )
        self.test("Admin: membership 模块导入", membership_import_admin)
        
        membership_import_main = self.check_file_contains(
            'project/main.py',
            r'from\s+\.membership\s+import'
        )
        self.test("Main: membership 模块导入", membership_import_main)
        
        # ============ 最终报告 ============
        self.print_summary()
    
    def print_summary(self):
        """打印测试总结"""
        total = self.passed + self.failed
        
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'测试完成总结':^60}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
        
        print(f"总测试数: {total}")
        print(f"{Colors.GREEN}通过: {self.passed}{Colors.END}")
        print(f"{Colors.RED}失败: {self.failed}{Colors.END}")
        
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ 所有验证通过！系统准备就绪{Colors.END}")
            print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
            print("下一步:")
            print("  1. 启动应用: python3 run.py")
            print("  2. 在 Admin 面板配置 Payhip 凭证")
            print("  3. 启用会员系统")
            print("  4. 测试购买流程")
            print()
            return 0
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ 部分验证失败，请检查上方信息{Colors.END}")
            print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
            return 1

def main():
    verifier = Verifier()
    exit_code = verifier.run_all_tests()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
