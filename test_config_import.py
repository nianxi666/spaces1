#!/usr/bin/env python3
"""
Test importing the netmind_config module.
"""

import sys
import importlib.util

try:
    # Test direct import of netmind_config
    spec = importlib.util.spec_from_file_location("netmind_config", "/home/engine/project/project/netmind_config.py")
    netmind_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(netmind_config)
    
    print("✅ Successfully imported netmind_config module")
    print("\nAvailable constants:")
    print(f"  - DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS = {netmind_config.DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS}")
    print(f"  - DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS = {netmind_config.DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS}")
    print(f"  - DEFAULT_ENABLE_THINKING = {netmind_config.DEFAULT_ENABLE_THINKING}")
    
    print("\nAvailable functions:")
    print("  - sanitize_rate_limit_window()")
    print("  - sanitize_rate_limit_max_requests()")
    print("  - get_rate_limit_config()")
    print("  - is_thinking_enabled()")
    
    # Test the is_thinking_enabled function
    print("\nTesting is_thinking_enabled():")
    
    # Test 1: Default
    result = netmind_config.is_thinking_enabled()
    assert result is True
    print(f"  ✓ Default: {result}")
    
    # Test 2: Explicit True
    result = netmind_config.is_thinking_enabled({'enable_thinking': True})
    assert result is True
    print(f"  ✓ Explicit True: {result}")
    
    # Test 3: Explicit False
    result = netmind_config.is_thinking_enabled({'enable_thinking': False})
    assert result is False
    print(f"  ✓ Explicit False: {result}")
    
    # Test 4: String 'true'
    result = netmind_config.is_thinking_enabled({'enable_thinking': 'true'})
    assert result is True
    print(f"  ✓ String 'true': {result}")
    
    # Test 5: String 'false'
    result = netmind_config.is_thinking_enabled({'enable_thinking': 'false'})
    assert result is False
    print(f"  ✓ String 'false': {result}")
    
    print("\n✅ All config imports and functions work correctly!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
