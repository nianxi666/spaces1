# -*- coding: utf-8 -*-
"""
清理ai_project_view.html中所有cerebrium相关的代码
"""

# 所有需要删除cerebrium判断的行号（基于grep搜索结果）
# 第49行: {% if space_card_type == 'cerebrium' %}
# 第132行: {% if space_card_type != 'cerebrium' %}
# 第212行: {% if api_examples and space_card_type != 'cerebrium' %}
# 第305行: {% if space_card_type == 'cerebrium' and last_custom_gpu_result %}
# 第344行: {% if space_card_type == 'cerebrium' %}
# 第816行: {% if space_card_type == 'cerebrium' %}
# 第1357行: const isCustomGpuSpace = {{ 'true' if space_card_type == 'cerebrium' else 'false'

# 由于ai_project_view.html现在只支持remote_inference卡片类型
# 所有针对cerebrium的条件判断都应该删除，因为：
# 1. space_card_type == 'cerebrium' 的条件永远不会为true（已迁移到remote_inference）
# 2. space_card_type != 'cerebrium' 的条件永远为true（总是显示）

# 需要删除的主要大块代码段：
# - 第49-130行左右：cerebrium特定的GPU配置选择界面
# - 第816-1200行左右：intiCustomG  puFlow()函数（只用于cerebrium）

# 由于这个文件太复杂，建议手动审查并删除，或者直接简化为只支持remote_inference

print("ai_project_view.html中cerebrium相关的代码位置:")
print("1. 第49行开始: GPU配置选择区(<49行开始的{% if space_card_type == 'cerebrium' %} 块)")
print("2. 第132行: API示例排除cerebrium")
print("3. 第212行: API示例排除cerebrium") 
print("4. 第305行: 显示last_custom_gpu_result")
print("5. 第344行: 日志区域排除cerebrium")
print("6. 第816行开始: 整个initCustomGpuFlow() JavaScript函数块")
print("7. 第1357行: isCustomGpu  Space变量")
print()
print("建议: 由于remote_inference已经取代了cerebrium，")
print("可以考虑将所有 'cerebrium' 条件判断简化为始终显示remote_inference UI")
