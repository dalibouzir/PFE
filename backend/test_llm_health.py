"""
Minimal LLM provider health check - test both Groq and OpenRouter without exposing keys.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.ml.llm.provider import get_llm_client


async def test_llm_providers():
    """Test both LLM providers with a minimal call."""
    print("=" * 80)
    print("LLM PROVIDER HEALTH CHECK")
    print("=" * 80)

    results = {
        "groq": {"status": "unknown", "latency_ms": 0, "error": None},
        "openrouter": {"status": "unknown", "latency_ms": 0, "error": None},
    }

    # Test Groq
    print("\n[1] Testing GROQ (llama-3.3-70b-versatile)...")
    try:
        import time
        start = time.perf_counter()
        
        # Get Groq client
        os.environ["LLM_PROVIDER"] = "groq"
        from app.core.config import settings
        settings.llm_provider = "groq"  # Force reload
        
        # Actually, we need to reload settings. Let's do a fresh import
        from importlib import reload
        import app.ml.llm.provider as provider_module
        reload(provider_module)
        
        client = provider_module.get_llm_client()
        
        # Minimal test: just check if we can instantiate and make a call
        response = await client.chat(
            messages=[{"role": "user", "content": "Say 'OK' in one word only."}],
            max_tokens=10,
        )
        
        latency = int((time.perf_counter() - start) * 1000)
        results["groq"]["latency_ms"] = latency
        results["groq"]["status"] = "✅ OK"
        print(f"   ✅ GROQ responding normally")
        print(f"   Response: {response.content[:50]}...")
        print(f"   Latency: {latency}ms")
        
    except Exception as e:
        error_msg = str(e)[:100]
        results["groq"]["error"] = error_msg
        results["groq"]["status"] = f"❌ {type(e).__name__}"
        print(f"   ❌ GROQ error: {error_msg}")

    # Test OpenRouter
    print("\n[2] Testing OPENROUTER (openai/gpt-4o-mini)...")
    try:
        import time
        start = time.perf_counter()
        
        # Get OpenRouter client
        os.environ["LLM_PROVIDER"] = "openrouter"
        from importlib import reload
        import app.ml.llm.provider as provider_module
        reload(provider_module)
        
        client = provider_module.get_llm_client()
        
        response = await client.chat(
            messages=[{"role": "user", "content": "Say 'OK' in one word only."}],
            max_tokens=10,
        )
        
        latency = int((time.perf_counter() - start) * 1000)
        results["openrouter"]["latency_ms"] = latency
        results["openrouter"]["status"] = "✅ OK"
        print(f"   ✅ OPENROUTER responding normally")
        print(f"   Response: {response.content[:50]}...")
        print(f"   Latency: {latency}ms")
        
    except Exception as e:
        error_msg = str(e)[:100]
        results["openrouter"]["error"] = error_msg
        results["openrouter"]["status"] = f"❌ {type(e).__name__}"
        print(f"   ❌ OPENROUTER error: {error_msg}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for provider, data in results.items():
        print(f"{provider.upper():12s} | {data['status']:20s} | {data['latency_ms']:4d}ms | {data['error'] or 'OK'}")

    print("=" * 80)
    
    # Determine which provider to use for QA testing
    groq_ok = results["groq"]["status"].startswith("✅")
    openrouter_ok = results["openrouter"]["status"].startswith("✅")
    
    if openrouter_ok:
        recommended = "openrouter"
    elif groq_ok:
        recommended = "groq"
    else:
        recommended = "none"
    
    print(f"\n🎯 Recommended provider for QA: {recommended.upper()}")
    
    return recommended, results


if __name__ == "__main__":
    recommended, results = asyncio.run(test_llm_providers())
    sys.exit(0 if recommended != "none" else 1)
