#!/bin/bash

# 充值会员系统 - 完整测试套件
# 使用: bash run_all_tests.sh

set -e  # 任何命令失败就停止

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         充值会员系统 - 完整测试套件                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 测试计数
PASSED=0
FAILED=0

# 测试函数
run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -n "测试: $test_name ... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 通过${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ 失败${NC}"
        ((FAILED++))
    fi
}

# ================== 第一部分：Python 编译检查 ==================
echo -e "${BLUE}[第一部分] Python 文件编译检查${NC}"
echo "═══════════════════════════════════════════════════════════════"

run_test "project/membership.py" "python3 -m py_compile project/membership.py"
run_test "project/database.py" "python3 -m py_compile project/database.py"
run_test "project/auth.py" "python3 -m py_compile project/auth.py"
run_test "project/api.py" "python3 -m py_compile project/api.py"
run_test "project/admin.py" "python3 -m py_compile project/admin.py"
run_test "project/main.py" "python3 -m py_compile project/main.py"

echo

# ================== 第二部分：文件存在检查 ==================
echo -e "${BLUE}[第二部分] 文件存在检查${NC}"
echo "═══════════════════════════════════════════════════════════════"

run_test "membership.py 存在" "test -f project/membership.py"
run_test "admin_membership_settings.html 存在" "test -f project/templates/admin_membership_settings.html"
run_test "Pro 文件已删除 (pro_apply.html)" "test ! -f project/templates/pro_apply.html"
run_test "Pro 文件已删除 (admin_pro_settings.html)" "test ! -f project/templates/admin_pro_settings.html"

echo

# ================== 第三部分：代码引用检查 ==================
echo -e "${BLUE}[第三部分] 代码引用检查${NC}"
echo "═══════════════════════════════════════════════════════════════"

# 检查是否还有 Pro 会员相关的引用（应该为0）
PRO_REFS=$(grep -r "pro_apply\|is_pro\|pro_submission\|manage_pro" project/ --include="*.py" --include="*.html" 2>/dev/null | grep -v ".pyc" | wc -l)

if [ "$PRO_REFS" -eq 0 ]; then
    echo -e "检查: Pro 会员引用 ... ${GREEN}✓ 通过 (0 个引用)${NC}"
    ((PASSED++))
else
    echo -e "检查: Pro 会员引用 ... ${RED}✗ 失败 ($PRO_REFS 个引用)${NC}"
    ((FAILED++))
fi

# 检查是否存在会员相关的函数
MEMBERSHIP_FUNCS=$(grep -c "def.*membership\|def.*set_user_membership\|def.*get_user_membership" project/membership.py 2>/dev/null || echo "0")

if [ "$MEMBERSHIP_FUNCS" -gt 0 ]; then
    echo -e "检查: 会员函数数量 ... ${GREEN}✓ 通过 ($MEMBERSHIP_FUNCS 个函数)${NC}"
    ((PASSED++))
else
    echo -e "检查: 会员函数数量 ... ${RED}✗ 失败${NC}"
    ((FAILED++))
fi

# 检查 API 端点
API_ENDPOINTS=$(grep -c "@api_bp.route('/membership" project/api.py 2>/dev/null || echo "0")

if [ "$API_ENDPOINTS" -eq 3 ]; then
    echo -e "检查: API 端点数量 ... ${GREEN}✓ 通过 (3 个端点)${NC}"
    ((PASSED++))
else
    echo -e "检查: API 端点数量 ... ${RED}✗ 失败 (期望 3 个，得到 $API_ENDPOINTS 个)${NC}"
    ((FAILED++))
fi

echo

# ================== 第四部分：单元测试 ==================
echo -e "${BLUE}[第四部分] 单元测试${NC}"
echo "═══════════════════════════════════════════════════════════════"

if command -v python3 &> /dev/null; then
    if python3 test_membership_system.py > /tmp/membership_test.log 2>&1; then
        echo -e "测试: test_membership_system.py ... ${GREEN}✓ 通过${NC}"
        ((PASSED++))
    else
        echo -e "测试: test_membership_system.py ... ${RED}✗ 失败${NC}"
        cat /tmp/membership_test.log | tail -20
        ((FAILED++))
    fi
else
    echo -e "测试: test_membership_system.py ... ${YELLOW}⊘ 跳过 (Python 3 未找到)${NC}"
fi

echo

# ================== 第五部分：文档检查 ==================
echo -e "${BLUE}[第五部分] 文档检查${NC}"
echo "═══════════════════════════════════════════════════════════════"

run_test "MEMBERSHIP_API_IMPLEMENTATION.md" "test -f MEMBERSHIP_API_IMPLEMENTATION.md"
run_test "MEMBERSHIP_QUICK_START.md" "test -f MEMBERSHIP_QUICK_START.md"
run_test "MEMBERSHIP_CHANGES_SUMMARY.md" "test -f MEMBERSHIP_CHANGES_SUMMARY.md"
run_test "REMOVED_PRO_MEMBERSHIP.md" "test -f REMOVED_PRO_MEMBERSHIP.md"
run_test "TESTING_GUIDE.md" "test -f TESTING_GUIDE.md"

echo

# ================== 测试总结 ==================
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                      测试完成总结                               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

TOTAL=$((PASSED + FAILED))

echo "总测试数: $TOTAL"
echo -e "通过: ${GREEN}$PASSED${NC}"
echo -e "失败: ${RED}$FAILED${NC}"

echo

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ 所有测试通过！系统准备就绪${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo
    echo "下一步:"
    echo "  1. 配置 Payhip API 凭证"
    echo "  2. 在 Admin 面板启用会员系统"
    echo "  3. 测试支付流程"
    echo "  4. 部署到生产环境"
    echo
    exit 0
else
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ 部分测试失败，请检查上方错误信息${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo
    exit 1
fi
