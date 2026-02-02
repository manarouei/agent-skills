#!/usr/bin/env python3
"""
Validator Bug Fix Verification Tests

This module tests the contract validator to ensure it correctly:
1. Accepts legitimate production hosts (e.g., api.github.com)
2. Rejects placeholder hosts (e.g., example.com, localhost)
3. Rejects empty strings
4. Rejects whitespace-only strings

The bug that was fixed: Empty string "" in invalid list caused ALL hosts to be rejected
because `"" in any_string` is always True in Python.
"""

import sys
from contracts.node_contract import CredentialScope, SideEffectDeclaration


def test_host_allowlist_accepts_real_hosts():
    """Real production hosts should be accepted."""
    try:
        scope = CredentialScope(
            credential_type='githubApi',
            required=True,
            host_allowlist=['api.github.com', 'api.stripe.com', 'production.mycompany.com']
        )
        print('✅ TEST 1 PASSED: Real production hosts accepted')
        return True
    except Exception as e:
        print(f'❌ TEST 1 FAILED: Real hosts rejected: {e}')
        return False


def test_host_allowlist_rejects_placeholders():
    """Placeholder hosts should be rejected."""
    test_cases = [
        ('example.com', 'example.com'),
        ('localhost', 'localhost'),
        ('TODO', 'TODO'),
        ('dummy.com', 'dummy'),
        ('placeholder.com', 'placeholder'),
    ]
    
    all_passed = True
    for host, reason in test_cases:
        try:
            scope = CredentialScope(
                credential_type='test',
                required=True,
                host_allowlist=[host]
            )
            print(f'❌ TEST 2.{host} FAILED: {host} was accepted (should reject)')
            all_passed = False
        except Exception:
            print(f'✅ TEST 2.{host} PASSED: {host} rejected as expected')
    
    return all_passed


def test_host_allowlist_rejects_empty():
    """Empty and whitespace-only strings should be rejected."""
    test_cases = [
        ('', 'empty string'),
        ('   ', 'whitespace only'),
        ('\t', 'tab only'),
    ]
    
    all_passed = True
    for host, desc in test_cases:
        try:
            scope = CredentialScope(
                credential_type='test',
                required=True,
                host_allowlist=[host]
            )
            print(f'❌ TEST 3.{desc} FAILED: {repr(host)} was accepted (should reject)')
            all_passed = False
        except Exception:
            print(f'✅ TEST 3.{desc} PASSED: {repr(host)} rejected as expected')
    
    return all_passed


def test_network_destinations_accepts_real_hosts():
    """Network destinations should accept real production hosts."""
    try:
        side_effects = SideEffectDeclaration(
            types=['network'],
            network_destinations=['api.github.com', 'api.stripe.com', '192.168.1.100']
        )
        print('✅ TEST 4 PASSED: Real network destinations accepted')
        return True
    except Exception as e:
        print(f'❌ TEST 4 FAILED: Real destinations rejected: {e}')
        return False


def test_network_destinations_rejects_placeholders():
    """Network destinations should reject placeholders."""
    test_cases = [
        ('example.com', 'example.com'),
        ('TODO', 'TODO'),
        ('dummy.com', 'dummy'),
    ]
    
    all_passed = True
    for dest, reason in test_cases:
        try:
            side_effects = SideEffectDeclaration(
                types=['network'],
                network_destinations=[dest]
            )
            print(f'❌ TEST 5.{dest} FAILED: {dest} was accepted (should reject)')
            all_passed = False
        except Exception:
            print(f'✅ TEST 5.{dest} PASSED: {dest} rejected as expected')
    
    return all_passed


def test_mixed_valid_and_invalid():
    """One invalid host in a list should cause rejection."""
    try:
        scope = CredentialScope(
            credential_type='test',
            required=True,
            host_allowlist=['api.github.com', 'example.com']  # One valid, one invalid
        )
        print('❌ TEST 6 FAILED: Mixed valid/invalid hosts were accepted')
        return False
    except Exception:
        print('✅ TEST 6 PASSED: Mixed valid/invalid hosts rejected (one bad apple)')
        return True


def main():
    """Run all validator verification tests."""
    print("=" * 70)
    print("CONTRACT VALIDATOR BUG FIX VERIFICATION")
    print("=" * 70)
    print()
    
    tests = [
        ("Real production hosts", test_host_allowlist_accepts_real_hosts),
        ("Placeholder rejection", test_host_allowlist_rejects_placeholders),
        ("Empty string rejection", test_host_allowlist_rejects_empty),
        ("Network destinations (real)", test_network_destinations_accepts_real_hosts),
        ("Network destinations (placeholders)", test_network_destinations_rejects_placeholders),
        ("Mixed valid/invalid", test_mixed_valid_and_invalid),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nRunning: {name}")
        print("-" * 70)
        passed = test_func()
        results.append((name, passed))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = all(passed for _, passed in results)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED - Validator bug fix verified!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Validator still has issues")
        return 1


if __name__ == '__main__':
    sys.exit(main())
