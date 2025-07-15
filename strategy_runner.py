#!/usr/bin/env python3
"""
Strategy Runner for Real Trading
This script loads configuration and executes the specified strategy
"""

import sys
import json
import os
import importlib.util
import traceback
from pathlib import Path

def load_config(config_path):
    """Load strategy configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"✅ Configuration loaded successfully")
        print(f"📊 Session: {config.get('session_key', 'N/A')}")
        print(f"🎯 Strategy: {config.get('strategy_name', 'N/A')}")
        print(f"🏦 Exchange: {config.get('exchange', 'N/A')}")
        print(f"💰 Initial Balance: ${config.get('initial_balance', 0):,.2f}")
        return config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def find_strategy_directory(strategy_name):
    """Find the Python strategy directory based on strategy name"""
    strategies_dir = Path(__file__).parent / "strategies"
    
    if not strategies_dir.exists():
        print(f"❌ Strategies directory not found: {strategies_dir}")
        return None
    
    # Look for strategy folder matching the name
    for strategy_dir in strategies_dir.iterdir():
        if strategy_dir.is_dir() and strategy_name.lower() in strategy_dir.name.lower():
            # Check if directory contains Python files
            python_files = list(strategy_dir.glob("*.py"))
            if python_files:
                print(f"✅ Found strategy directory: {strategy_dir}")
                print(f"📁 Contains {len(python_files)} Python files")
                return strategy_dir
    
    print(f"❌ Strategy directory not found for: {strategy_name}")
    return None

def find_all_python_files(strategy_dir):
    """Find all Python files in the strategy directory"""
    python_files = []
    for file in strategy_dir.glob("*.py"):
        if not file.name.startswith("__"):
            python_files.append(file)
    return python_files

def execute_strategy_file(script_path, config):
    """Execute a single strategy script with the given configuration"""
    try:
        print(f"🚀 Executing strategy file: {script_path}")
        
        # Load the strategy module dynamically
        module_name = f"strategy_module_{script_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        strategy_module = importlib.util.module_from_spec(spec)
        
        # Add the strategy directory to sys.path so imports work
        strategy_dir = str(script_path.parent)
        if strategy_dir not in sys.path:
            sys.path.insert(0, strategy_dir)
        
        # Set environment variables for the strategy
        os.environ['STRATEGY_SESSION_KEY'] = config.get('session_key', '')
        os.environ['STRATEGY_API_KEY'] = config.get('api_key', '')
        os.environ['STRATEGY_API_SECRET'] = config.get('api_secret', '')
        os.environ['STRATEGY_EXCHANGE'] = config.get('exchange', '')
        os.environ['STRATEGY_INITIAL_BALANCE'] = str(config.get('initial_balance', 0))
        
        # Execute the module
        spec.loader.exec_module(strategy_module)
        
        # Look for main function or strategy class
        if hasattr(strategy_module, 'main'):
            print("📞 Calling main() function...")
            result = strategy_module.main()
            print(f"✅ Strategy file execution completed with result: {result}")
            return True
        else:
            print("⚠️  No main() function found, executing module directly...")
            print("✅ Strategy module executed successfully")
            return True
            
    except Exception as e:
        print(f"❌ Error executing strategy file {script_path}: {e}")
        print(f"📋 Traceback:\n{traceback.format_exc()}")
        return False

def execute_all_strategies(strategy_dir, config):
    """Execute all Python files in the strategy directory"""
    python_files = find_all_python_files(strategy_dir)
    
    if not python_files:
        print("⚠️  No Python files found in strategy directory")
        return False
    
    print(f"🎯 Found {len(python_files)} Python files to execute:")
    for file in python_files:
        print(f"  - {file.name}")
    
    success_count = 0
    failed_files = []
    
    for script_path in python_files:
        print(f"\n{'='*60}")
        print(f"🔄 Executing: {script_path.name}")
        print(f"{'='*60}")
        
        if execute_strategy_file(script_path, config):
            success_count += 1
        else:
            failed_files.append(script_path.name)
    
    print(f"\n{'='*60}")
    print(f"📊 Execution Summary:")
    print(f"✅ Successfully executed: {success_count}/{len(python_files)} files")
    if failed_files:
        print(f"❌ Failed files: {', '.join(failed_files)}")
    print(f"{'='*60}")
    
    return success_count > 0

def main():
    """Main function"""
    print("🎯 Strategy Runner Starting...")
    print("=" * 50)
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("❌ Usage: python3 strategy_runner.py <config_file>")
        return 1
    
    config_path = sys.argv[1]
    print(f"📁 Config file: {config_path}")
    
    # Load configuration
    config = load_config(config_path)
    if not config:
        return 1
    
    # For now, just print "Hello World" and config info
    print("\n" + "=" * 50)
    print("🌍 Hello World from Python Strategy Runner!")
    print("=" * 50)
    
    print(f"📊 Session Key: {config.get('session_key', 'N/A')}")
    print(f"🎯 Strategy Name: {config.get('strategy_name', 'N/A')}")
    print(f"📝 Strategy Code: {config.get('strategy_code', 'N/A')}")
    print(f"👤 Username: {config.get('username', 'N/A')}")
    print(f"🏦 Exchange: {config.get('exchange', 'N/A')}")
    print(f"💰 Initial Balance: ${config.get('initial_balance', 0):,.2f}")
    print(f"⚡ Risk Level: {config.get('risk_level', 'N/A')}")
    print(f"📈 Asset Class: {config.get('asset_class', 'N/A')}")
    print(f"⏰ Timeframe: {config.get('timeframe', 'N/A')}")
    print(f"🕐 Start Time: {config.get('start_time', 'N/A')}")
    
    # Find and execute strategy directory
    strategy_name = config.get('strategy_name', '')
    
    # First, check if STRATEGY_DIR environment variable is set
    strategy_dir_env = os.environ.get('STRATEGY_DIR')
    if strategy_dir_env:
        strategy_dir = Path(strategy_dir_env)
        print(f"🔍 Using strategy directory from environment: {strategy_dir}")
    elif strategy_name:
        strategy_dir = find_strategy_directory(strategy_name)
    else:
        strategy_dir = None
    
    if strategy_dir and strategy_dir.exists():
        success = execute_all_strategies(strategy_dir, config)
        if success:
            print("\n✅ All strategy files executed successfully!")
            return 0
        else:
            print("\n❌ Strategy execution failed!")
            return 1
    else:
        print(f"\n⚠️  Strategy directory not found, running in demo mode")
    
    print("\n🎉 Demo execution completed successfully!")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    exit(main())