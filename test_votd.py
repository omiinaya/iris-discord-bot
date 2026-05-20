#!/usr/bin/env python3
"""Test script for YouVersion Verse of the Day implementation."""

import os
import sys
from dotenv import load_dotenv

# Add current directory to path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youversion.client import YouVersionClient


def test_votd():
    """Test the Verse of the Day functionality."""
    # Load environment variables
    load_dotenv()

    # Check if credentials are set
    username = os.getenv("YOUVERSION_USERNAME")
    password = os.getenv("YOUVERSION_PASSWORD")

    if not username or not password:
        print("❌ Error: YOUVERSION_USERNAME and YOUVERSION_PASSWORD required")
        print("Create a .env file with these variables:")
        print("YOUVERSION_USERNAME=your_username")
        print("YOUVERSION_PASSWORD=your_password")
        return

    print("🚀 Testing YouVersion Verse of the Day Implementation")
    print("=" * 50)

    try:
        # Initialize client
        client = YouVersionClient()
        print("✅ Client initialized successfully")

        # Test authentication
        token = client.authenticator.get_access_token()
        print(f"✅ Authentication successful (token: {token[:20]}...)")

        # Test VOTD without specific day
        print("\n📖 Testing Verse of the Day (current day)...")
        votd_data = client.get_formatted_verse_of_the_day()
        print("✅ Verse of the Day fetched successfully:")
        print(f"   Day: {votd_data['day']}")
        print(f"   Reference: {votd_data['human_reference']}")
        print(f"   Text: {votd_data['verse_text'][:100]}...")

        # Test VOTD with specific day
        print("\n📖 Testing Verse of the Day (day 100)...")
        votd_data_day100 = client.get_formatted_verse_of_the_day(day=100)
        print("✅ Verse for day 100 fetched successfully:")
        print(f"   Day: {votd_data_day100['day']}")
        print(f"   Reference: {votd_data_day100['human_reference']}")
        print(f"   Text: {votd_data_day100['verse_text'][:100]}...")

        print("\n🎉 All tests passed! The implementation is working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_votd()
