#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEO 优化验证脚本
验证所有 SEO 相关的配置和文件
"""

import os
import sys
import json
import re
from pathlib import Path

class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """打印标题"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}{Colors.END}\n")

def print_success(text):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    """打印错误消息"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    """打印警告消息"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    """打印信息消息"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def check_file_exists(file_path, description):
    """检查文件是否存在"""
    if os.path.exists(file_path):
        print_success(f"{description}: {file_path}")
        return True
    else:
        print_error(f"{description} 不存在: {file_path}")
        return False

def check_robots_txt():
    """检查 robots.txt"""
    print_header("检查 Robots.txt")
    
    robots_path = "project/static/robots.txt"
    if not check_file_exists(robots_path, "Robots.txt"):
        return False
    
    with open(robots_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键规则
    checks = [
        ("Googlebot 规则", "User-agent: Googlebot"),
        ("Sitemap 声明", "Sitemap:"),
        ("Admin 保护", "Disallow: /admin/"),
        ("API 保护", "Disallow: /api/"),
        ("静态资源允许", "Allow: /static/"),
    ]
    
    for name, pattern in checks:
        if pattern in content:
            print_success(f"{name}存在")
        else:
            print_warning(f"{name}缺失")
    
    return True

def check_layout_meta_tags():
    """检查 layout.html 的 meta 标签"""
    print_header("检查 Layout.html Meta 标签")
    
    layout_path = "project/templates/layout.html"
    if not check_file_exists(layout_path, "Layout.html"):
        return False
    
    with open(layout_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键 meta 标签
    meta_tags = [
        ("基础 description", '<meta name="description"'),
        ("Keywords", '<meta name="keywords"'),
        ("Author", '<meta name="author"'),
        ("Robots", '<meta name="robots"'),
        ("Googlebot", '<meta name="googlebot"'),
        ("Open Graph Type", '<meta property="og:type"'),
        ("Open Graph Title", '<meta property="og:title"'),
        ("Open Graph Description", '<meta property="og:description"'),
        ("Open Graph Image", '<meta property="og:image"'),
        ("Twitter Card", '<meta name="twitter:card"'),
        ("Twitter Title", '<meta name="twitter:title"'),
        ("Twitter Image", '<meta name="twitter:image"'),
        ("Canonical URL", '<link rel="canonical"'),
        ("Theme Color", '<meta name="theme-color"'),
    ]
    
    missing_count = 0
    for name, pattern in meta_tags:
        if pattern in content:
            print_success(f"{name}")
        else:
            print_error(f"{name} 缺失")
            missing_count += 1
    
    if missing_count == 0:
        print_success(f"\n所有 {len(meta_tags)} 个重要 Meta 标签都已存在！")
    else:
        print_warning(f"\n缺失 {missing_count}/{len(meta_tags)} 个 Meta 标签")
    
    return missing_count == 0

def check_structured_data():
    """检查结构化数据"""
    print_header("检查 JSON-LD 结构化数据")
    
    layout_path = "project/templates/layout.html"
    with open(layout_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查 JSON-LD 脚本
    schemas = [
        ("WebSite Schema", '"@type": "WebSite"'),
        ("Organization Schema", '"@type": "Organization"'),
        ("SearchAction", '"@type": "SearchAction"'),
    ]
    
    for name, pattern in schemas:
        if pattern in content:
            print_success(f"{name} 存在")
        else:
            print_warning(f"{name} 缺失")
    
    # 检查结构化数据块
    if '{% block structured_data %}' in content:
        print_success("结构化数据扩展块已配置")
    else:
        print_warning("结构化数据扩展块缺失")
    
    return True

def check_performance_tags():
    """检查性能优化标签"""
    print_header("检查性能优化标签")
    
    layout_path = "project/templates/layout.html"
    with open(layout_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    perf_tags = [
        ("DNS Prefetch", 'rel="dns-prefetch"'),
        ("Preconnect", 'rel="preconnect"'),
        ("Google Fonts Preconnect", 'fonts.googleapis.com'),
    ]
    
    for name, pattern in perf_tags:
        if pattern in content:
            print_success(f"{name}")
        else:
            print_warning(f"{name} 缺失")
    
    return True

def check_sitemap():
    """检查 sitemap 配置"""
    print_header("检查 Sitemap 配置")
    
    # 检查 sitemap 模板
    sitemap_template = "project/templates/sitemap_template.xml"
    if not check_file_exists(sitemap_template, "Sitemap 模板"):
        return False
    
    with open(sitemap_template, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查高级特性
    features = [
        ("图片支持", 'xmlns:image'),
        ("多语言支持", 'xmlns:xhtml'),
        ("图片 loc", '<image:loc>'),
        ("语言备选", '<xhtml:link'),
    ]
    
    for name, pattern in features:
        if pattern in content:
            print_success(f"{name}")
        else:
            print_warning(f"{name} 缺失")
    
    # 检查 sitemap 生成逻辑
    main_py = "project/main.py"
    if check_file_exists(main_py, "Main.py"):
        with open(main_py, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'def sitemap():' in content:
            print_success("Sitemap 路由存在")
            
            # 检查高级功能
            if 'images' in content and 'alternates' in content:
                print_success("Sitemap 包含图片和多语言支持")
            else:
                print_warning("Sitemap 缺少高级功能")
        else:
            print_error("Sitemap 路由不存在")
    
    return True

def check_seo_blocks():
    """检查 SEO 扩展块"""
    print_header("检查 SEO 扩展块")
    
    layout_path = "project/templates/layout.html"
    with open(layout_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = [
        ("title", "{% block title %}"),
        ("meta_description", "{% block meta_description %}"),
        ("og_title", "{% block og_title %}"),
        ("og_description", "{% block og_description %}"),
        ("og_image", "{% block og_image %}"),
        ("twitter_title", "{% block twitter_title %}"),
        ("twitter_description", "{% block twitter_description %}"),
        ("twitter_image", "{% block twitter_image %}"),
        ("structured_data", "{% block structured_data %}"),
    ]
    
    for name, pattern in blocks:
        if pattern in content:
            print_success(f"{name} 块")
        else:
            print_warning(f"{name} 块缺失")
    
    return True

def generate_report():
    """生成完整报告"""
    print_header("SEO 优化验证报告")
    
    print_info("开始验证 SEO 优化...")
    
    results = []
    
    # 执行所有检查
    results.append(("Robots.txt", check_robots_txt()))
    results.append(("Meta 标签", check_layout_meta_tags()))
    results.append(("结构化数据", check_structured_data()))
    results.append(("性能优化", check_performance_tags()))
    results.append(("Sitemap", check_sitemap()))
    results.append(("SEO 扩展块", check_seo_blocks()))
    
    # 总结
    print_header("验证总结")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n通过: {passed}/{total}\n")
    
    for name, result in results:
        if result:
            print_success(f"{name}: 通过")
        else:
            print_error(f"{name}: 失败")
    
    # 最终评分
    score = (passed / total) * 100
    print(f"\n{Colors.BOLD}总体评分: {score:.1f}%{Colors.END}\n")
    
    if score == 100:
        print_success("🎉 所有 SEO 优化都已正确实施！")
        print_info("\n下一步:")
        print_info("1. 部署到生产环境")
        print_info("2. 提交 sitemap 到 Google Search Console")
        print_info("3. 验证结构化数据")
        print_info("4. 监控搜索表现")
    elif score >= 80:
        print_success("✅ SEO 优化基本完成，但有一些小问题需要修复")
    elif score >= 60:
        print_warning("⚠️  SEO 优化部分完成，建议修复剩余问题")
    else:
        print_error("❌ SEO 优化未完成，请查看上述错误")
    
    return score == 100

def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║           SEO 优化验证工具                                        ║")
    print("║           Google Search Console 标准                              ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    # 检查是否在项目根目录
    if not os.path.exists('project'):
        print_error("请在项目根目录运行此脚本")
        sys.exit(1)
    
    # 生成报告
    success = generate_report()
    
    print("\n" + "="*70 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
