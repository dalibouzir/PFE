#!/usr/bin/env python3
"""
Groq LLM Provider Connectivity Test
Verifies that Groq is available and working as fallback LLM provider.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.ml.llm.provider import get_llm_client, _create_openrouter_client, _create_groq_client
from app.utils.exceptions import ValidationError


def test_groq_connectivity():
    """Test Groq connectivity with a simple query."""
    print("\n" + "=" * 70)
    print("GROQ LLM PROVIDER CONNECTIVITY TEST")
    print("=" * 70)
    
    # Check config
    print("\n1. Configuration Status:")
    print(f"   LLM_PROVIDER: {settings.llm_provider}")
    print(f"   LLM_MODEL: {settings.llm_model}")
    print(f"   GROQ_MODEL: {settings.groq_model}")
    print(f"   OpenRouter API Key: {'✅ Present' if settings.openrouter_api_key else '❌ Missing'}")
    print(f"   Groq API Key: {'✅ Present' if settings.groq_api_key else '❌ Missing'}")
    
    # Test OpenRouter connectivity
    print("\n2. Testing OpenRouter Connectivity:")
    try:
        client = _create_openrouter_client()
        if not client:
            print("   ❌ OpenRouter credentials missing")
        else:
            print("   ✅ OpenRouter client created")
            # Try a simple request
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' in one word."}
            ]
            try:
                response = client.chat(messages)
                print(f"   ✅ OpenRouter responded: {response.content[:50]}...")
            except ValidationError as e:
                print(f"   ⚠️  OpenRouter failed: {str(e)}")
    except Exception as e:
        print(f"   ❌ Error testing OpenRouter: {e}")
    
    # Test Groq connectivity
    print("\n3. Testing Groq Connectivity:")
    try:
        client = _create_groq_client()
        if not client:
            print("   ❌ Groq credentials missing")
        else:
            print("   ✅ Groq client created")
            # Try a simple request
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' in one word."}
            ]
            try:
                response = client.chat(messages)
                print(f"   ✅ Groq responded: {response.content[:50]}...")
                print("   ✅ GROQ CONNECTIVITY: WORKING")
            except ValidationError as e:
                print(f"   ❌ Groq failed: {str(e)}")
    except Exception as e:
        print(f"   ❌ Error testing Groq: {e}")
    
    # Test get_llm_client fallback
    print("\n4. Testing LLM Client Fallback Logic:")
    try:
        client = get_llm_client()
        print(f"   ✅ Got LLM client: {client.provider_name if hasattr(client, 'provider_name') else client.base_url}")
        
        # Test with actual agricultural context
        messages = [
            {"role": "system", "content": "You are an agricultural cooperative assistant. Respond in French, concisely."},
            {"role": "user", "content": "What are the key post-harvest practices for mango? (Answer in 1-2 sentences)"}
        ]
        response = client.chat(messages)
        print(f"   ✅ LLM Response:\n      {response.content}")
    except Exception as e:
        print(f"   ❌ Error with fallback logic: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_groq_connectivity()
